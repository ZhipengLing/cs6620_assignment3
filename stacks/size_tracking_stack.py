"""
SizeTrackingStack – Lambda that reacts to S3 object events via EventBridge.

Uses EventBridge rules (instead of direct S3 notifications) to avoid
circular dependency between StorageStack and this stack.
"""

from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
)
from constructs import Construct


class SizeTrackingStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        bucket: s3.IBucket,
        table: dynamodb.ITable,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -------- Lambda Function --------
        self.lambda_function = lambda_.Function(
            self,
            "SizeTrackingFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("lambda_code/size_tracking"),
            timeout=Duration.minutes(1),
            memory_size=256,
            environment={
                "TABLE_NAME": table.table_name,
            },
            description="Tracks S3 bucket size changes and records to DynamoDB",
        )

        # -------- Permissions --------
        bucket.grant_read(self.lambda_function)
        table.grant_write_data(self.lambda_function)

        # -------- EventBridge Rules (S3 → Lambda) --------
        # Object Created events
        events.Rule(
            self,
            "OnObjectCreated",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={"bucket": {"name": [bucket.bucket_name]}},
            ),
            targets=[targets.LambdaFunction(self.lambda_function)],
        )

        # Object Deleted events
        events.Rule(
            self,
            "OnObjectDeleted",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Deleted"],
                detail={"bucket": {"name": [bucket.bucket_name]}},
            ),
            targets=[targets.LambdaFunction(self.lambda_function)],
        )
