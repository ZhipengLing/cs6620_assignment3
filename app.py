#!/usr/bin/env python3
"""
Assignment 3 - S3 Bucket Size Tracking System using AWS CDK
Author: Zhipeng Ling

Deploys Assignment 2 resources via CDK in 4 stacks:
  1. StorageStack       – S3 bucket + DynamoDB table (with GSI)
  2. SizeTrackingStack  – Lambda triggered by S3 events
  3. PlottingStack      – Lambda + matplotlib layer + REST API
  4. DriverStack        – Lambda for orchestrating test operations
"""

import aws_cdk as cdk
from stacks.storage_stack import StorageStack
from stacks.size_tracking_stack import SizeTrackingStack
from stacks.plotting_stack import PlottingStack
from stacks.driver_stack import DriverStack


app = cdk.App()

# ---------- Stack 1: Storage (S3 + DynamoDB) ----------
storage_stack = StorageStack(
    app,
    "StorageStack",
    description="S3 bucket and DynamoDB table for size tracking",
)

# ---------- Stack 2: Size-tracking Lambda ----------
size_tracking_stack = SizeTrackingStack(
    app,
    "SizeTrackingStack",
    bucket=storage_stack.bucket,
    table=storage_stack.table,
    description="Size-tracking Lambda triggered by S3 events",
)
size_tracking_stack.add_dependency(storage_stack)

# ---------- Stack 3: Plotting Lambda + API Gateway ----------
plotting_stack = PlottingStack(
    app,
    "PlottingStack",
    bucket=storage_stack.bucket,
    table=storage_stack.table,
    description="Plotting Lambda with matplotlib layer and REST API",
)
plotting_stack.add_dependency(storage_stack)

# ---------- Stack 4: Driver Lambda ----------
driver_stack = DriverStack(
    app,
    "DriverStack",
    bucket=storage_stack.bucket,
    api_url=plotting_stack.api_url,
    description="Driver Lambda for end-to-end testing",
)
driver_stack.add_dependency(storage_stack)
driver_stack.add_dependency(plotting_stack)

# ---------- Useful outputs ----------
cdk.CfnOutput(storage_stack, "BucketName",
               value=storage_stack.bucket.bucket_name)
cdk.CfnOutput(storage_stack, "TableName",
               value=storage_stack.table.table_name)
cdk.CfnOutput(plotting_stack, "PlottingApiUrl",
               value=plotting_stack.api_url)

app.synth()
