"""
DriverStack – Lambda that orchestrates the test sequence.

Cross-stack values injected automatically by CDK
--------------------------------------------------
* BUCKET_NAME       ← StorageStack's S3 bucket name
* PLOTTING_API_URL  ← PlottingStack's API Gateway URL (e.g. https://xxx/prod/plot)

These are passed as constructor parameters in app.py and set as Lambda
environment variables.  CDK generates CloudFormation cross-stack exports
so the actual values are resolved at deploy time — no hardcoding needed.
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
        # BUCKET_NAME:       resolved from StorageStack at deploy time
        # PLOTTING_API_URL:  resolved from PlottingStack at deploy time
        # The Driver Lambda reads these via os.environ at runtime.
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
        # grant_read_write + grant_delete: Driver creates, updates, and deletes
        # objects in the bucket during the test sequence.
        bucket.grant_read_write(self.lambda_function)
        bucket.grant_delete(self.lambda_function)
