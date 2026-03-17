#!/bin/bash
# Start worker with auto-restart

while true; do
    echo "Starting worker..."
    python worker_standalone.py
    
    exit_code=$?
    echo "Worker exited with code $exit_code"
    
    if [ $exit_code -eq 0 ]; then
        echo "Clean exit, stopping."
        break
    fi
    
    echo "Restarting in 5 seconds..."
    sleep 5
done
