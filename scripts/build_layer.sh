#!/usr/bin/env bash
# build_layer.sh – Download the matplotlib Lambda layer from AWS
#
# Usage:
#   chmod +x scripts/build_layer.sh
#   ./scripts/build_layer.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT="$PROJECT_DIR/layers/matplotlib-layer.zip"
LAYER_ARN="arn:aws:lambda:us-west-2:843363563410:layer:matplotlib-layer:5"

mkdir -p "$PROJECT_DIR/layers"

if [ -f "$OUTPUT" ]; then
    echo "✓ Layer zip already exists at: $OUTPUT"
    echo "  Delete it first if you want to re-download."
    exit 0
fi

echo "Downloading matplotlib layer from AWS..."

URL=$(aws lambda get-layer-version-by-arn \
    --arn "$LAYER_ARN" \
    --query 'Content.Location' \
    --output text)

curl -o "$OUTPUT" "$URL"

echo "✓ Layer downloaded successfully: $OUTPUT"
echo "  Size: $(du -h "$OUTPUT" | cut -f1)"
