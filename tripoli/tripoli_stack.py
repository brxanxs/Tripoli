import json
from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_ssm as ssm,
    aws_iam as iam,
)
from constructs import Construct

TRIPOLI = "Tripoli"
DATACENTERS = ["valdez", "vegas"]

class TripoliStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucketMap = {}
        buckets = {}
        
        # Create s3 buckets
        for dc in DATACENTERS:
            CDK_bucketName = f"{TRIPOLI}-{dc}Bucket"
            bucket = s3.Bucket(self, CDK_bucketName,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                encryption=s3.BucketEncryption.S3_MANAGED,
                versioned=False)
            bucketMap[dc] = bucket.bucket_name
            buckets[dc] = bucket

        # Create Lambda
        CDK_lambdaName = f"{TRIPOLI}-PresignURL"
        urlExpirySeconds = 3600
        lambdaTimeoutSeconds = 30  # Lambda max timeout is 900 seconds (15 min)
        fn = _lambda.Function(self, CDK_lambdaName,
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="presign_url.main",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.seconds(lambdaTimeoutSeconds),
            environment={
                "SSM_bucketMap_PARAM": "/tripoli/buckets",
                "URL_EXPIRATION": str(urlExpirySeconds)
            })

        # Lambda PUT permission to buckets
        for dc in DATACENTERS:
            buckets[dc].grant_put(fn)

        # Grant SSM read permission upfront (without specific parameter dependency)
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter"],
            resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/tripoli/buckets"]
        ))

        # REST API
        CDK_apiName = f"{TRIPOLI}-RestApiGW"
        api = apigw.RestApi(self, CDK_apiName)

        # Pass apiKey to Lambda (using proxy integration)
        fnIntegration = apigw.LambdaIntegration(fn, proxy=True)
        fnResource = api.root.add_resource("gen-url")
        fnResource.add_method("POST", fnIntegration, api_key_required=True)

        # Add API keys & Usage plans, and build out bucket map
        api_key_map = {}
        for dc in DATACENTERS:
            CDK_keyName = f"{TRIPOLI}-{dc}-ApiKey"
            key = api.add_api_key(CDK_keyName)
            CDK_usagePlanName = f"{TRIPOLI}-{dc}-UsagePlan"
            usagePlan = api.add_usage_plan(CDK_usagePlanName,
                api_stages=[apigw.UsagePlanPerApiStage(api=api, stage=api.deployment_stage)])
            usagePlan.add_api_key(key)

            # Map API key ID to bucket
            api_key_map[key.key_id] = bucketMap[dc]

            # Outputs key IDs
            CfnOutput(self, f"{dc}-ApiKeyID", value=key.key_id)

        # Create SSM SP with API key to bucket mapping
        CDK_ssmName = f"{TRIPOLI}-BucketMapSP"
        bucketMapSSM = ssm.StringParameter(self, CDK_ssmName,
            parameter_name="/tripoli/buckets",
            string_value=json.dumps(api_key_map))

        # API endpoint
        CfnOutput(self, "ApiEndpoint", value=api.url)