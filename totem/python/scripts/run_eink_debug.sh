#!/bin/bash
# Run E-Ink debug mode and capture output to a log file

# Ensure we're in the correct directory
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Kill any existing Python processes
pkill -f python || true
sleep 2

# Create timestamp
TIMESTAMP=$(date +%s)
LOG_FILE="eink_debug_${TIMESTAMP}.log"

# Run the test with debug mode and capture output
echo "Running E-Ink debug mode..."
python system_test.py --test eink-debug --log-level debug > "$LOG_FILE" 2>&1

# Check exit code
EXIT_CODE=$?

# Show summary
echo "Test completed with exit code $EXIT_CODE. Output saved to $LOG_FILE"
echo "Last 20 lines of output:"
tail -n 20 "$LOG_FILE"

# Print log file location
echo "Full log available at: $(pwd)/$LOG_FILE" 