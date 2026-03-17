#!/bin/bash
# Run ticket checker and send results via OpenClaw to Telegram
cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null
output=$(python -m src.main 2>&1)
exit_code=$?

if [ $exit_code -eq 0 ] && [ -n "$output" ]; then
    # Only notify if there are actual events (not the "no events" message)
    # Or always notify — user wants updates either way
    openclaw run --message "$output" --target "telegram:6987951065" 2>/dev/null || \
    echo "$output"
fi
