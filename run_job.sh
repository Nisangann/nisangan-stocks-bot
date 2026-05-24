#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# run_job.sh — Universal launcher for all Stocks scheduled jobs
# Usage: ./run_job.sh <script_name.py> [script args...]
#
# Loads .env for credentials, activates the venv, and runs the given script.
# Designed to be called by macOS launchd.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
ENV_FILE="$SCRIPT_DIR/.env"
LOG_DIR="$SCRIPT_DIR/logs"

mkdir -p "$LOG_DIR"

# Load environment variables from .env
if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "$(date): ERROR — .env file not found at $ENV_FILE" >> "$LOG_DIR/launcher.log"
    exit 1
fi

# Validate credentials are set
if [[ "$BOT_TOKEN" == "YOUR_BOT_TOKEN_HERE" || "$CHAT_ID" == "YOUR_CHAT_ID_HERE" ]]; then
    echo "$(date): ERROR — BOT_TOKEN or CHAT_ID not configured in .env" >> "$LOG_DIR/launcher.log"
    exit 1
fi

TARGET_SCRIPT="$SCRIPT_DIR/$1"
shift

if [[ ! -f "$TARGET_SCRIPT" ]]; then
    echo "$(date): ERROR — Script not found: $TARGET_SCRIPT" >> "$LOG_DIR/launcher.log"
    exit 1
fi

# Run the script
echo "$(date): Starting $1" >> "$LOG_DIR/launcher.log"
cd "$SCRIPT_DIR"
"$VENV_PYTHON" "$TARGET_SCRIPT" "$@" 2>&1 | tee -a "$LOG_DIR/launcher.log"
EXIT_CODE=${PIPESTATUS[0]}
echo "$(date): Finished $1 (exit code: $EXIT_CODE)" >> "$LOG_DIR/launcher.log"
exit $EXIT_CODE
