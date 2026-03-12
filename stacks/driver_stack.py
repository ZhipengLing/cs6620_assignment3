"""
DriverStack – Lambda that orchestrates the test sequence.

Performs S3 creates / updates / deletes and finally calls the plotting
API to generate the chart.
"""

from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_s3 as s3,
)
from constructs import Construct


class DriverStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        bucket: s3.IBucket,
        api_url: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -------- Lambda Function --------
        self.lambda_function = lambda_.Function(
            self,
            "DriverFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("lambda_code/driver"),
            timeout=Duration.minutes(5),
            memory_size=256,
            environment={
                "BUCKET_NAME": bucket.bucket_name,
                "PLOTTING_API_URL": api_url,
            },
            description="Driver function for testing S3 size tracking system",
        )

        # -------- Permissions --------
        bucket.grant_read_write(self.lambda_function)
        bucket.grant_delete(self.lambda_function)
