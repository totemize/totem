#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import time

# Setup direct logging without using the logger module yet
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('totem')

# Add the parent directory to the path so we can import our modules
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))  # Python directory
sys.path.insert(0, parent_dir)

# Define a function to import the required modules
def import_modules():
    try:
        # Try direct imports first
        from managers.storage_manager import StorageManager
        from devices.nvme.nvme import NVME
        from devices.nvme.drivers.generic_nvme import Driver as NVMeDriver
        return StorageManager, NVME, NVMeDriver
    except ImportError:
        # Try alternate import path
        sys.path.insert(0, os.path.abspath(os.path.join(parent_dir, '..')))  # Totem root directory
        try:
            from totem.python.managers.storage_manager import StorageManager
            from totem.python.devices.nvme.nvme import NVME
            from totem.python.devices.nvme.drivers.generic_nvme import Driver as NVMeDriver
            return StorageManager, NVME, NVMeDriver
        except ImportError as e:
            logger.error(f"Failed to import required modules: {e}")
            raise

def confirm_action(message="Do you want to continue?"):
    """Ask for user confirmation before proceeding with an action."""
    response = input(f"{message} (y/N): ").lower().strip()
    return response == 'y'

def dump_partition_info(partition, mount_point=None):
    """Display basic information about a partition."""
    print(f"\nPartition info for {partition}:")
    
    # Get filesystem type
    fs_type = "Unknown"
    try:
        result = subprocess.run(['blkid', '-o', 'value', '-s', 'TYPE', partition], 
                                capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            fs_type = result.stdout.strip()
        print(f"Filesystem: {fs_type}")
    except Exception as e:
        print(f"Error getting filesystem type: {e}")
    
    # Get size info
    try:
        result = subprocess.run(['lsblk', '-b', '-n', '-o', 'SIZE', partition], 
                                capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            size_bytes = int(result.stdout.strip())
            size_gb = size_bytes / (1024**3)
            print(f"Size: {size_gb:.2f} GB ({size_bytes} bytes)")
    except Exception as e:
        print(f"Error getting partition size: {e}")
    
    # Check mount status
    if mount_point:
        print(f"Mounted at: {mount_point}")
        
        # Show disk usage
        try:
            result = subprocess.run(['df', '-h', mount_point], 
                                    capture_output=True, text=True, check=False)
            if result.returncode == 0:
                print("\nDisk Usage:")
                for line in result.stdout.splitlines():
                    print(f"  {line}")
        except Exception as e:
            print(f"Error getting disk usage: {e}")
        
        # List top-level directories and files
        try:
            if os.path.exists(mount_point):
                print("\nTop-level content:")
                items = os.listdir(mount_point)
                if not items:
                    print("  <empty>")
                else:
                    for item in sorted(items)[:10]:  # Show first 10 items
                        item_path = os.path.join(mount_point, item)
                        if os.path.isdir(item_path):
                            print(f"  📁 {item}/")
                        else:
                            size = os.path.getsize(item_path)
                            print(f"  📄 {item} ({size} bytes)")
                    
                    if len(items) > 10:
                        print(f"  ... and {len(items) - 10} more items")
        except Exception as e:
            print(f"Error listing directory content: {e}")
    else:
        print("Status: Not mounted")

def test_with_direct_driver():
    """Test NVMe functionality using the driver directly."""
    logger.info("Testing NVMe detection with direct driver access")
    
    # Import required modules
    _, NVME, NVMeDriver = import_modules()
    
    # Initialize the driver directly
    nvme_driver = NVMeDriver()
    init_result = nvme_driver.init()
    
    if not init_result:
        logger.error("Failed to initialize NVMe driver")
        return False
    
    print("\n=== NVMe Device Information ===")
    print(f"Main NVMe device: {nvme_driver.nvme_device}")
    
    # List all partitions and their info
    partitions = nvme_driver.list_partitions()
    print(f"\nDetected {len(partitions)} partitions:")
    
    for i, (partition, fs_type, mount_point) in enumerate(partitions, 1):
        print(f"\n{i}. {partition}")
        print(f"   Type: {fs_type or 'Unknown'}")
        print(f"   Mount point: {mount_point or 'Not mounted'}")
    
    # Detailed partition inspection
    for partition, fs_type, mount_point in partitions:
        dump_partition_info(partition, mount_point)
    
    # Ask user which partition to work with
    if not partitions:
        print("No partitions found to work with.")
        return False
    
    while True:
        try:
            print("\nAvailable operations:")
            print("1. Mount a partition")
            print("2. Unmount a partition")
            print("3. Format a partition")
            print("4. Exit")
            
            choice = input("\nSelect an operation (1-4): ")
            
            if choice == '1':  # Mount a partition
                # List unmounted partitions
                unmounted = [(i, p) for i, (p, _, m) in enumerate(partitions, 1) if not m]
                if not unmounted:
                    print("All partitions are already mounted.")
                    continue
                
                print("\nUnmounted partitions:")
                for idx, part in unmounted:
                    print(f"{idx}. {part}")
                
                part_idx = int(input("Select partition to mount: ")) - 1
                if part_idx < 0 or part_idx >= len(partitions):
                    print("Invalid selection.")
                    continue
                
                partition = partitions[part_idx][0]
                mount_point = input("Enter mount point (e.g., /mnt/nvme): ")
                
                if confirm_action(f"Mount {partition} at {mount_point}?"):
                    success = nvme_driver.mount_partition(partition, mount_point)
                    if success:
                        print(f"Successfully mounted {partition} at {mount_point}")
                        # Update mount point in partitions list
                        partitions[part_idx] = (partition, partitions[part_idx][1], mount_point)
                    else:
                        print(f"Failed to mount {partition}")
            
            elif choice == '2':  # Unmount a partition
                # List mounted partitions
                mounted = [(i, p, m) for i, (p, _, m) in enumerate(partitions, 1) if m]
                if not mounted:
                    print("No mounted partitions.")
                    continue
                
                print("\nMounted partitions:")
                for idx, part, mount in mounted:
                    print(f"{idx}. {part} (mounted at {mount})")
                
                part_idx = int(input("Select partition to unmount: ")) - 1
                if part_idx < 0 or part_idx >= len(partitions):
                    print("Invalid selection.")
                    continue
                
                partition = partitions[part_idx][0]
                
                if confirm_action(f"Unmount {partition}?"):
                    success = nvme_driver.unmount_partition(partition)
                    if success:
                        print(f"Successfully unmounted {partition}")
                        # Update mount point in partitions list
                        partitions[part_idx] = (partition, partitions[part_idx][1], None)
                    else:
                        print(f"Failed to unmount {partition}")
            
            elif choice == '3':  # Format a partition
                print("\nAvailable partitions:")
                for i, (p, fs, m) in enumerate(partitions, 1):
                    status = f"(mounted at {m})" if m else "(not mounted)"
                    print(f"{i}. {p} - {fs or 'Unknown'} {status}")
                
                part_idx = int(input("Select partition to format: ")) - 1
                if part_idx < 0 or part_idx >= len(partitions):
                    print("Invalid selection.")
                    continue
                
                partition = partitions[part_idx][0]
                
                print("\nAvailable filesystems:")
                print("1. ext4")
                print("2. fat32")
                fs_choice = input("Select filesystem type (1-2): ")
                
                if fs_choice == '1':
                    fs_type = 'ext4'
                elif fs_choice == '2':
                    fs_type = 'fat32'
                else:
                    print("Invalid selection.")
                    continue
                
                label = input("Enter volume label (optional): ")
                
                if confirm_action(f"⚠️ WARNING: Format {partition} with {fs_type}? ALL DATA WILL BE LOST!"):
                    if confirm_action("Are you ABSOLUTELY SURE? This cannot be undone!"):
                        success = nvme_driver.format_partition(partition, fs_type, label if label else None)
                        if success:
                            print(f"Successfully formatted {partition} as {fs_type}")
                            # Update filesystem type in partitions list
                            partitions[part_idx] = (partition, fs_type, None)
                        else:
                            print(f"Failed to format {partition}")
            
            elif choice == '4':  # Exit
                print("Exiting NVMe test.")
                break
            
            else:
                print("Invalid choice. Please select a number between 1 and 4.")
                
        except ValueError:
            print("Please enter a valid number.")
        except Exception as e:
            print(f"Error: {e}")
    
    return True

def test_with_storage_manager():
    """Test NVMe functionality using the StorageManager."""
    logger.info("Testing NVMe with StorageManager")
    
    # Import required modules
    StorageManager, _, _ = import_modules()
    
    try:
        # Create test file and read it back
        test_file_path = "nvme_test_file.txt"
        test_data = "NVMe Storage Test Data - " + "X" * 100
        
        print(f"Writing test data to {test_file_path}...")
        storage_manager = StorageManager(driver_name='generic_nvme')
        storage_manager.write_data(test_file_path, test_data)
        
        print(f"Reading data from {test_file_path}...")
        read_data = storage_manager.read_data(test_file_path)
        
        if read_data == test_data:
            print("\n✅ NVMe Storage Test Passed: Data integrity confirmed.")
        else:
            print("\n❌ NVMe Storage Test Failed: Data mismatch.")
            print(f"Original: {test_data[:50]}...")
            print(f"Read: {read_data[:50]}...")
        
        return True
    except Exception as e:
        logger.error(f"Error in storage manager test: {e}")
        print(f"\n❌ NVMe Storage Test Failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Test NVMe Storage')
    parser.add_argument('--direct', action='store_true', help='Use direct driver instead of StorageManager')
    parser.add_argument('--log-level', choices=['debug', 'info', 'warning', 'error'], 
                      default='info', help='Set the logging level')
    args = parser.parse_args()
    
    # Set logging level
    import logging
    log_level = getattr(logging, args.log_level.upper())
    logger.setLevel(log_level)
    
    print("=== NVMe Storage Test ===")
    
    if args.direct:
        test_with_direct_driver()
    else:
        test_with_storage_manager()
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    main() 