# Assignment 3 – CDK Deployment for S3 Bucket Size Tracking

**Author:** Zhipeng Ling  
**Course:** CS6620 – Fundamentals of Cloud Computing

## Architecture

Four CloudFormation stacks managed by AWS CDK:

| Stack | Resources |
|-------|-----------|
| `StorageStack` | S3 bucket, DynamoDB table (with GSI) |
| `SizeTrackingStack` | Size-tracking Lambda, S3 → Lambda event trigger |
| `PlottingStack` | Plotting Lambda, matplotlib Lambda Layer, REST API Gateway |
| `DriverStack` | Driver Lambda |

No resource names are hardcoded — CDK generates unique names automatically.

## Prerequisites

- Python 3.9+
- AWS CDK CLI (`npm install -g aws-cdk`)
- AWS credentials configured (`aws configure`)
- Docker (for building the matplotlib layer)

## Setup & Deploy

```bash
cd cs6620_assignment3

# 1. Build the matplotlib Lambda layer (requires Docker)
chmod +x scripts/build_layer.sh
./scripts/build_layer.sh

# 2. Create virtual environment and install CDK dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Bootstrap CDK (first time only per account/region)
cdk bootstrap

# 4. Deploy all stacks
cdk deploy --all --require-approval never
```

### Alternative: Copy existing layer zip

If you already have the matplotlib layer zip from Assignment 2:

```bash
mkdir -p layers
cp <path-to-your>/matplotlib-layer.zip layers/
```

## Test

1. Open AWS Console → Lambda
2. Find the Driver Lambda (name contains `DriverStack`)
3. Click **Test** → create an empty test event `{}`
4. Invoke and wait ~20 seconds
5. Check DynamoDB table for recorded size metrics
6. Download the `plot` object from the S3 bucket

## Demo Steps

```bash
# 0. Clean up everything
cdk destroy --all

# 1. Clone and reset
git clone <repo-url>
cd cs6620_assignment3
git reset --hard <YourCommitBefore8pm>

# 2. Prepare layer
chmod +x scripts/build_layer.sh
./scripts/build_layer.sh

# 3. Setup and deploy
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cdk deploy --all --require-approval never

# 4. Go to CloudFormation console → show 4 stacks and their resources
# 5. Invoke Driver Lambda → check DynamoDB + S3 plot
```

## Cleanup

```bash
cdk destroy --all
```
