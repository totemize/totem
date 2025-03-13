#!/bin/bash
# Run EInk diagnostics with various options

# Set the directory to the project root
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
TOTEM_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$TOTEM_DIR"

# Default PIN to use is 9 (which we know is free)
PIN=${1:-9}
TEST=${2:-"all"}

export PYTHONPATH="${TOTEM_DIR}"

echo "Running EInk diagnostics with PIN=${PIN} and TEST=${TEST}"
echo "PYTHONPATH: ${PYTHONPATH}"

# Run the diagnostics script
python3 python/tests/test_eink_diagnostics.py --pin ${PIN} --test ${TEST}

exit $? 