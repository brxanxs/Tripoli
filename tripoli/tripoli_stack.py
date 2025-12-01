from aws_cdk import (
    # Duration,
    Stack,
    Duration,
    CfnOutput,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_ssm as ssm,
)
from constructs import Construct

DATACENTERS = ["valdez", "vegas"]

class TripoliStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        for dc in DATACENTERS:
            name = "backup-" + dc

            bucketName = "Bucket_" + name
            bucket = s3.Bucket(self, bucketName,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                encryption=s3.BucketEncryption.S3_MANAGED,
                versioned=False
            )

            fnName = "Lambda_" + name
            fn = _lambda.Function(self, fnName,
                runtime=_lambda.Runtime.PYTHON_3_12,
                handler="presign_url.handler",
                code=_lambda.Code.from_asset("lambda"),
                timeout=Duration.seconds(30),
                environment={"BUCKET_NAME": bucketName}
            )
            
            # Lambda permission
            bucket.grant_put(fn)

            # API endpoint
            apiName = "ApiEndpoint_" + name
            apiEndpoint = apigw.RestApi(
                self, apiName,
                deploy_options=apigw.StageOptions(stage_name="prod"),
                api_key_source_type=apigw.ApiKeySourceType.HEADER
            )
            
            # API method with Lambda function
            fn_integration = apigw.LambdaIntegration(fn)
            fn_resource = apiEndpoint.root.add_resource("gen-url")
            fn_resource.add_method(
                "GET",
                fn_integration,
                api_key_required=True
            )

            # Create key
            api_keyName = "ApiKey_" + name
            api_key = apiEndpoint.add_api_key(api_keyName)

            # Usage plan
            planName = "UsagePlan_" + name
            plan = apiEndpoint.add_usage_plan(planName,
                throttle=apigw.ThrottleSettings(
                    rate_limit=50,
                    burst_limit=20
                )
            )
            plan.add_api_key(api_key)
            plan.add_api_stage(
                stage=apiEndpoint.deployment_stage
            ) 
            
            # Outputs
            CfnOutput(self, f"{dc}-BucketName", value=bucketName)
            CfnOutput(self, f"{dc}-ApiEndpoint", value=apiEndpoint.url)
            CfnOutput(self, f"{dc}-ApiKey", value=api_key.key_id)

