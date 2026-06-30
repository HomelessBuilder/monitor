#!/bin/bash
# Hourly monitor cron script
# Invokes the Claude Code monitor instance and saves the report

MONITOR_DIR="$HOME/monitor"
REPORT_DIR="$MONITOR_DIR/reports"
LOG="$MONITOR_DIR/cron.log"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M)
REPORT_FILE="$REPORT_DIR/$TIMESTAMP.md"

# Ensure PATH includes claude
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

cd "$MONITOR_DIR" || exit 1

echo "[$(date)] Monitor check started" >> "$LOG"

claude --print --model claude-haiku-4-5-20251001 "Run your monitoring check per the procedure in your CLAUDE.md." > "$REPORT_FILE" 2>> "$LOG"

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  echo "[$(date)] ERROR: claude exited with code $EXIT_CODE" >> "$LOG"
else
  echo "[$(date)] Report written to $REPORT_FILE" >> "$LOG"
fi
