"""
Plotting Lambda – generates a matplotlib chart of bucket size history.
Author: Zhipeng Ling

When invoked via API Gateway:
  1. Queries DynamoDB for the last N seconds of size data (Query, NOT Scan)
  2. Queries DynamoDB for the historical max across all records for that bucket
  3. Plots a line chart with a horizontal "historical high" line
  4. Uploads the PNG to S3 as ``plot``
"""

import io
import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import boto3
from boto3.dynamodb.conditions import Key

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


@dataclass
class Config:
    bucket_name: str
    table_name: str = "S3-object-size-history"
    window_seconds: int = 10
    plot_key: str = "plot"


s3_client = boto3.client("s3")
ddb = boto3.resource("dynamodb")


def _to_int(n: Any) -> int:
    return int(n) if not isinstance(n, Decimal) else int(n)


def _get_config(event: Dict[str, Any]) -> Config:
    qs = (event or {}).get("queryStringParameters") or {}
    bucket = qs.get("bucket") or os.environ.get("BUCKET_NAME")
    if not bucket:
        raise ValueError("Bucket name not provided. Set BUCKET_NAME env or pass ?bucket=")
    window_str = qs.get("window") or os.environ.get("WINDOW_SECONDS", "10")
    try:
        window = int(window_str)
    except Exception:
        window = 10
    table = os.environ.get("TABLE_NAME", "S3-object-size-history")
    return Config(bucket_name=bucket, table_name=table, window_seconds=window)


def _query_last_window(
    table, bucket: str, now_epoch: int, window_seconds: int
) -> List[Dict[str, Any]]:
    """Return items in [now - window, now] using a Query (not Scan)."""
    since = now_epoch - window_seconds
    items: List[Dict[str, Any]] = []
    kwargs = {
        "KeyConditionExpression": Key("bucket_name").eq(bucket)
        & Key("timestamp").gte(since),
        "ScanIndexForward": True,
    }
    while True:
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek
    return items


def _query_all_for_max(table, bucket: str) -> int:
    """Query entire partition and return the maximum total_size ever recorded."""
    max_size = 0
    kwargs = {
        "KeyConditionExpression": Key("bucket_name").eq(bucket)
        & Key("timestamp").gte(0),
        "ScanIndexForward": True,
    }
    while True:
        resp = table.query(**kwargs)
        for it in resp.get("Items", []):
            sz = _to_int(it.get("total_size", 0))
            if sz > max_size:
                max_size = sz
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek
    return max_size


def _generate_plot(points: List[Tuple[int, int]], historical_high: int) -> bytes:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    fig, ax = plt.subplots(figsize=(7, 3.5), dpi=150)

    if xs:
        x0 = xs[0]
        x_secs = [x - x0 for x in xs]
        ax.plot(
            x_secs, ys, marker="o", linewidth=1.5, color="#1f77b4",
            label="Bucket size (last window)",
        )
    else:
        ax.plot([], [], label="No data in window")

    ax.axhline(
        y=historical_high, color="#d62728", linestyle="--", linewidth=1.2,
        label="Historical high",
    )

    ax.set_xlabel("Seconds (relative)")
    ax.set_ylabel("Total size (bytes)")
    ax.set_title("Bucket size change with historical high")
    ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.6)
    ax.legend(loc="best", fontsize=8)

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        cfg = _get_config(event)
        table = ddb.Table(cfg.table_name)
        now_epoch = int(time.time())

        window_items = _query_last_window(
            table, cfg.bucket_name, now_epoch, cfg.window_seconds
        )
        points: List[Tuple[int, int]] = sorted(
            [
                (_to_int(it["timestamp"]), _to_int(it.get("total_size", 0)))
                for it in window_items
            ]
        )

        historical_high = _query_all_for_max(table, cfg.bucket_name)

        png_bytes = _generate_plot(points, historical_high)

        s3_client.put_object(
            Bucket=cfg.bucket_name,
            Key=cfg.plot_key,
            Body=png_bytes,
            ContentType="image/png",
            CacheControl="no-cache",
        )

        body = {
            "bucket": cfg.bucket_name,
            "s3_key": cfg.plot_key,
            "window_seconds": cfg.window_seconds,
            "num_points": len(points),
            "historical_high": historical_high,
        }
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
