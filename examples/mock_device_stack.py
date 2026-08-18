"""Exercise every high-level manager without touching host hardware."""

from tempfile import TemporaryDirectory

from totem.managers.display_manager import DisplayManager
from totem.managers.network_manager import NetworkManager
from totem.managers.nfc_manager import NFCManager
from totem.managers.storage_manager import StorageManager


def main() -> None:
    display = DisplayManager("mock_eink", allow_mock=True)
    nfc = NFCManager("mock_nfc", allow_mock=True)
    network = NetworkManager("mock_wifi", allow_mock=True)

    display.display_text("Totem")
    nfc.write_card("nostr-native")
    print("NFC:", nfc.read_card())
    print("Networks:", network.scan_networks())

    with TemporaryDirectory() as storage_root:
        storage = StorageManager("filesystem", storage_root=storage_root)
        storage.write_data("example.bin", b"totem")
        print("Storage:", storage.read_data("example.bin"))


if __name__ == "__main__":
    main()
