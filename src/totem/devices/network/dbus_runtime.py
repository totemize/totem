"""Small persistent system-D-Bus runtime used by the radio drivers."""

import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError
import threading
from typing import Any, Callable, Dict, List, Optional

from totem.devices.network.errors import (
    RadioOperationError,
    RadioTimeoutError,
)


class DBusCallError(RadioOperationError):
    def __init__(self, error_name: str, detail: str):
        self.error_name = error_name
        super().__init__("{}: {}".format(error_name, detail))


def variant_value(value: Any) -> Any:
    """Recursively unwrap dbus-next Variant objects."""

    if hasattr(value, "signature") and hasattr(value, "value"):
        return variant_value(value.value)
    if isinstance(value, dict):
        return {key: variant_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [variant_value(item) for item in value]
    return value


class SystemDBusRuntime:
    """Own one D-Bus client and event loop for the manager's lifetime.

    Keeping one bus name is important: BlueZ discovery sessions,
    advertisements and GATT subscriptions are scoped to the calling client.
    """

    def __init__(self, default_timeout: float = 15.0):
        self.default_timeout = default_timeout
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run, name="totem-radio-dbus", daemon=True
        )
        self._started = threading.Event()
        self._bus = None
        self._closed = False
        self._handlers: List[Callable[[Any], None]] = []
        self._thread.start()
        if not self._started.wait(default_timeout):
            raise RadioTimeoutError("Timed out starting the system D-Bus runtime")
        self._submit(self._connect(), default_timeout)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._started.set()
        self._loop.run_forever()

    async def _connect(self) -> None:
        try:
            from dbus_next.aio import MessageBus
            from dbus_next.constants import BusType
        except ImportError as exc:
            raise RadioOperationError(
                "dbus-next is required for NetworkManager and BlueZ radio primitives"
            ) from exc
        self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        self._bus.add_message_handler(self._dispatch_message)

    def _submit(self, coroutine, timeout: Optional[float] = None):
        if self._closed:
            raise RadioOperationError("System D-Bus runtime is closed")
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout or self.default_timeout)
        except FutureTimeoutError as exc:
            future.cancel()
            raise RadioTimeoutError("D-Bus operation timed out") from exc

    async def _call_async(
        self,
        destination: str,
        path: str,
        interface: str,
        member: str,
        signature: str = "",
        body: Optional[List[Any]] = None,
    ) -> List[Any]:
        from dbus_next import Message
        from dbus_next.constants import MessageType

        reply = await self._bus.call(
            Message(
                destination=destination,
                path=path,
                interface=interface,
                member=member,
                signature=signature,
                body=body or [],
            )
        )
        if reply.message_type == MessageType.ERROR:
            detail = str(reply.body[0]) if reply.body else "D-Bus call failed"
            raise DBusCallError(
                reply.error_name or "org.freedesktop.DBus.Error.Failed", detail
            )
        return [variant_value(item) for item in reply.body]

    def call(
        self,
        destination: str,
        path: str,
        interface: str,
        member: str,
        signature: str = "",
        body: Optional[List[Any]] = None,
        timeout: Optional[float] = None,
    ) -> List[Any]:
        return self._submit(
            self._call_async(destination, path, interface, member, signature, body),
            timeout,
        )

    def get_all(
        self,
        destination: str,
        path: str,
        interface: str,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        result = self.call(
            destination,
            path,
            "org.freedesktop.DBus.Properties",
            "GetAll",
            "s",
            [interface],
            timeout,
        )
        return result[0] if result else {}

    def get_property(
        self,
        destination: str,
        path: str,
        interface: str,
        name: str,
        timeout: Optional[float] = None,
    ) -> Any:
        result = self.call(
            destination,
            path,
            "org.freedesktop.DBus.Properties",
            "Get",
            "ss",
            [interface, name],
            timeout,
        )
        return result[0] if result else None

    def set_property(
        self,
        destination: str,
        path: str,
        interface: str,
        name: str,
        signature: str,
        value: Any,
        timeout: Optional[float] = None,
    ) -> None:
        from dbus_next import Variant

        self.call(
            destination,
            path,
            "org.freedesktop.DBus.Properties",
            "Set",
            "ssv",
            [interface, name, Variant(signature, value)],
            timeout,
        )

    def add_message_handler(self, handler: Callable[[Any], None]) -> None:
        self._handlers.append(handler)

    def remove_message_handler(self, handler: Callable[[Any], None]) -> None:
        if handler in self._handlers:
            self._handlers.remove(handler)

    def _dispatch_message(self, message) -> None:
        for handler in tuple(self._handlers):
            try:
                handler(message)
            except Exception:
                # A consumer callback must not take down dbus-next's reader task.
                continue

    def schedule(self, coroutine) -> None:
        if not self._closed:
            asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    def export(
        self, path: str, interface: Any, timeout: Optional[float] = None
    ) -> None:
        async def perform():
            self._bus.export(path, interface)

        self._submit(perform(), timeout)

    def unexport(
        self, path: str, interface: Any = None, timeout: Optional[float] = None
    ) -> None:
        async def perform():
            self._bus.unexport(path, interface)

        self._submit(perform(), timeout)

    def close(self) -> None:
        if self._closed:
            return

        async def disconnect():
            if self._bus is not None:
                self._bus.disconnect()

        try:
            self._submit(disconnect(), self.default_timeout)
        finally:
            self._closed = True
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=self.default_timeout)
