"""
PlottingStack – Lambda + matplotlib layer + REST API Gateway.

When invoked via the API, the Lambda reads recent size history from
DynamoDB, generates a matplotlib plot, and stores it as ``plot`` in S3.
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
        matplotlib_layer = lambda_.LayerVersion(
            self,
            "MatplotlibLayer",
            code=lambda_.Code.from_asset("layers/matplotlib-layer.zip"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="matplotlib and dependencies for plotting",
        )

        # -------- Lambda Function --------
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

        # Expose the full URL so DriverStack can use it
        self.api_url = f"{api.url}plot"
