from aws_cdk import (
    # Duration,
    Stack,
    # aws_sqs as sqs,
    aws_s3 as s3,
    aws_lambda as lambda_,
)
from constructs import Construct

class TripoliStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here
        # This is a test

        # example resource
        # queue = sqs.Queue(
        #     self, "TripoliQueue",
        #     visibility_timeout=Duration.seconds(300),
        # )

        # temporary log storage
        # replace this bucket and add trigger for lambda
        temp_bucket = s3.Bucket(self, "TempBucket")

        # bucket for reports
        report_bucket = s3.Bucket(self, "ReportBucket")

        
