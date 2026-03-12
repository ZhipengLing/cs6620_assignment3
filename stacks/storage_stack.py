"""
StorageStack – S3 bucket and DynamoDB table.

Design Decisions
----------------
* event_bridge_enabled=True:
    Instead of configuring S3 event notifications directly (which would
    require referencing the size-tracking Lambda ARN and create a circular
    dependency between StorageStack ↔ SizeTrackingStack), we enable
    EventBridge on the bucket.  This makes S3 publish ALL object events to
    the default EventBridge bus — a one-way operation that does not reference
    any downstream consumer.  The SizeTrackingStack then sets up EventBridge
    Rules to filter and route the relevant events to its Lambda.

* No hardcoded names:
    CDK auto-generates unique names for the bucket and table, satisfying the
    assignment requirement "do not hardcode any resource's name".

Resources
---------
* S3 Bucket  (EventBridge enabled, auto-delete on destroy)
* DynamoDB table
    PK = bucket_name (S)   – supports multiple buckets
    SK = timestamp   (N)   – enables time-range queries
    GSI: timestamp-index   – allows querying by time across all buckets
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class StorageStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -------- S3 Bucket --------
        # event_bridge_enabled=True sends all S3 object events to EventBridge.
        # This avoids circular dependency: StorageStack does NOT need to know
        # about any Lambda; the SizeTrackingStack independently subscribes to
        # the events via EventBridge Rules.
        self.bucket = s3.Bucket(
            self,
            "TestBucket",
            versioned=False,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            event_bridge_enabled=True,
        )

        # -------- DynamoDB Table --------
        # PK = bucket_name so we can store size history for multiple buckets.
        # SK = timestamp (epoch) so we can query a time range with KeyCondition.
        self.table = dynamodb.Table(
            self,
            "SizeHistoryTable",
            partition_key=dynamodb.Attribute(
                name="bucket_name",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # GSI for time-based queries across all buckets (used by plotting
        # lambda to find the historical max across ANY bucket).
        self.table.add_global_secondary_index(
            index_name="timestamp-index",
            partition_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )
