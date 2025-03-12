#!/bin/bash
# Run tests with sudo while preserving the Poetry environment

set -e  # Exit on error

# Get the current user's Poetry virtual environment path
POETRY_VENV_PATH=$(poetry env info -p)
echo "Using Poetry virtualenv: $POETRY_VENV_PATH"

# Make directories if needed
if [ "$1" == "nvme" ]; then
  # Create the test directory with proper permissions
  TEST_DIR="/mnt/nvme/nvme_test_$(date +%s)"
  sudo mkdir -p "$TEST_DIR"
  sudo chown -R $USER:$USER "$TEST_DIR"
  echo "Created test directory with proper permissions: $TEST_DIR"
fi

# Run the test using the Poetry Python interpreter directly
if [ "$1" == "nvme" ]; then
  echo "Running NVMe tests with Poetry environment..."
  sudo -E "$POETRY_VENV_PATH/bin/python" -m tests.system_test --test nvme --log-level info
elif [ "$1" == "eink" ]; then
  echo "Running E-Ink tests with Poetry environment..."
  "$POETRY_VENV_PATH/bin/python" -m tests.system_test --test eink --log-level info
elif [ "$1" == "all" ]; then
  echo "Running all tests with Poetry environment..."
  sudo -E "$POETRY_VENV_PATH/bin/python" -m tests.system_test --test all --log-level info
else
  echo "Usage: $0 [nvme|eink|all]"
  echo "  nvme: Run NVMe tests"
  echo "  eink: Run E-Ink tests"
  echo "  all: Run all tests"
  exit 1
fi 