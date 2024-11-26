
from managers.display_manager import DisplayManager
from managers.nfc_manager import NFCManager
from managers.storage_manager import StorageManager
from managers.network_manager import NetworkManager
from utils.logger import logger
import time

def test_eink_display():
    print("\n=== Testing E-Ink Display ===")
    try:
        display_manager = DisplayManager()
        display_manager.clear_screen()
        print("E-Ink display cleared. Please confirm the screen is blank.")
        input("Press Enter to continue...")

        test_message = "E-Ink Display Test"
        display_manager.display_text(test_message)
        print(f"Displayed message: '{test_message}' on the E-Ink screen.")
        print("Please confirm the message is visible on the screen.")
        input("Press Enter to continue...")


        print("E-Ink Display Test Completed.\n")
    except Exception as e:
        print(f"E-Ink Display Test Failed: {e}")

def test_nfc_device():
    print("\n=== Testing NFC Device ===")
    try:
        nfc_manager = NFCManager()
        print("Please place an NFC card/tag near the reader.")
        input("Press Enter when ready...")

        card_data = nfc_manager.read_card()
        print(f"Data read from NFC card: {card_data}")

        write_data = "NFC Test Data"
        nfc_manager.write_card(write_data)
        print(f"Data '{write_data}' written to NFC card.")
        print("Please confirm the NFC card was written successfully (e.g., by reading it again).")
        input("Press Enter to continue...")

        print("NFC Device Test Completed.\n")
    except Exception as e:
        print(f"NFC Device Test Failed: {e}")

def test_nvme_storage():
    print("\n=== Testing NVMe Storage ===")
    try:
        storage_manager = StorageManager()
        test_file_path = '/mnt/nvme_test_file.txt'
        test_data = "NVMe Storage Test Data"

        storage_manager.write_data(test_file_path, test_data)
        print(f"Data written to NVMe storage at {test_file_path}.")

        read_data = storage_manager.read_data(test_file_path)
        print(f"Data read from NVMe storage: {read_data}")

        if read_data == test_data:
            print("NVMe Storage Test Passed: Data integrity confirmed.")
        else:
            print("NVMe Storage Test Failed: Data mismatch.")

        print("Please confirm the NVMe storage is operational.")
        input("Press Enter to continue...")

        print("NVMe Storage Test Completed.\n")
    except Exception as e:
        print(f"NVMe Storage Test Failed: {e}")

def test_wifi_controller():
    print("\n=== Testing Wi-Fi Controller ===")
    try:
        network_manager = NetworkManager()

        current_status = network_manager.get_wifi_status()
        print(f"Current Wi-Fi Status: {current_status}")

        ssid = "Test_Hotspot"
        password = "TestPassword123"
        network_manager.create_hotspot(ssid, password)
        print(f"Wi-Fi hotspot '{ssid}' created. Please check available Wi-Fi networks.")
        input("Press Enter after verifying the hotspot is visible...")

        network_manager.stop_hotspot()
        print("Hotspot stopped.")

        existing_ssid = input("Enter the SSID of an existing Wi-Fi network to connect: ")
        existing_password = input("Enter the password: ")
        network_manager.connect_to_network(existing_ssid, existing_password)
        print(f"Connecting to Wi-Fi network '{existing_ssid}'...")
        time.sleep(5)

        new_status = network_manager.get_wifi_status()
        print(f"New Wi-Fi Status: {new_status}")
        print("Please confirm the device is connected to the Wi-Fi network.")
        input("Press Enter to continue...")

        print("Wi-Fi Controller Test Completed.\n")
    except Exception as e:
        print(f"Wi-Fi Controller Test Failed: {e}")

def main():
    print("=== Starting System Test ===")
    test_eink_display()
    test_nfc_device()
    test_nvme_storage()
    test_wifi_controller()
    print("=== System Test Completed ===")

if __name__ == "__main__":
    main()
