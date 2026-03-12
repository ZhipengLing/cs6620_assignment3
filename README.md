# Assignment 3 – CDK Deployment for S3 Bucket Size Tracking

**Author:** Zhipeng Ling  
**Course:** CS6620 – Fundamentals of Cloud Computing

## Overview

This project uses AWS CDK (Python) to deploy the same S3 bucket size tracking system from Assignment 2. All resources are managed by CDK across four stacks — no manual AWS Console setup is needed.

## Architecture

| Stack | Resources |
|-------|-----------|
| `StorageStack` | S3 bucket (EventBridge enabled), DynamoDB table with GSI |
| `SizeTrackingStack` | Size-tracking Lambda, EventBridge rules (Object Created / Deleted) |
| `PlottingStack` | Plotting Lambda, matplotlib Lambda Layer, REST API Gateway |
| `DriverStack` | Driver Lambda |

No resource names are hardcoded — CDK generates unique names automatically.

### Why EventBridge Instead of Direct S3 Notifications?

In Assignment 2, we configured S3 event notifications directly on the bucket to trigger the
size-tracking Lambda. However, in CDK this causes a **circular dependency** when the bucket
and the Lambda live in separate stacks:

- `SizeTrackingStack` depends on `StorageStack` (it needs the bucket reference)
- But `bucket.add_event_notification(lambda)` writes the Lambda ARN back into
  the StorageStack template, making `StorageStack` also depend on `SizeTrackingStack`

This creates a cycle that CDK rejects. The solution is **EventBridge**:

1. `StorageStack` enables `event_bridge_enabled=True` on the S3 bucket — this tells S3
   to send all object events to the default EventBridge bus (one-way, no reference to any Lambda)
2. `SizeTrackingStack` creates EventBridge Rules that match events from that specific bucket
   and route them to the Lambda

This is a one-directional flow: StorageStack → EventBridge → SizeTrackingStack, no cycle.

### How the Plotting API URL Reaches the Driver Lambda

The Driver Lambda needs to call the plotting REST API, but the API URL is only known after
the PlottingStack is deployed. CDK handles this automatically through cross-stack references:

1. **PlottingStack** creates the API Gateway and exposes the URL as `self.api_url`
2. **app.py** passes `plotting_stack.api_url` as a constructor parameter to `DriverStack`
3. **DriverStack** injects the URL into the Lambda's environment variable `PLOTTING_API_URL`
4. **Driver Lambda code** reads `os.environ["PLOTTING_API_URL"]` at runtime

CDK resolves the actual URL at deploy time and generates CloudFormation cross-stack exports/imports
behind the scenes — no manual updates or placeholder values needed.

## Project Structure

```
cs6620_assignment3/
├── app.py                      # CDK app entry point (wires stacks together)
├── cdk.json                    # CDK configuration
├── requirements.txt            # Python dependencies
├── stacks/
│   ├── storage_stack.py        # S3 bucket + DynamoDB table
│   ├── size_tracking_stack.py  # Size-tracking Lambda + EventBridge rules
│   ├── plotting_stack.py       # Plotting Lambda + Layer + API Gateway
│   └── driver_stack.py         # Driver Lambda
├── lambda_code/
│   ├── size_tracking/index.py  # Triggered by S3 events, records to DynamoDB
│   ├── plotting/index.py       # Generates matplotlib plot, stores in S3
│   └── driver/index.py         # Orchestrates S3 ops + calls plotting API
├── layers/                     # matplotlib-layer.zip (not in git, download before deploy)
└── scripts/
    └── build_layer.sh          # Downloads matplotlib layer zip from AWS
```

## Prerequisites

- Python 3.9+
- AWS CDK CLI (`npm install -g aws-cdk`)
- AWS credentials configured (`aws configure`)
- matplotlib Lambda Layer already published in your AWS account

## Setup & Deploy

```bash
cd cs6620_assignment3

# 1. Download the matplotlib Lambda layer
chmod +x scripts/build_layer.sh
./scripts/build_layer.sh

# 2. Install CDK Python dependencies
pip install -r requirements.txt

# 3. Bootstrap CDK (first time only per account/region)
cdk bootstrap

# 4. Deploy all stacks
cdk deploy --all --require-approval never
```

## Test

1. Open AWS Console → Lambda
2. Find the Driver Lambda (name contains `DriverStack-DriverFunction`)
3. Click **Test** → create an empty test event `{}`
4. Invoke and wait ~20 seconds
5. Check DynamoDB table for recorded size metrics (19 → 28 → 0 → 2 bytes)
6. Download the `plot` object from the S3 bucket to view the chart

## Demo Steps

```bash
# 0. Clean up all stacks
cdk destroy --all

# 1. Clone and reset
git clone <repo-url>
cd cs6620_assignment3
git reset --hard <YourCommitBefore8pm>

# 2. Download matplotlib layer
chmod +x scripts/build_layer.sh
./scripts/build_layer.sh

# 3. Install dependencies and deploy
pip install -r requirements.txt
cdk deploy --all --require-approval never

# 4. Go to CloudFormation console → verify 4 stacks and their resources
# 5. Invoke Driver Lambda → check DynamoDB table + download S3 plot
```

## Cleanup

```bash
cdk destroy --all
```
