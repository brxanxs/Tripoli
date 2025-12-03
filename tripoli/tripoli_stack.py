import json
from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    RemovalPolicy,
    aws_logs as logs,
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

        logBucketMap = {}
        logBuckets = {}
        
        # Create s3 buckets and lifecycle rules
        for dc in DATACENTERS:
            lifecycleRule = s3.LifecycleRule(
                enabled=True,
                expiration=Duration.days(365*5),
                transitions=[
                    s3.Transition(
                        storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                        transition_after=Duration.days(30)),
                    s3.Transition(
                        storage_class=s3.StorageClass.GLACIER_INSTANT_RETRIEVAL,
                        transition_after=Duration.days(90)
                    ),
                    s3.Transition(
                        storage_class=s3.StorageClass.GLACIER,
                        transition_after=Duration.days(180)
                    ),
                    s3.Transition(
                        storage_class=s3.StorageClass.DEEP_ARCHIVE,
                        transition_after=Duration.days(365*2)
                    )]
            )
            CDK_logBucketName = f"{TRIPOLI}-{dc}logBucket"
            logBucket = s3.Bucket(self, CDK_logBucketName,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                encryption=s3.BucketEncryption.S3_MANAGED,
                versioned=False,
                removal_policy=RemovalPolicy.DESTROY,
                auto_delete_objects=True,
                lifecycle_rules=[lifecycleRule])
            logBucketMap[dc] = logBucket.bucket_name
            logBuckets[dc] = logBucket

        # Create Lambda
        CDK_lambdaName = f"{TRIPOLI}-Lambda-PresignURL"
        urlExpirySeconds = 3600
        lambdaTimeoutSeconds = 30
        LambdaPresignURL = _lambda.Function(self, CDK_lambdaName,
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="presign_url.main",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.seconds(lambdaTimeoutSeconds),
            environment={
                "SSM_logBucketMap_PARAM": "/tripoli/buckets",
                "URL_EXPIRATION": str(urlExpirySeconds)
            })

        # Lambda PUT permission to buckets
        for dc in DATACENTERS:
            logBuckets[dc].grant_put(LambdaPresignURL)

        # Grant SSM read permission upfront (without specific parameter dependency)
        LambdaPresignURL.add_to_role_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter"],
            resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/tripoli/buckets"]
        ))

        # REST API
        CDK_APIPresignURLName = f"{TRIPOLI}-RestApiGW"
        APIPresignURL = apigw.RestApi(self, CDK_APIPresignURLName)

        # Pass apiKey to Lambda (using proxy integration)
        LambdaPresignURLIntegration = apigw.LambdaIntegration(LambdaPresignURL, proxy=True)
        LambdaPresignURLResource = APIPresignURL.root.add_resource("gen-url")
        LambdaPresignURLResource.add_method("POST", LambdaPresignURLIntegration, api_key_required=True)

        # Add API keys & Usage plans, and build out bucket map
        PresignURLapi_key_map = {}
        for dc in DATACENTERS:
            CDK_keyName = f"{TRIPOLI}-{dc}-APIPresignURLKey"
            key = APIPresignURL.add_api_key(CDK_keyName)
            CDK_usagePlanName = f"{TRIPOLI}-{dc}-UsagePlan"
            usagePlan = APIPresignURL.add_usage_plan(CDK_usagePlanName,
                api_stages=[apigw.UsagePlanPerApiStage(api=APIPresignURL, stage=APIPresignURL.deployment_stage)])
            usagePlan.add_api_key(key)

            # Map API key ID to bucket
            PresignURLapi_key_map[key.key_id] = logBucketMap[dc]

            # Outputs key IDs
            CfnOutput(self, f"{dc}-APIPresignURLKeyID", value=key.key_id)

        # Create SSM SP with API key to bucket mapping
        CDK_ssmName = f"{TRIPOLI}-logBucketMapSP"
        logBucketMapSSM = ssm.StringParameter(self, CDK_ssmName,
            parameter_name="/tripoli/buckets",
            string_value=json.dumps(PresignURLapi_key_map))

        # API endpoint
        CfnOutput(self, "APIPresignURLEndpoint", value=APIPresignURL.url)