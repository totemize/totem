"""Bounded, payload-blind LE L2CAP CoC socket ownership.

This module owns only channel lifecycle.  It never reads or writes channel
payloads; a connected descriptor is transferred to FIPS with SCM_RIGHTS so
FIPS remains responsible for framing, identity, Noise, and routing.
"""

from array import array
from dataclasses import replace
from datetime import datetime, timezone
import json
import socket
import struct
import threading
from typing import Any, Callable, Dict, Optional
import uuid

from totem.devices.network.errors import (
    InvalidRadioRequestError,
    RadioConflictError,
    RadioOperationError,
    RadioResourceNotFoundError,
    RadioTimeoutError,
)
from totem.devices.network.models import L2CAPConnection, L2CAPListener


LE_PUBLIC = getattr(socket, "BDADDR_LE_PUBLIC", 0x01)
LE_RANDOM = getattr(socket, "BDADDR_LE_RANDOM", 0x02)
AF_BLUETOOTH = getattr(socket, "AF_BLUETOOTH", 31)
BTPROTO_L2CAP = getattr(socket, "BTPROTO_L2CAP", 0)
SOL_BLUETOOTH = getattr(socket, "SOL_BLUETOOTH", 274)
BT_RCVMTU = getattr(socket, "BT_RCVMTU", 13)
ADDRESS_TYPES = {"public": LE_PUBLIC, "random": LE_RANDOM}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class L2CAPTransport:
    """Own a bounded set of Linux LE CoC listeners and connections."""

    def __init__(
        self,
        *,
        socket_factory: Callable[..., Any] = socket.socket,
        maximum_listeners: int = 4,
        maximum_connections: int = 16,
        accepted_callback: Optional[Callable[[L2CAPConnection], None]] = None,
    ):
        self._socket_factory = socket_factory
        self.maximum_listeners = maximum_listeners
        self.maximum_connections = maximum_connections
        self._accepted_callback = accepted_callback
        self._listeners: Dict[str, Dict[str, Any]] = {}
        self._connections: Dict[str, Dict[str, Any]] = {}
        self._pending_listeners = 0
        self._pending_connections = 0
        self._lock = threading.RLock()
        self._closed = False

    @staticmethod
    def _validate(psm: int, mtu: int, address_type: str) -> None:
        if not 0 <= psm <= 0x00FF:
            raise InvalidRadioRequestError("LE L2CAP PSM must be between 0 and 255")
        if not 23 <= mtu <= 65535:
            raise InvalidRadioRequestError("LE L2CAP MTU must be between 23 and 65535")
        if address_type not in ADDRESS_TYPES:
            raise InvalidRadioRequestError(
                "LE Bluetooth address type must be public or random"
            )

    def _new_socket(self):
        try:
            return self._socket_factory(
                AF_BLUETOOTH, socket.SOCK_SEQPACKET, BTPROTO_L2CAP
            )
        except (AttributeError, OSError) as exc:
            raise RadioOperationError(
                "Could not open an LE L2CAP socket: {}".format(exc)
            )

    @staticmethod
    def _address(address: str, psm: int, address_type: str):
        return (address, psm, 0, ADDRESS_TYPES[address_type])

    @staticmethod
    def _set_receive_mtu(channel: Any, mtu: int) -> None:
        try:
            channel.setsockopt(SOL_BLUETOOTH, BT_RCVMTU, struct.pack("H", mtu))
        except OSError as exc:
            raise RadioOperationError(
                "Could not set the LE L2CAP receive MTU: {}".format(exc)
            )

    def create_listener(
        self,
        *,
        local_address: str,
        service_uuid: str,
        psm: int = 0,
        mtu: int = 1024,
        address_type: str = "public",
    ) -> L2CAPListener:
        self._validate(psm, mtu, address_type)
        with self._lock:
            if self._closed:
                raise RadioOperationError("LE L2CAP transport is closed")
            if len(self._listeners) + self._pending_listeners >= self.maximum_listeners:
                raise RadioConflictError("LE L2CAP listener limit reached")
            self._pending_listeners += 1
        try:
            channel = self._new_socket()
        except Exception:
            with self._lock:
                self._pending_listeners -= 1
            raise
        listener_id = uuid.uuid4().hex
        stop = threading.Event()
        try:
            self._set_receive_mtu(channel, mtu)
            channel.settimeout(0.5)
            channel.bind(self._address(local_address, psm, address_type))
            channel.listen(1)
            assigned = channel.getsockname()
            assigned_psm = int(assigned[1])
        except RadioOperationError:
            with self._lock:
                self._pending_listeners -= 1
            channel.close()
            raise
        except OSError as exc:
            with self._lock:
                self._pending_listeners -= 1
            channel.close()
            raise RadioOperationError(
                "Could not listen on an LE L2CAP channel: {}".format(exc)
            )
        model = L2CAPListener(
            id=listener_id,
            local_address=local_address,
            address_type=address_type,
            psm=assigned_psm,
            mtu=mtu,
            service_uuid=service_uuid,
            advertisement_id=None,
            listening=True,
        )
        thread = threading.Thread(
            target=self._accept_loop,
            args=(listener_id,),
            name="totem-l2cap-{}".format(listener_id[:8]),
            daemon=True,
        )
        with self._lock:
            self._pending_listeners -= 1
            if self._closed:
                channel.close()
                raise RadioOperationError("LE L2CAP transport is closed")
            self._listeners[listener_id] = {
                "model": model,
                "socket": channel,
                "stop": stop,
                "thread": thread,
            }
        thread.start()
        return model

    def set_listener_advertisement(
        self, listener_id: str, advertisement_id: str
    ) -> L2CAPListener:
        with self._lock:
            entry = self._listeners.get(listener_id)
            if entry is None:
                raise RadioResourceNotFoundError("LE L2CAP listener was not found")
            model = replace(entry["model"], advertisement_id=advertisement_id)
            entry["model"] = model
            return model

    def _accept_loop(self, listener_id: str) -> None:
        while True:
            with self._lock:
                entry = self._listeners.get(listener_id)
                if entry is None or entry["stop"].is_set():
                    return
                channel = entry["socket"]
                listener = entry["model"]
            try:
                connected, peer = channel.accept()
            except (TimeoutError, socket.timeout):
                continue
            except OSError:
                return
            with self._lock:
                if (
                    len(self._connections) + self._pending_connections
                    >= self.maximum_connections
                ):
                    connected.close()
                    continue
                connection_id = uuid.uuid4().hex
                peer_address = str(peer[0]) if peer else ""
                model = L2CAPConnection(
                    id=connection_id,
                    listener_id=listener_id,
                    peer_address=peer_address,
                    address_type=listener.address_type,
                    psm=listener.psm,
                    mtu=listener.mtu,
                    connected_at=_utc_now(),
                )
                self._connections[connection_id] = {
                    "model": model,
                    "socket": connected,
                }
            if self._accepted_callback:
                self._accepted_callback(model)

    def connect(
        self,
        *,
        peer_address: str,
        psm: int,
        mtu: int = 1024,
        address_type: str = "public",
        timeout: float = 15.0,
    ) -> L2CAPConnection:
        self._validate(psm, mtu, address_type)
        if psm == 0:
            raise InvalidRadioRequestError("A peer LE L2CAP PSM is required")
        with self._lock:
            if self._closed:
                raise RadioOperationError("LE L2CAP transport is closed")
            if (
                len(self._connections) + self._pending_connections
                >= self.maximum_connections
            ):
                raise RadioConflictError("LE L2CAP connection limit reached")
            self._pending_connections += 1
        try:
            channel = self._new_socket()
        except Exception:
            with self._lock:
                self._pending_connections -= 1
            raise
        try:
            self._set_receive_mtu(channel, mtu)
            channel.settimeout(timeout)
            channel.connect(self._address(peer_address, psm, address_type))
            channel.settimeout(None)
        except RadioOperationError:
            with self._lock:
                self._pending_connections -= 1
            channel.close()
            raise
        except (TimeoutError, socket.timeout) as exc:
            with self._lock:
                self._pending_connections -= 1
            channel.close()
            raise RadioTimeoutError("LE L2CAP connection timed out") from exc
        except OSError as exc:
            with self._lock:
                self._pending_connections -= 1
            channel.close()
            raise RadioOperationError(
                "Could not connect an LE L2CAP channel: {}".format(exc)
            )
        connection_id = uuid.uuid4().hex
        model = L2CAPConnection(
            id=connection_id,
            listener_id=None,
            peer_address=peer_address,
            address_type=address_type,
            psm=psm,
            mtu=mtu,
            connected_at=_utc_now(),
        )
        with self._lock:
            self._pending_connections -= 1
            if self._closed:
                channel.close()
                raise RadioOperationError("LE L2CAP transport is closed")
            self._connections[connection_id] = {"model": model, "socket": channel}
        return model

    def list_listeners(self):
        with self._lock:
            return [entry["model"] for entry in self._listeners.values()]

    def list_connections(self):
        with self._lock:
            return [entry["model"] for entry in self._connections.values()]

    def close_listener(self, listener_id: str) -> Optional[str]:
        with self._lock:
            entry = self._listeners.pop(listener_id, None)
        if entry is None:
            return None
        entry["stop"].set()
        entry["socket"].close()
        if entry["thread"] is not threading.current_thread():
            entry["thread"].join(timeout=1.0)
        return entry["model"].advertisement_id

    def close_connection(self, connection_id: str) -> None:
        with self._lock:
            entry = self._connections.pop(connection_id, None)
        if entry is not None:
            entry["socket"].close()

    def handoff(
        self,
        connection_id: str,
        receiver: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            entry = self._connections.get(connection_id)
            if entry is None:
                raise RadioResourceNotFoundError("LE L2CAP connection was not found")
            model = entry["model"]
            message = {
                "protocol": "fips-l2cap-v1",
                "connection": {
                    "id": model.id,
                    "peer_address": model.peer_address,
                    "address_type": model.address_type,
                    "psm": model.psm,
                    "mtu": model.mtu,
                },
            }
            if metadata:
                message["metadata"] = metadata
            descriptors = array("i", [entry["socket"].fileno()])
            try:
                receiver.sendmsg(
                    [json.dumps(message, sort_keys=True).encode("utf-8")],
                    [(socket.SOL_SOCKET, socket.SCM_RIGHTS, descriptors)],
                )
            except OSError as exc:
                raise RadioOperationError(
                    "Could not hand LE L2CAP channel to FIPS: {}".format(exc)
                )
            self.close_connection(connection_id)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            listener_ids = list(self._listeners)
            connection_ids = list(self._connections)
        for listener_id in listener_ids:
            self.close_listener(listener_id)
        for connection_id in connection_ids:
            self.close_connection(connection_id)
