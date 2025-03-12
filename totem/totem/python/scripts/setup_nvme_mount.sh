#!/bin/bash
# NVMe Mount Script for Totem
# This script mounts the NVMe drive at /mnt/nvme during system boot

set -e  # Exit on error

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}     Totem: NVMe Mount Setup              ${NC}"
echo -e "${GREEN}============================================${NC}"

# Create mount point if it doesn't exist
if [ ! -d "/mnt/nvme" ]; then
    echo "Creating mount point directory at /mnt/nvme..."
    sudo mkdir -p /mnt/nvme
    sudo chown root:root /mnt/nvme
    sudo chmod 755 /mnt/nvme
fi

# Detect NVMe device
echo "Detecting NVMe devices..."
NVME_DEVICES=($(lsblk -d -o NAME,SIZE,TYPE | grep "nvme" | awk '{print "/dev/"$1}'))

if [ ${#NVME_DEVICES[@]} -eq 0 ]; then
    echo -e "${RED}No NVMe devices detected!${NC}"
    exit 1
fi

echo "Found ${#NVME_DEVICES[@]} NVMe device(s):"
for i in "${!NVME_DEVICES[@]}"; do
    echo -e "${GREEN}${NVME_DEVICES[$i]}${NC} - $(lsblk -d -o SIZE ${NVME_DEVICES[$i]} | tail -n 1)"
done

# Identify the partition to mount
echo "Detecting partitions on NVMe devices..."
PARTITIONS=()

for device in "${NVME_DEVICES[@]}"; do
    device_partitions=($(lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT -n -l "$device" | grep -v " $" | awk '{print "/dev/"$1}'))
    PARTITIONS+=("${device_partitions[@]}")
done

if [ ${#PARTITIONS[@]} -eq 0 ]; then
    echo -e "${YELLOW}No partitions found on NVMe devices.${NC}"
    
    # Ask to create a partition
    echo -e "${YELLOW}Would you like to create a partition on ${NVME_DEVICES[0]}? (y/N)${NC}"
    read -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Creating partition on ${NVME_DEVICES[0]}..."
        # Create a GPT partition table
        sudo parted "${NVME_DEVICES[0]}" mklabel gpt
        # Create a partition using all available space
        sudo parted "${NVME_DEVICES[0]}" mkpart primary ext4 0% 100%
        # Update the PARTITIONS array
        PARTITIONS=($(lsblk -o NAME,SIZE -n -l "${NVME_DEVICES[0]}" | grep -v " $" | awk '{print "/dev/"$1}'))
        
        # Format the partition
        echo "Formatting partition ${PARTITIONS[0]} as ext4..."
        sudo mkfs.ext4 "${PARTITIONS[0]}"
    else
        echo "Exiting without creating a partition."
        exit 1
    fi
fi

echo "Found ${#PARTITIONS[@]} partition(s):"
for i in "${!PARTITIONS[@]}"; do
    fs_type=$(lsblk -o FSTYPE -n "${PARTITIONS[$i]}")
    mount_point=$(lsblk -o MOUNTPOINT -n "${PARTITIONS[$i]}")
    echo -e "${GREEN}${PARTITIONS[$i]}${NC} - Type: ${fs_type:-Unknown}, Mounted: ${mount_point:-Not mounted}"
done

# If multiple partitions, ask which one to use
TARGET_PARTITION=${PARTITIONS[0]}
if [ ${#PARTITIONS[@]} -gt 1 ]; then
    echo -e "${YELLOW}Multiple partitions found. Which one would you like to mount at /mnt/nvme?${NC}"
    for i in "${!PARTITIONS[@]}"; do
        echo "$((i+1)). ${PARTITIONS[$i]}"
    done
    read -p "Enter selection (1-${#PARTITIONS[@]}): " selection
    
    if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le "${#PARTITIONS[@]}" ]; then
        TARGET_PARTITION=${PARTITIONS[$((selection-1))]}
    else
        echo -e "${RED}Invalid selection. Using ${TARGET_PARTITION}.${NC}"
    fi
fi

echo "Selected partition: ${TARGET_PARTITION}"

# Check if partition is already mounted
MOUNT_POINT=$(lsblk -o MOUNTPOINT -n "${TARGET_PARTITION}")
if [ -n "$MOUNT_POINT" ]; then
    echo -e "${YELLOW}Partition is already mounted at ${MOUNT_POINT}${NC}"
    
    if [ "$MOUNT_POINT" != "/mnt/nvme" ]; then
        echo -e "${YELLOW}Would you like to unmount from ${MOUNT_POINT} and mount at /mnt/nvme? (y/N)${NC}"
        read -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Unmounting from ${MOUNT_POINT}..."
            sudo umount "${MOUNT_POINT}"
        else
            echo "Keeping current mount point."
            exit 0
        fi
    else
        echo "Already mounted at /mnt/nvme. No changes needed."
        exit 0
    fi
fi

# Check filesystem and format if necessary
FS_TYPE=$(lsblk -o FSTYPE -n "${TARGET_PARTITION}")
if [ -z "$FS_TYPE" ] || [ "$FS_TYPE" = "null" ]; then
    echo -e "${YELLOW}No filesystem detected on ${TARGET_PARTITION}.${NC}"
    echo -e "${YELLOW}Would you like to format it as ext4? (y/N)${NC}"
    read -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Formatting ${TARGET_PARTITION} as ext4..."
        sudo mkfs.ext4 "${TARGET_PARTITION}"
        FS_TYPE="ext4"
    else
        echo "Cannot mount without a filesystem. Exiting."
        exit 1
    fi
fi

# Mount the partition
echo "Mounting ${TARGET_PARTITION} to /mnt/nvme..."
sudo mount "${TARGET_PARTITION}" /mnt/nvme

# Check if mount was successful
if mountpoint -q /mnt/nvme; then
    echo -e "${GREEN}Successfully mounted ${TARGET_PARTITION} at /mnt/nvme${NC}"
    
    # Set appropriate permissions
    echo "Setting permissions..."
    sudo chown totem:totem /mnt/nvme
    sudo chmod 775 /mnt/nvme
else
    echo -e "${RED}Failed to mount ${TARGET_PARTITION} at /mnt/nvme${NC}"
    exit 1
fi

# Configure automatic mounting at boot time
echo "Setting up automatic mounting at boot time..."

# Get UUID of the partition for stable mounting
UUID=$(sudo blkid -s UUID -o value "${TARGET_PARTITION}")

# Check if entry already exists in fstab
if grep -q "/mnt/nvme" /etc/fstab; then
    echo "A mount entry for /mnt/nvme already exists in /etc/fstab."
    echo "Checking if it uses UUID=${UUID}..."
    
    if grep -q "UUID=${UUID}" /etc/fstab; then
        echo -e "${GREEN}Entry is already correctly configured.${NC}"
    else
        echo -e "${YELLOW}Updating existing entry to use UUID=${UUID}...${NC}"
        sudo sed -i "s|.*\s/mnt/nvme\s.*|UUID=${UUID} /mnt/nvme ${FS_TYPE} defaults 0 2|" /etc/fstab
    fi
else
    echo "Adding entry to /etc/fstab..."
    echo "UUID=${UUID} /mnt/nvme ${FS_TYPE} defaults 0 2" | sudo tee -a /etc/fstab
fi

# Create a systemd service to ensure mount is available
echo "Creating systemd service for NVMe mount..."
cat << EOF | sudo tee /etc/systemd/system/mnt-nvme.mount > /dev/null
[Unit]
Description=Mount NVMe Drive
After=local-fs.target

[Mount]
What=UUID=${UUID}
Where=/mnt/nvme
Type=${FS_TYPE}
Options=defaults

[Install]
WantedBy=multi-user.target
EOF

# Enable the service
sudo systemctl daemon-reload
sudo systemctl enable mnt-nvme.mount

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}     NVMe Mount Setup Complete!            ${NC}"
echo -e "${GREEN}============================================${NC}"
echo -e "The NVMe drive (${TARGET_PARTITION}) is now:"
echo -e "  - Mounted at: ${GREEN}/mnt/nvme${NC}"
echo -e "  - Configured to mount automatically at boot"
echo -e "  - Accessible to the totem user"
echo -e "${GREEN}============================================${NC}" 