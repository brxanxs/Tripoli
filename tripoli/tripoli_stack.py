from aws_cdk import (
    # Duration,
    Stack,
    # aws_sqs as sqs,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_sns as sns,
    aws_events as events,
    aws_events_targets as targets,
    aws_apigateway as apig,
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
        # replace this bucket
        temp_bucket = s3.Bucket(self, "TempBucket")

        # bucket for reports
        report_bucket = s3.Bucket(self, "ReportBucket")

        # sns for sending reports
        report_message = sns.Topic(self, "ReportSNS")

        # lambda for making the report
        # cutoff is for what files in the last hours should be reported
        # expiration is how long the URL will last in seconds
        report_lambda = lambda_.Function(
            self,
            "ReporterLambda",
            runtime = lambda_.Runtime.PYTHON_3_13,
            code = lambda_.Code.from_asset("lambda"),
            handler = "reporter.lambda_handler",
            environment = {
                "INPUT_BUCKET_NAME" : temp_bucket.bucket_name,
                "OUTPUT_BUCKET_NAME" : report_bucket.bucket_name,
                "REPORTER_SNS_ARN" : report_message.topic_arn,
                "CUTOFF_HOUR" : "24",
                "REPORT_URL_EXPIRATION_SECONDS" : "86400"
            }
        )

        temp_bucket.grant_read(report_lambda)
        report_bucket.grant_put(report_lambda)
        report_message.grant_publish(report_lambda)

        # event bridge trigger for reporter lambda
        # In UTC time, every day, at 11 am
        report_schedule = events.Rule(
            self, 
            "ReportSchedule",
            schedule = events.Schedule.cron(
                minute = "0",
                hour = "11",
                day = "*",
                month = "*",
                year = "*",
            )
        )

        report_schedule.add_target(targets.LambdaFunction(report_lambda))

        report_api = apig.LambdaRestApi(
            self,
            "ReporterAPI",
            handler = report_lambda,
            proxy = True
        )


