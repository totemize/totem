#!/bin/bash
PI_USER="pi"
PI_HOST="raspberrypi.local"
SSH_KEY="$HOME/.ssh/id_rsa"
APP_DIR="/home/pi/app"
LOCAL_APP_DIR="$(pwd)/src"
SETUP_SCRIPT="setup_dependencies.sh"

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
]]

echo "Deploying application to Raspberry Pi..."

rsync -avz -e "ssh -i $SSH_KEY" "$LOCAL_APP_DIR/" "$PI_USER@$PI_HOST:$APP_DIR"

scp -i "$SSH_KEY" "$SETUP_SCRIPT" "$PI_USER@$PI_HOST:/home/$PI_USER/"

ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" << EOF
chmod +x /home/$PI_USER/$SETUP_SCRIPT
./$SETUP_SCRIPT
EOF

ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" << EOF
cd "$APP_DIR"
poetry install --no-dev
sudo systemctl restart myapp.service
EOF

echo "Deployment complete."