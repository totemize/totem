#!/bin/bash
echo "Installing system dependencies..."

sudo apt-get update

REQUIRED_PACKAGES=(
    python3
    python3-pip
    python3-venv
    python3-dev
    build-essential
    libffi-dev
    libssl-dev
    libjpeg-dev
    libopenjp2-7
    libtiff5
    libatlas-base-dev
    libfreetype6-dev
    liblcms2-dev
    libwebp-dev
    zlib1g-dev
    libharfbuzz-dev
    libfribidi-dev
    libxcb1-dev
    i2c-tools
    spi-tools
    fonts-dejavu-core
)

for package in "${REQUIRED_PACKAGES[@]}"; do
    if dpkg -l | grep -q "^ii  $package "; then
        echo "$package is already installed."
    else
        echo "Installing $package..."
        sudo apt-get install -y "$package"
    fi
done

curl -sSL https://install.python-poetry.org | python3 -

if ! command -v poetry &> /dev/null; then
    echo "Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    source ~/.bashrc
else
    echo "Poetry is already installed."
fi

poetry install --extras "nfc eink"

echo "System dependencies installed successfully."