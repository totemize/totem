from managers.network_manager import NetworkManager
import time

def main():
    print("=== Wi-Fi Manager Test ===")
    try:
        network_manager = NetworkManager()
    except RuntimeError as e:
        print(f"Initialization failed: {e}")
        return

    networks = network_manager.scan_networks()
    if networks:
        print("Available Wi-Fi Networks:")
        for idx, network in enumerate(networks, start=1):
            print(f"{idx}. SSID: {network['SSID']}, Signal: {network['Signal']}")
    else:
        print("No Wi-Fi networks found.")

    existing_ssid = input("Enter the SSID of a Wi-Fi network to connect: ")
    existing_password = input("Enter the password: ")
    try:
        network_manager.connect_to_network(existing_ssid, existing_password)
        print(f"Connected to Wi-Fi network '{existing_ssid}'.")
    except Exception as e:
        print(f"Failed to connect to Wi-Fi network '{existing_ssid}': {e}")
        return

    status = network_manager.get_wifi_status()
    print(f"Wi-Fi Status: {status}")

    time.sleep(5)

    hotspot_ssid = "Test_Hotspot"
    hotspot_password = "TestPassword123"
    try:
        network_manager.create_hotspot(hotspot_ssid, hotspot_password)
        print(f"Wi-Fi hotspot '{hotspot_ssid}' created. Please check available Wi-Fi networks.")
    except Exception as e:
        print(f"Failed to create Wi-Fi hotspot: {e}")
        return

    input("Press Enter after verifying the hotspot is visible...")

    try:
        network_manager.stop_hotspot()
        print("Wi-Fi hotspot stopped.")
    except Exception as e:
        print(f"Failed to stop Wi-Fi hotspot: {e}")

    print("Wi-Fi Manager Test Completed.")

if __name__ == "__main__":
    main()
