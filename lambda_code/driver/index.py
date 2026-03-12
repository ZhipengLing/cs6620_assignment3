"""
Driver Lambda – orchestrates S3 operations and triggers the plot.
Author: Zhipeng Ling

Sequence:
  1. Create  assignment1.txt  ("Empty Assignment 1\n")   → 19 bytes
  2. Update  assignment1.txt  ("Empty Assignment 2222222222\n") → 28 bytes
  3. Delete  assignment1.txt
  4. Create  assignment2.txt  ("33")                     → 2 bytes
  5. Call the plotting REST API
"""

import json
import os
import time
import urllib.request
import urllib.error
from typing import Any, Dict

import boto3


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        bucket_name = os.environ["BUCKET_NAME"]
        plotting_api_url = os.environ["PLOTTING_API_URL"]

        s3_client = boto3.client("s3")
        results: Dict[str, Any] = {"operations": [], "plot_generation": None, "errors": []}

        print(f"Driver starting – bucket={bucket_name}, api={plotting_api_url}")

        # ---- 1. Create assignment1.txt (19 bytes) ----
        _put(s3_client, bucket_name, "assignment1.txt", "Empty Assignment 1\n", results, 1, "CREATE")
        time.sleep(3)

        # ---- 2. Update assignment1.txt (28 bytes) ----
        _put(s3_client, bucket_name, "assignment1.txt", "Empty Assignment 2222222222\n", results, 2, "UPDATE")
        time.sleep(3)

        # ---- 3. Delete assignment1.txt ----
        _delete(s3_client, bucket_name, "assignment1.txt", results, 3)
        time.sleep(3)

        # ---- 4. Create assignment2.txt (2 bytes) ----
        _put(s3_client, bucket_name, "assignment2.txt", "33", results, 4, "CREATE")

        # Wait for the last size-tracking invocation to finish
        time.sleep(3)

        # ---- 5. Call plotting API ----
        _call_plotting_api(plotting_api_url, bucket_name, results)

        successful = sum(1 for op in results["operations"] if op["status"] == "success")
        total = len(results["operations"])
        print(f"=== SUMMARY === {successful}/{total} ops OK")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Driver lambda completed",
                    "successful_operations": successful,
                    "total_operations": total,
                    "plot_generated": (
                        results["plot_generation"]["status"] == "success"
                        if results["plot_generation"]
                        else False
                    ),
                    "results": results,
                },
                indent=2,
            ),
        }

    except Exception as e:
        print(f"Driver lambda failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


# ---------- helpers ----------

def _put(s3, bucket, key, body, results, step, op_type):
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="text/plain")
        results["operations"].append(
            {"step": step, "operation": f"{op_type} {key}", "size": len(body), "status": "success"}
        )
        print(f"  [{step}] {op_type} {key} ({len(body)} bytes)")
    except Exception as e:
        msg = f"Failed {op_type} {key}: {e}"
        results["errors"].append(msg)
        print(f"  [{step}] ERROR – {msg}")


def _delete(s3, bucket, key, results, step):
    try:
        s3.delete_object(Bucket=bucket, Key=key)
        results["operations"].append(
            {"step": step, "operation": f"DELETE {key}", "size": 0, "status": "success"}
        )
        print(f"  [{step}] DELETE {key}")
    except Exception as e:
        msg = f"Failed DELETE {key}: {e}"
        results["errors"].append(msg)
        print(f"  [{step}] ERROR – {msg}")


def _call_plotting_api(url, bucket_name, results):
    try:
        print(f"Calling plotting API: {url}")
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                results["plot_generation"] = {
                    "status": "success",
                    "api_response": data,
                    "plot_url": f"s3://{bucket_name}/plot",
                }
                print(f"  Plot generated: {data}")
            else:
                err = f"Plotting API returned {resp.status}"
                results["plot_generation"] = {"status": "failed", "error": err}
                results["errors"].append(err)
    except Exception as e:
        err = f"Plotting API call failed: {e}"
        results["plot_generation"] = {"status": "failed", "error": err}
        results["errors"].append(err)
        print(f"  ERROR – {err}")
