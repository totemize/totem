#!/bin/bash
# Setup Wi-Fi hotspot functionality on Raspberry Pi
# This allows the Pi to act as an access point

set -e  # Exit on error

echo "============================================"
echo "Totem: Wi-Fi Hotspot Setup"
echo "============================================"

# Default configuration
SSID="TotemAP"
PASSWORD="totempassword"
CHANNEL=7
COUNTRY="US"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --ssid)
            SSID="$2"
            shift 2
            ;;
        --password)
            PASSWORD="$2"
            shift 2
            ;;
        --channel)
            CHANNEL="$2"
            shift 2
            ;;
        --country)
            COUNTRY="$2"
            shift 2
            ;;
        *)
            echo "Unknown parameter: $1"
            exit 1
            ;;
    esac
done

# 1. Install required packages
echo "Installing required packages for hotspot functionality..."
sudo apt-get update
sudo apt-get install -y hostapd dnsmasq

# 2. Stop services temporarily
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq

# 3. Configure static IP
echo "Configuring static IP for wlan0..."
if ! grep -q "interface wlan0" /etc/dhcpcd.conf; then
    cat << EOF | sudo tee -a /etc/dhcpcd.conf > /dev/null

# Configuration for Totem hotspot
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF
fi

# 4. Configure DHCP server (dnsmasq)
echo "Configuring DHCP server..."
sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig || true
cat << EOF | sudo tee /etc/dnsmasq.conf > /dev/null
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
domain=wlan
address=/totem.local/192.168.4.1
EOF

# 5. Configure access point (hostapd)
echo "Configuring hostapd..."
cat << EOF | sudo tee /etc/hostapd/hostapd.conf > /dev/null
interface=wlan0
driver=nl80211
ssid=${SSID}
hw_mode=g
channel=${CHANNEL}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=${PASSWORD}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
country_code=${COUNTRY}
EOF

# Ensure the configuration file is used
echo "Enabling hostapd configuration..."
sudo sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|g' /etc/default/hostapd

# 6. Enable and start services
echo "Enabling services to start on boot..."
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl enable dnsmasq

echo "============================================"
echo "Wi-Fi hotspot configuration complete!"
echo "SSID: ${SSID}"
echo "Password: ${PASSWORD}"
echo "Channel: ${CHANNEL}"
echo "Country: ${COUNTRY}"
echo "============================================"
echo "Please restart your Raspberry Pi to apply these changes."
echo "After restart, the hotspot should be available."
echo "============================================" 