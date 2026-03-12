"""
StorageStack – S3 bucket and DynamoDB table.

Resources
---------
* S3 Bucket  (no hardcoded name – CDK generates a unique one)
    - EventBridge enabled so that S3 events flow to EventBridge
* DynamoDB table
    PK = bucket_name (S)
    SK = timestamp   (N)
    GSI: timestamp-index  (PK = timestamp)
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
        self.bucket = s3.Bucket(
            self,
            "TestBucket",
            versioned=False,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            # Send S3 events to EventBridge (avoids cross-stack circular ref)
            event_bridge_enabled=True,
        )

        # -------- DynamoDB Table --------
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

        # GSI for time-based queries across all buckets
        self.table.add_global_secondary_index(
            index_name="timestamp-index",
            partition_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )
