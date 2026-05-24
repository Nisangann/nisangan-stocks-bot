#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# stocks_ctl.sh — Control panel for local Stocks scheduled jobs
#
# Usage:
#   ./stocks_ctl.sh status          Show status of all jobs
#   ./stocks_ctl.sh start           Load all jobs into launchd
#   ./stocks_ctl.sh stop            Unload all jobs from launchd
#   ./stocks_ctl.sh restart         Stop + Start
#   ./stocks_ctl.sh disable-github-local
#                                      Unload old local jobs now owned by GitHub
#   ./stocks_ctl.sh run <script>    Run a specific script immediately
#   ./stocks_ctl.sh logs            Tail the launcher log
# ─────────────────────────────────────────────────────────────────────────────

PLIST_DIR="$HOME/Library/LaunchAgents"
LOCAL_JOBS=(
    "com.stocks.portfolio-monitor"
    "com.stocks.weekly-digest"
    "com.stocks.fii-dii-tracker"
    "com.stocks.mf-shadow"
)

GITHUB_JOBS=(
    "morning_digest.py"
    "stock_analyst_bot.py --once"
)

GITHUB_LAUNCHD_JOBS=(
    "com.stocks.morning-digest"
    "com.stocks.stock-analyst-bot"
    "com.nisangan.morningdigest"
    "com.nisangan.stockanalyst"
)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

unload_job() {
    local job="$1"
    launchctl unload "$PLIST_DIR/$job.plist" 2>/dev/null || true
}

job_loaded() {
    local job="$1"
    local result
    result=$(launchctl list "$job" 2>&1)
    ! echo "$result" | grep -q "Could not find"
}

disable_github_local_jobs() {
    echo "Ensuring GitHub-owned jobs are not loaded locally..."
    for job in "${GITHUB_LAUNCHD_JOBS[@]}"; do
        if job_loaded "$job"; then
            unload_job "$job"
            echo "  ✓ unloaded $job"
        fi
    done
}

case "${1:-status}" in
    status)
        echo "═══ Stocks Job Status ═══"
        echo "Local launchd jobs managed on this Mac:"
        printf "%-35s %s\n" "JOB" "STATUS"
        printf "%-35s %s\n" "---" "------"
        for job in "${LOCAL_JOBS[@]}"; do
            result=$(launchctl list "$job" 2>&1)
            if echo "$result" | grep -q "Could not find"; then
                printf "%-35s %s\n" "$job" "⏹  Not loaded"
            else
                pid=$(echo "$result" | grep '"PID"' | awk '{print $NF}' | tr -d ';')
                exit_code=$(launchctl list | grep "$job" | awk '{print $2}')
                if [[ -n "$pid" && "$pid" != "0" ]]; then
                    printf "%-35s %s\n" "$job" "▶  Running (PID: $pid)"
                else
                    printf "%-35s %s\n" "$job" "⏸  Waiting (last exit: $exit_code)"
                fi
            fi
        done
        echo
        echo "GitHub-owned jobs (not managed by launchd here):"
        for job in "${GITHUB_JOBS[@]}"; do
            printf "%-35s %s\n" "$job" "Runs from GitHub Actions"
        done
        for job in "${GITHUB_LAUNCHD_JOBS[@]}"; do
            if job_loaded "$job"; then
                printf "%-35s %s\n" "$job" "⚠ loaded locally; run ./stocks_ctl.sh disable-github-local"
            fi
        done
        ;;
    start)
        echo "Loading local Mac jobs..."
        for job in "${LOCAL_JOBS[@]}"; do
            launchctl load "$PLIST_DIR/$job.plist" 2>/dev/null && echo "  ✓ $job" || echo "  ⚠ $job (already loaded?)"
        done
        disable_github_local_jobs
        ;;
    stop)
        echo "Unloading local Mac jobs..."
        for job in "${LOCAL_JOBS[@]}"; do
            launchctl unload "$PLIST_DIR/$job.plist" 2>/dev/null && echo "  ✓ $job" || echo "  ⚠ $job (not loaded?)"
        done
        disable_github_local_jobs
        ;;
    disable-github-local)
        disable_github_local_jobs
        ;;
    restart)
        "$0" stop
        sleep 1
        "$0" start
        ;;
    run)
        if [[ -z "$2" ]]; then
            echo "Usage: $0 run <script.py>"
            echo "Available scripts:"
            echo "  portfolio_monitor.py"
            echo "  weekly_digest.py"
            echo "  fii_dii_tracker.py"
            echo "  mf_shadow.py"
            echo "GitHub-owned scripts:"
            echo "  morning_digest.py"
            echo "  stock_analyst_bot.py --once"
            exit 1
        fi
        if [[ "$2" == "morning_digest.py" || "$2" == "stock_analyst_bot.py" ]]; then
            echo "Note: $2 is GitHub-owned now. Running it locally only for a manual test."
        fi
        "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/run_job.py" "${@:2}"
        ;;
    logs)
        tail -f "$SCRIPT_DIR/logs/launcher.log"
        ;;
    *)
        echo "Usage: $0 {status|start|stop|restart|disable-github-local|run <script.py>|logs}"
        exit 1
        ;;
esac
