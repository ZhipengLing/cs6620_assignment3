"""
PlottingStack – Lambda + matplotlib layer + REST API Gateway.

How the API URL reaches the Driver Lambda
------------------------------------------
1. This stack creates the API Gateway and stores the full endpoint URL
   (e.g. https://xxx.execute-api.../prod/plot) in ``self.api_url``.
2. In app.py, ``plotting_stack.api_url`` is passed to the DriverStack
   constructor as a parameter.
3. DriverStack injects it into the Driver Lambda's environment variable
   ``PLOTTING_API_URL``.
4. At runtime, the Driver Lambda reads ``os.environ["PLOTTING_API_URL"]``
   and calls it via HTTP.

CDK handles the cross-stack reference automatically — it generates
CloudFormation Exports/Imports behind the scenes.  No manual URL copy
or placeholder values are needed.
"""

from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_apigateway as apigateway,
)
from constructs import Construct


class PlottingStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        bucket: s3.IBucket,
        table: dynamodb.ITable,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -------- matplotlib Lambda Layer (CDK-managed) --------
        # The zip is downloaded before deploy via scripts/build_layer.sh.
        # CDK uploads it to the bootstrap S3 bucket and creates the layer.
        matplotlib_layer = lambda_.LayerVersion(
            self,
            "MatplotlibLayer",
            code=lambda_.Code.from_asset("layers/matplotlib-layer.zip"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="matplotlib and dependencies for plotting",
        )

        # -------- Lambda Function --------
        # Environment variables are auto-resolved by CDK from other stacks:
        #   TABLE_NAME  ← StorageStack (DynamoDB table name)
        #   BUCKET_NAME ← StorageStack (S3 bucket name)
        self.lambda_function = lambda_.Function(
            self,
            "PlottingFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("lambda_code/plotting"),
            timeout=Duration.minutes(1),
            memory_size=512,
            layers=[matplotlib_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "BUCKET_NAME": bucket.bucket_name,
                "WINDOW_SECONDS": "30",
            },
            description="Generates matplotlib plots of bucket size history",
        )

        # -------- Permissions --------
        # grant_read_data: Lambda queries DynamoDB for size history
        # grant_put: Lambda uploads the generated plot PNG to S3
        table.grant_read_data(self.lambda_function)
        bucket.grant_put(self.lambda_function)

        # -------- REST API Gateway --------
        api = apigateway.RestApi(
            self,
            "PlottingApi",
            rest_api_name="S3SizeTrackingPlottingAPI",
            description="REST API for generating bucket size plots",
            deploy_options=apigateway.StageOptions(stage_name="prod"),
        )

        plot_resource = api.root.add_resource("plot")
        plot_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self.lambda_function, proxy=True),
        )

        # Expose the full URL (e.g. https://xxx.execute-api.../prod/plot)
        # so that DriverStack can pass it to its Lambda as an env var.
        # CDK resolves this at deploy time via CloudFormation cross-stack exports.
        self.api_url = f"{api.url}plot"
