"""
Size-tracking Lambda – triggered by S3 object events via EventBridge.
Author: Zhipeng Ling

Handles both EventBridge and S3 Notification event formats.

Each invocation:
  1. Reads the bucket name from the event
  2. Calculates total bucket size and object count
  3. Writes a snapshot to DynamoDB
"""

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, Tuple

import boto3

s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

TABLE_NAME = os.environ.get("TABLE_NAME", "S3-object-size-history")
table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        bucket_name, event_name = _parse_event(event)
        print(f"Processing event: {event_name} for bucket: {bucket_name}")

        total_size, object_count = _calculate_bucket_metrics(bucket_name)

        timestamp = int(time.time())
        recorded_at = datetime.utcnow().isoformat() + "Z"

        item = {
            "bucket_name": bucket_name,
            "timestamp": timestamp,
            "total_size": total_size,
            "object_count": object_count,
            "recorded_at": recorded_at,
            "triggered_by": event_name,
        }

        table.put_item(Item=item)
        print(f"Recorded metrics – Size: {total_size} bytes, Objects: {object_count}")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Bucket size tracking completed",
                    "bucket": bucket_name,
                    "total_size": total_size,
                    "object_count": object_count,
                    "timestamp": timestamp,
                }
            ),
        }

    except Exception as e:
        print(f"Error in size-tracking lambda: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def _parse_event(event: Dict[str, Any]) -> Tuple[str, str]:
    """
    Parse bucket name and event type from either EventBridge or S3 Notification format.

    EventBridge format:
      {"source": "aws.s3", "detail-type": "Object Created",
       "detail": {"bucket": {"name": "..."}, ...}}

    S3 Notification format:
      {"Records": [{"eventName": "ObjectCreated:Put",
       "s3": {"bucket": {"name": "..."}, ...}}]}
    """
    # EventBridge format
    if "detail" in event and "source" in event:
        bucket_name = event["detail"]["bucket"]["name"]
        event_name = event.get("detail-type", "Unknown")
        return bucket_name, event_name

    # S3 Notification format (fallback)
    record = event["Records"][0]
    bucket_name = record["s3"]["bucket"]["name"]
    event_name = record["eventName"]
    return bucket_name, event_name


def _calculate_bucket_metrics(bucket_name: str) -> Tuple[int, int]:
    """Return (total_size, object_count) for every object in the bucket."""
    total_size = 0
    object_count = 0
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket_name):
            for obj in page.get("Contents", []):
                total_size += obj["Size"]
                object_count += 1
        print(f"Metrics for {bucket_name}: {object_count} objects, {total_size} bytes")
    except Exception as e:
        print(f"Error calculating bucket metrics: {e}")
    return total_size, object_count
