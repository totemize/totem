#!/bin/bash

# usage:
# ./deploy.sh -u pi -h 192.168.1.10 -k ~/.ssh/id_rsa_custom -a /home/pi/my_app -l ./my_src


PI_USER="pi"
PI_HOST="raspberrypi.local"
SSH_KEY="$HOME/.ssh/id_rsa"
APP_DIR="/home/pi/totem/python"
LOCAL_APP_DIR="$(pwd)/src"

function usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -u, --user          Raspberry Pi username (default: pi)"
    echo "  -h, --host          Raspberry Pi host/IP (default: raspberrypi.local)"
    echo "  -k, --key           SSH private key file (default: \$HOME/.ssh/id_rsa)"
    echo "  -a, --app-dir       Application directory on Raspberry Pi (default: /home/pi/app)"
    echo "  -l, --local-dir     Local application directory (default: ./src)"
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
        -l|--local-dir)
        LOCAL_APP_DIR="$2"
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

echo "Deploying application to Raspberry Pi..."

rsync -avz -e "ssh -i $SSH_KEY" "$LOCAL_APP_DIR/" "$PI_USER@$PI_HOST:$APP_DIR"

ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" << EOF
cd "$APP_DIR"
poetry install --no-dev
sudo systemctl restart totem.service
EOF

echo "Deployment complete."
