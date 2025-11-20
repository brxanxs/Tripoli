from aws_cdk import (
    # Duration,
    Stack,
    aws_sns as sns,
)
from constructs import Construct

class TripoliStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        # example resource
        # queue = sqs.Queue(
        #     self, "TripoliQueue",
        #     visibility_timeout=Duration.seconds(300),
        # )
