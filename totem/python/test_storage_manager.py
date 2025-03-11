#!/usr/bin/env python3

import os
import time
from utils.logger import logger
from managers.storage_manager import StorageManager

def test_write_with_options():
    """Test the updated write_data method with various options."""
    print("\n=== Testing StorageManager with Options ===")
    
    # Initialize the storage manager with the generic_nvme driver
    storage_manager = StorageManager("generic_nvme")
    
    # Generate unique test file paths
    timestamp = int(time.time())
    base_path = f"test_storage_{timestamp}"
    
    # Test case 1: Basic write with default options
    test_file_1 = f"{base_path}_basic.txt"
    data_1 = b"This is a basic test with default options"
    print(f"\nTest 1: Basic write with default options")
    print(f"Writing to: {test_file_1}")
    success_1 = storage_manager.write_data(test_file_1, data_1)
    print(f"Write success: {success_1}")
    
    # Verify data was written correctly
    read_data_1 = storage_manager.read_data(test_file_1)
    print(f"Data verification: {'✅ Passed' if read_data_1 == data_1.decode('utf-8') else '❌ Failed'}")
    
    # Test case 2: Write with append option
    test_file_2 = f"{base_path}_append.txt"
    data_2a = b"First part of data. "
    data_2b = b"Second part of data."
    print(f"\nTest 2: Write with append option")
    print(f"Writing first part to: {test_file_2}")
    storage_manager.write_data(test_file_2, data_2a)
    
    print(f"Appending second part")
    success_2 = storage_manager.write_data(test_file_2, data_2b, {"append": True})
    print(f"Append success: {success_2}")
    
    # Verify data was appended correctly
    expected_data_2 = data_2a + data_2b
    read_data_2 = storage_manager.read_data(test_file_2)
    print(f"Data verification: {'✅ Passed' if read_data_2 == expected_data_2.decode('utf-8') else '❌ Failed'}")
    
    # Test case 3: Write with custom permissions
    test_file_3 = f"{base_path}_permissions.txt"
    data_3 = b"Testing with custom permissions (0o644)"
    print(f"\nTest 3: Write with custom permissions")
    print(f"Writing to: {test_file_3} with permissions 0o644")
    success_3 = storage_manager.write_data(test_file_3, data_3, {"permissions": 0o644})
    print(f"Write success: {success_3}")
    
    # Verify permissions if we're on Linux
    if os.name == 'posix':
        try:
            file_path = os.path.join('/mnt/nvme', test_file_3)
            if os.path.exists(file_path):
                permissions = oct(os.stat(file_path).st_mode)[-3:]
                print(f"File permissions: {permissions} (Expected: 644)")
                print(f"Permissions verification: {'✅ Passed' if permissions == '644' else '❌ Failed'}")
            else:
                print(f"❌ Failed: File not found at expected path")
        except Exception as e:
            print(f"Error checking permissions: {e}")
    
    # Test case 4: Write with sync option
    test_file_4 = f"{base_path}_sync.txt"
    data_4 = b"Testing with sync option for immediate disk write"
    print(f"\nTest 4: Write with sync option")
    print(f"Writing to: {test_file_4} with sync option")
    start_time = time.time()
    success_4 = storage_manager.write_data(test_file_4, data_4, {"sync": True})
    elapsed = time.time() - start_time
    print(f"Write success: {success_4} (completed in {elapsed:.6f} seconds)")
    
    # Test case 5: Write with multiple options combined
    test_file_5 = f"{base_path}_combined.txt"
    data_5a = b"Initial data. "
    data_5b = b"Additional data with multiple options."
    print(f"\nTest 5: Write with multiple options combined")
    print(f"Writing initial data to: {test_file_5}")
    storage_manager.write_data(test_file_5, data_5a)
    
    print(f"Writing additional data with append, sync, and permissions options")
    options = {
        "append": True,
        "sync": True,
        "permissions": 0o600
    }
    success_5 = storage_manager.write_data(test_file_5, data_5b, options)
    print(f"Write success: {success_5}")
    
    # Verify final content
    expected_data_5 = data_5a + data_5b
    read_data_5 = storage_manager.read_data(test_file_5)
    print(f"Data verification: {'✅ Passed' if read_data_5 == expected_data_5.decode('utf-8') else '❌ Failed'}")
    
    # Summary
    print("\n=== Test Summary ===")
    print(f"Test 1 (Basic write): {'✅ Passed' if success_1 else '❌ Failed'}")
    print(f"Test 2 (Append): {'✅ Passed' if success_2 else '❌ Failed'}")
    print(f"Test 3 (Permissions): {'✅ Passed' if success_3 else '❌ Failed'}")
    print(f"Test 4 (Sync): {'✅ Passed' if success_4 else '❌ Failed'}")
    print(f"Test 5 (Combined options): {'✅ Passed' if success_5 else '❌ Failed'}")
    
    print("\nTest files created:")
    for file_name in [test_file_1, test_file_2, test_file_3, test_file_4, test_file_5]:
        print(f" - {file_name}")
    
    return all([success_1, success_2, success_3, success_4, success_5])

if __name__ == "__main__":
    import sys
    success = test_write_with_options()
    print(f"\n{'✅ All tests passed!' if success else '❌ Some tests failed!'}")
    sys.exit(0 if success else 1) 