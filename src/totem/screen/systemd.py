"""Minimal systemd readiness notification support."""

import os
import socket
from typing import Optional


class SystemdNotifier:
    def __init__(self, address: Optional[str] = None):
        self.address = (
            address if address is not None else os.environ.get("NOTIFY_SOCKET")
        )

    def ready(self, status: str = "Boot splash rendered") -> bool:
        if not self.address:
            return False
        address = self.address
        if address.startswith("@"):
            address = "\0" + address[1:]
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.connect(address)
            client.sendall("READY=1\nSTATUS={}".format(status).encode("utf-8"))
        return True
