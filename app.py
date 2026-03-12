#!/usr/bin/env python3
"""
Assignment 3 - S3 Bucket Size Tracking System using AWS CDK
Author: Zhipeng Ling

Deploys Assignment 2 resources via CDK in 4 stacks:
  1. StorageStack       – S3 bucket (EventBridge enabled) + DynamoDB table (with GSI)
  2. SizeTrackingStack  – Lambda + EventBridge rules (S3 → Lambda)
  3. PlottingStack      – Lambda + matplotlib layer + REST API Gateway
  4. DriverStack        – Lambda that orchestrates test operations

Cross-stack data flow:
  StorageStack.bucket  ──►  SizeTrackingStack  (for read access + event filtering)
  StorageStack.bucket  ──►  PlottingStack      (for uploading plot)
  StorageStack.table   ──►  SizeTrackingStack  (for writing size snapshots)
  StorageStack.table   ──►  PlottingStack      (for querying size history)
  PlottingStack.api_url ──► DriverStack        (so Driver can call the plotting API)

CDK resolves all cross-stack references at deploy time via CloudFormation exports.
"""

import aws_cdk as cdk
from stacks.storage_stack import StorageStack
from stacks.size_tracking_stack import SizeTrackingStack
from stacks.plotting_stack import PlottingStack
from stacks.driver_stack import DriverStack


app = cdk.App()

# ---------- Stack 1: Storage (S3 + DynamoDB) ----------
# Foundation stack — all other stacks depend on it.
# S3 bucket has EventBridge enabled so events flow to the default bus.
storage_stack = StorageStack(
    app,
    "StorageStack",
    description="S3 bucket and DynamoDB table for size tracking",
)

# ---------- Stack 2: Size-tracking Lambda ----------
# Subscribes to S3 events via EventBridge (not direct S3 notifications)
# to avoid circular dependency with StorageStack.
size_tracking_stack = SizeTrackingStack(
    app,
    "SizeTrackingStack",
    bucket=storage_stack.bucket,
    table=storage_stack.table,
    description="Size-tracking Lambda triggered by S3 events via EventBridge",
)
size_tracking_stack.add_dependency(storage_stack)

# ---------- Stack 3: Plotting Lambda + API Gateway ----------
# Exposes self.api_url which is passed to DriverStack below.
plotting_stack = PlottingStack(
    app,
    "PlottingStack",
    bucket=storage_stack.bucket,
    table=storage_stack.table,
    description="Plotting Lambda with matplotlib layer and REST API",
)
plotting_stack.add_dependency(storage_stack)

# ---------- Stack 4: Driver Lambda ----------
# Receives api_url from PlottingStack — CDK auto-creates a CloudFormation
# export/import so the real URL is resolved at deploy time.
driver_stack = DriverStack(
    app,
    "DriverStack",
    bucket=storage_stack.bucket,
    api_url=plotting_stack.api_url,
    description="Driver Lambda for end-to-end testing",
)
driver_stack.add_dependency(storage_stack)
driver_stack.add_dependency(plotting_stack)

# ---------- Useful outputs (shown in terminal after deploy) ----------
cdk.CfnOutput(storage_stack, "BucketName",
               value=storage_stack.bucket.bucket_name)
cdk.CfnOutput(storage_stack, "TableName",
               value=storage_stack.table.table_name)
cdk.CfnOutput(plotting_stack, "PlottingApiUrl",
               value=plotting_stack.api_url)

app.synth()
