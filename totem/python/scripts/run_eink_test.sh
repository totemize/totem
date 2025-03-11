#!/bin/bash
# E-Ink Test Runner
# Runs the quick E-Ink hardware test and saves output to a log file

# Ensure we're in the correct directory
cd "$(dirname "$0")"

# Activate the virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Kill any existing Python processes that might interfere
pkill -f python || true
sleep 2

# Run the test and capture output to a log file
echo "Running E-Ink quick test..."
python eink_quick_test.py > eink_test_output.log 2>&1

# Check the result
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "Test completed successfully. See eink_test_output.log for details."
else
    echo "Test failed with exit code $EXIT_CODE. See eink_test_output.log for details."
fi

# Print the last few lines of the log for quick reference
echo "Last 10 lines of log:"
tail -n 10 eink_test_output.log

exit $EXIT_CODE 