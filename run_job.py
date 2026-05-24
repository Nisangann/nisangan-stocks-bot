#!/usr/bin/env python3
"""
run_job.py — Python replacement for run_job.sh

Bypasses macOS Full Disk Access restrictions on /bin/bash by running
everything through the venv Python interpreter instead.

Usage: .venv/bin/python run_job.py <script_name.py> [script args...]
"""

import sys
import os
import subprocess
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "launcher.log")


def log(msg):
    timestamp = datetime.datetime.now().strftime("%a %b %d %H:%M:%S IST %Y")
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp}: {msg}\n")


# ── Load .env ────────────────────────────────────────────────────────────────
env_file = os.path.join(SCRIPT_DIR, ".env")
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ[key.strip()] = value.strip()
else:
    log("ERROR — .env file not found at " + env_file)
    sys.exit(1)

# ── Validate credentials ────────────────────────────────────────────────────
if os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE") == "YOUR_BOT_TOKEN_HERE" or \
   os.environ.get("CHAT_ID", "YOUR_CHAT_ID_HERE") == "YOUR_CHAT_ID_HERE":
    log("ERROR — BOT_TOKEN or CHAT_ID not configured in .env")
    sys.exit(1)

# ── Determine target script ─────────────────────────────────────────────────
if len(sys.argv) < 2:
    log("ERROR — No script specified. Usage: run_job.py <script_name.py>")
    sys.exit(1)

target = sys.argv[1]
target_path = os.path.join(SCRIPT_DIR, target)
script_args = sys.argv[2:]

if not os.path.isfile(target_path):
    log(f"ERROR — Script not found: {target_path}")
    sys.exit(1)

# ── Run the script ───────────────────────────────────────────────────────────
log(f"Starting {target}")
os.chdir(SCRIPT_DIR)

result = subprocess.run([sys.executable, target_path, *script_args])

log(f"Finished {target} (exit code: {result.returncode})")
sys.exit(result.returncode)
