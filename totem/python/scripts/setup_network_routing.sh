#!/bin/bash
# Setup network routing with iptables
# This allows internet sharing from the Ethernet to Wi-Fi hotspot clients

set -e  # Exit on error

echo "============================================"
echo "Totem: Network Routing Setup"
echo "============================================"

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
   echo "This script must be run as root" 
   exit 1
fi

# 1. Enable IP forwarding
echo "Enabling IP forwarding..."
sudo sed -i 's/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/' /etc/sysctl.conf
sudo sysctl -p

# 2. Setup iptables for NAT routing
echo "Setting up iptables rules for routing..."

# Clear existing rules
iptables -F
iptables -t nat -F
iptables -X

# Setup NAT
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# Forward from wlan0 to eth0
iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT
iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT

# Allow established connections
iptables -A INPUT -m state --state RELATED,ESTABLISHED -j ACCEPT

# Allow local connection
iptables -A INPUT -i lo -j ACCEPT

# Allow SSH
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Allow DHCP
iptables -A INPUT -i wlan0 -p udp --dport 67:68 -j ACCEPT

# Allow DNS
iptables -A INPUT -i wlan0 -p udp --dport 53 -j ACCEPT
iptables -A INPUT -i wlan0 -p tcp --dport 53 -j ACCEPT

# Default policies
iptables -P FORWARD ACCEPT
iptables -P INPUT ACCEPT
iptables -P OUTPUT ACCEPT

# 3. Save iptables rules
echo "Saving iptables rules..."
sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
sudo netfilter-persistent reload

# 4. Create a service to apply rules on boot
echo "Creating iptables-restore service..."
cat << EOF | sudo tee /etc/systemd/system/iptables-restore.service > /dev/null
[Unit]
Description=Restore iptables rules
After=network.target

[Service]
Type=oneshot
ExecStart=/sbin/iptables-restore /etc/iptables/rules.v4
ExecStart=/sbin/ip6tables-restore /etc/iptables/rules.v6

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable iptables-restore

echo "============================================"
echo "Network routing setup complete!"
echo "Traffic from Wi-Fi clients will be routed through Ethernet."
echo "============================================"
echo "Please restart your Raspberry Pi to apply all changes."
echo "============================================" 