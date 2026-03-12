"""
SizeTrackingStack – Lambda that reacts to S3 object events via EventBridge.

Why EventBridge instead of S3 Notifications?
---------------------------------------------
Using bucket.add_event_notification() would write the Lambda ARN into
StorageStack's template, creating a circular dependency:

    StorageStack ──depends-on──► SizeTrackingStack  (Lambda ARN in bucket config)
    SizeTrackingStack ──depends-on──► StorageStack  (needs bucket reference)

EventBridge breaks this cycle:
    1. StorageStack enables event_bridge_enabled=True on the bucket.
       S3 sends events to the default EventBridge bus (no Lambda reference needed).
    2. This stack creates EventBridge Rules that match events from that bucket
       and route them to the Lambda.

Flow:  S3 bucket  ──►  EventBridge  ──►  EventBridge Rule  ──►  Lambda

The Lambda receives events in EventBridge format (different from S3 Notification
format), so the Lambda code handles both formats for compatibility.
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
        # TABLE_NAME is injected as an env var so the Lambda code doesn't
        # need to hardcode any resource name.
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
        # grant_read: Lambda needs to list objects in the bucket to calculate size
        # grant_write_data: Lambda writes size snapshots to DynamoDB
        bucket.grant_read(self.lambda_function)
        table.grant_write_data(self.lambda_function)

        # -------- EventBridge Rules --------
        # These rules subscribe to S3 events on the default EventBridge bus.
        # They only match events from our specific bucket (by bucket name).
        # CDK automatically adds the necessary Lambda invoke permission.

        # Rule 1: Fires when any object is created or updated in the bucket
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

        # Rule 2: Fires when any object is deleted from the bucket
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
