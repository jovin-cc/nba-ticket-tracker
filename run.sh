#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null
output=$(python -m src.main 2>&1)
exit_code=$?
if [ $exit_code -eq 0 ] && [ -n "$output" ]; then
    echo "$output"
fi
exit $exit_code
