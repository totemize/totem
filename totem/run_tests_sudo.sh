#!/bin/bash

# Wrapper script to run system tests with sudo

if [ $# -lt 1 ]; then
    echo "Usage: $0 [eink|nvme|all]"
    exit 1
fi

TEST_TYPE=$1

# Update repo first
echo "Updating repository..."
git pull

# Create test directory with proper permissions if needed
if [ "$TEST_TYPE" = "nvme" ] || [ "$TEST_TYPE" = "all" ]; then
    echo "Creating test directory with proper permissions..."
    sudo mkdir -p /mnt/nvme
    sudo chown -R $(whoami):$(whoami) /mnt/nvme
fi

# Run the test with sudo while preserving environment variables
echo "Running $TEST_TYPE test..."
if [ -d "totem" ]; then
    cd totem  # If we're in the repo root with a totem subdir
fi

# Check if we're using Poetry
if [ -f "pyproject.toml" ]; then
    # Run with Poetry
    echo "Using Poetry environment..."
    sudo -E PYTHONPATH=$(pwd) poetry run python3 python/tests/system_test.py --test "$TEST_TYPE"
else
    # Run with regular Python
    echo "Using system Python..."
    sudo -E PYTHONPATH=$(pwd) python3 python/tests/system_test.py --test "$TEST_TYPE"
fi 