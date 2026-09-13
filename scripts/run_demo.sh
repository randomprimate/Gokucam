#!/bin/bash
# Run GokuCam locally with synthetic hardware + canned AI responses — no
# Pi, camera, Robot HAT, or Anthropic API key needed. Intervals below are
# sped up from their real defaults purely so a demo session shows data
# accumulating instead of waiting an hour for the first snapshot.
set -e
cd "$(dirname "$0")/.."

export GOKU_MOCK_HARDWARE=1
export GOKU_AI_MOCK=1
export GOKU_PORT="${GOKU_PORT:-8000}"
export GOKU_SNAP_DIR="${GOKU_SNAP_DIR:-/tmp/gokucam_demo_captures}"
export GOKU_DB_PATH="${GOKU_DB_PATH:-/tmp/gokucam_demo.db}"

export GOKU_SNAPSHOT_INTERVAL_MIN="${GOKU_SNAPSHOT_INTERVAL_MIN:-0.5}"
export GOKU_AI_HEALTHCHECK_INTERVAL_HOURS="${GOKU_AI_HEALTHCHECK_INTERVAL_HOURS:-0.05}"
export GOKU_AI_ROUNDUP_INTERVAL_DAYS="${GOKU_AI_ROUNDUP_INTERVAL_DAYS:-0.005}"
export GOKU_AI_HIGHLIGHT_INTERVAL_DAYS="${GOKU_AI_HIGHLIGHT_INTERVAL_DAYS:-0.002}"

echo "Demo login: username=goku password=shellyeah"
exec python3 run.py
