#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse

def format_partition(partition, fs_type, label=None):
    """Format a partition with the specified filesystem type."""
    try:
        # Format command based on filesystem type
        if fs_type == 'ext4':
            cmd = ['mkfs.ext4']
            if label:
                cmd.extend(['-L', label])
            cmd.append(partition)
        elif fs_type == 'fat32' or fs_type == 'vfat':
            cmd = ['mkfs.vfat', '-F', '32']
            if label:
                cmd.extend(['-n', label])
            cmd.append(partition)
        else:
            print(f"Unsupported filesystem type: {fs_type}")
            return False
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            print(f"Successfully formatted {partition} as {fs_type}")
            return True
        else:
            print(f"Failed to format {partition}: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error formatting {partition}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Format NVMe Partition')
    parser.add_argument('--partition', required=True, help='Partition to format (e.g., /dev/nvme0n1p3)')
    parser.add_argument('--fs-type', choices=['ext4', 'fat32'], default='ext4', help='Filesystem type')
    parser.add_argument('--label', help='Volume label')
    args = parser.parse_args()
    
    print(f"About to format {args.partition} as {args.fs_type}")
    confirm = input("Are you SURE you want to continue? This will ERASE ALL DATA! (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        return
    
    format_partition(args.partition, args.fs_type, args.label)

if __name__ == "__main__":
    main() 