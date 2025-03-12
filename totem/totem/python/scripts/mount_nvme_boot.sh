#!/bin/bash
# NVMe Boot Mount Script for Totem
# This script is designed to run at system boot to mount NVMe at /mnt/nvme
# Non-interactive version for use in systemd service

# Redirect stdout and stderr to a log file
exec &> /var/log/nvme-mount.log

echo "=== Starting NVMe mount process: $(date) ==="

# Create mount point if it doesn't exist
if [ ! -d "/mnt/nvme" ]; then
    echo "Creating mount point directory at /mnt/nvme..."
    mkdir -p /mnt/nvme
    chown root:root /mnt/nvme
    chmod 755 /mnt/nvme
fi

# Detect NVMe device
echo "Detecting NVMe devices..."
NVME_DEVICES=($(lsblk -d -o NAME,SIZE,TYPE | grep "nvme" | awk '{print "/dev/"$1}'))

if [ ${#NVME_DEVICES[@]} -eq 0 ]; then
    echo "No NVMe devices detected!"
    exit 1
fi

echo "Found ${#NVME_DEVICES[@]} NVMe device(s):"
for device in "${NVME_DEVICES[@]}"; do
    echo "$device - $(lsblk -d -o SIZE $device | tail -n 1)"
done

# Identify partitions
echo "Detecting partitions on NVMe devices..."
PARTITIONS=()

for device in "${NVME_DEVICES[@]}"; do
    device_partitions=($(lsblk -o NAME,SIZE,FSTYPE -n -l "$device" | grep -v " $" | awk '{print "/dev/"$1}'))
    if [ ${#device_partitions[@]} -gt 0 ]; then
        PARTITIONS+=("${device_partitions[@]}")
    fi
done

if [ ${#PARTITIONS[@]} -eq 0 ]; then
    echo "No partitions found on NVMe devices. Cannot proceed."
    exit 1
fi

echo "Found ${#PARTITIONS[@]} partition(s):"
for partition in "${PARTITIONS[@]}"; do
    fs_type=$(lsblk -o FSTYPE -n "$partition")
    echo "$partition - Type: ${fs_type:-Unknown}"
done

# Check if any partition is already configured in fstab
CONFIGURED_PARTITION=""
if grep -q "/mnt/nvme" /etc/fstab; then
    echo "Found existing /mnt/nvme entry in fstab"
    UUID_IN_FSTAB=$(grep "/mnt/nvme" /etc/fstab | grep -o "UUID=[^ ]*" | cut -d= -f2)
    
    if [ -n "$UUID_IN_FSTAB" ]; then
        for partition in "${PARTITIONS[@]}"; do
            PART_UUID=$(blkid -s UUID -o value "$partition")
            if [ "$PART_UUID" = "$UUID_IN_FSTAB" ]; then
                CONFIGURED_PARTITION="$partition"
                echo "Found configured partition: $CONFIGURED_PARTITION with UUID=$PART_UUID"
                break
            fi
        done
    fi
fi

# If no configured partition found, use the first one with a filesystem
if [ -z "$CONFIGURED_PARTITION" ]; then
    for partition in "${PARTITIONS[@]}"; do
        fs_type=$(lsblk -o FSTYPE -n "$partition")
        if [ -n "$fs_type" ] && [ "$fs_type" != "null" ]; then
            CONFIGURED_PARTITION="$partition"
            echo "Selected first partition with filesystem: $CONFIGURED_PARTITION ($fs_type)"
            break
        fi
    done
fi

# If still no partition found, use the first one (but don't format it)
if [ -z "$CONFIGURED_PARTITION" ]; then
    CONFIGURED_PARTITION="${PARTITIONS[0]}"
    echo "No partition with filesystem found. Using first partition: $CONFIGURED_PARTITION"
    echo "WARNING: This partition has no filesystem and will not be mounted"
    exit 1
fi

# Check if partition is already mounted
MOUNT_POINT=$(lsblk -o MOUNTPOINT -n "$CONFIGURED_PARTITION")
if [ -n "$MOUNT_POINT" ]; then
    if [ "$MOUNT_POINT" = "/mnt/nvme" ]; then
        echo "Partition $CONFIGURED_PARTITION is already mounted at /mnt/nvme"
        exit 0
    else
        echo "Partition $CONFIGURED_PARTITION is mounted at $MOUNT_POINT. Trying to unmount..."
        umount "$MOUNT_POINT" || {
            echo "Failed to unmount $CONFIGURED_PARTITION from $MOUNT_POINT"
            exit 1
        }
    fi
fi

# Get the filesystem type
FS_TYPE=$(lsblk -o FSTYPE -n "$CONFIGURED_PARTITION")
if [ -z "$FS_TYPE" ] || [ "$FS_TYPE" = "null" ]; then
    echo "No filesystem on $CONFIGURED_PARTITION. Cannot mount."
    exit 1
fi

# Mount the partition
echo "Mounting $CONFIGURED_PARTITION to /mnt/nvme..."
mount "$CONFIGURED_PARTITION" /mnt/nvme || {
    echo "Failed to mount $CONFIGURED_PARTITION at /mnt/nvme"
    exit 1
}

# Check if mount was successful
if mountpoint -q /mnt/nvme; then
    echo "Successfully mounted $CONFIGURED_PARTITION at /mnt/nvme"
    
    # Set appropriate permissions
    echo "Setting permissions..."
    chown totem:totem /mnt/nvme
    chmod 775 /mnt/nvme
    
    # Get UUID of the partition for stable mounting
    UUID=$(blkid -s UUID -o value "$CONFIGURED_PARTITION")
    
    # Configure fstab if not already configured
    if ! grep -q "/mnt/nvme" /etc/fstab; then
        echo "Adding entry to /etc/fstab..."
        echo "UUID=$UUID /mnt/nvme $FS_TYPE defaults 0 2" >> /etc/fstab
        echo "Added fstab entry for UUID=$UUID"
    elif ! grep -q "UUID=$UUID" /etc/fstab; then
        echo "Updating existing fstab entry to use UUID=$UUID..."
        sed -i "s|.*\s/mnt/nvme\s.*|UUID=$UUID /mnt/nvme $FS_TYPE defaults 0 2|" /etc/fstab
        echo "Updated fstab entry for UUID=$UUID"
    else
        echo "fstab entry for UUID=$UUID already exists"
    fi
else
    echo "Failed to mount $CONFIGURED_PARTITION at /mnt/nvme"
    exit 1
fi

echo "=== NVMe mount process completed: $(date) ===" 