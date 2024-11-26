#!/bin/bash


PI_USER="pi"
PI_HOST="raspberrypi.local"
SSH_KEY="$HOME/.ssh/id_rsa"
APP_DIR="/home/pi/totem"

function usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -u, --user          Raspberry Pi username (default: pi)"
    echo "  -h, --host          Raspberry Pi host/IP (default: raspberrypi.local)"
    echo "  -k, --key           SSH private key file (default: \$HOME/.ssh/id_rsa)"
    echo "  -a, --app-dir       Application directory on Raspberry Pi (default: /home/pi/app)"
    echo "      --help          Show this help message"
    exit 1
}

while [[ $
    case $1 in
        -u|--user)
        PI_USER="$2"
        shift 2
        ;;
        -h|--host)
        PI_HOST="$2"
        shift 2
        ;;
        -k|--key)
        SSH_KEY="$2"
        shift 2
        ;;
        -a|--app-dir)
        APP_DIR="$2"
        shift 2
        ;;
        --help)
        usage
        ;;
        *)
        echo "Unknown option: $1"
        usage
        ;;
    esac
done

echo "Running tests on Raspberry Pi..."

ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" << EOF
cd "$APP_DIR"
poetry install --no-dev
poetry run pytest
EOF

TEST_EXIT_CODE=$?

if [ $TEST_EXIT_CODE -ne 0 ]; then
    echo "Tests failed on Raspberry Pi."
    exit $TEST_EXIT_CODE
else
    echo "All tests passed on Raspberry Pi."
fi
