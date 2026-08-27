"""Lease-gated, independently hosted Bluetooth provider composition."""

from __future__ import annotations

from enum import Enum
from typing import Callable, Iterable, Mapping, Optional, Tuple

from totem_driver_api import ResourceClaim
from totem_driver_api.capabilities.radio.bluetooth import (
    BluetoothAdvertisementResult,
    BluetoothConnectResult,
    BluetoothDevice,
    BluetoothDiscoveryResult,
)

from totem.hardware.capabilities.radio.shared import RadioConstraint
from totem.hardware.builtin.bootstrap import BuiltinBootstrap


_SERVICE_CLAIM = ("dbus", "org.bluez")


class BluetoothSelectionError(ValueError):
    """Bluetooth selection was invalid before a provider backend was invoked."""


class BluetoothProviderState(Enum):
    READY = "ready"
    RUNNING = "running"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class BluetoothProvider:
    """Compose one validated BlueZ session without owning Wi-Fi state."""

    def __init__(
        self,
        *,
        adapter: Optional[str] = None,
        phy: Optional[str] = None,
        claims: Iterable[ResourceClaim] = (),
        runtime: object = None,
        driver: object = None,
        driver_factory: Optional[Callable[[], object]] = None,
        explicit_mock: bool = False,
        compatibility_group: str = "bluetooth",
        maximum_failures: int = 5,
    ) -> None:
        self.adapter = self._required_text(adapter, "adapter")
        self.phy = self._required_text(phy, "phy")
        self._claims: Tuple[ResourceClaim, ...] = tuple(claims)
        self._runtime = runtime
        self._driver = driver
        self._driver_factory = driver_factory
        self._explicit_mock = explicit_mock
        self._compatibility_group = self._required_text(
            compatibility_group, "compatibility group"
        )
        if not isinstance(maximum_failures, int) or maximum_failures < 1:
            raise ValueError("maximum failures must be a positive integer")
        self._maximum_failures = maximum_failures
        self._state = BluetoothProviderState.READY
        self._failures = 0
        self._advertisement_id: Optional[str] = None

    @staticmethod
    def _required_text(value: object, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise BluetoothSelectionError("bluetooth {} is not declared".format(field))
        return value.strip()

    @property
    def state(self) -> BluetoothProviderState:
        return self._state

    def radio_constraint(self, mode: str) -> RadioConstraint:
        return RadioConstraint(
            phy=self.phy,
            interface=self.adapter,
            adapter=self.adapter,
            mode=mode,
            compatibility_group=self._compatibility_group,
        )

    def session(self) -> object:
        self._validate_claims()
        if self._state is BluetoothProviderState.QUARANTINED:
            raise BluetoothSelectionError("bluetooth provider is quarantined")
        if self._driver is None:
            self._driver = self._compose_driver()
        return self._driver

    def start(self) -> object:
        session = self.session()
        initializer = getattr(session, "init", None)
        if not callable(initializer):
            raise BluetoothSelectionError("bluetooth driver does not provide initialization")
        try:
            initializer()
        except Exception:
            self._record_failure()
            raise
        self._state = BluetoothProviderState.RUNNING
        return session

    def discover(self) -> BluetoothDiscoveryResult:
        session = self._ready_session()
        discovery_id = session.start_discovery(duration_seconds=1)
        try:
            return BluetoothDiscoveryResult(
                tuple(BluetoothDevice(item.address, item.name) for item in session.list_devices())
            )
        finally:
            session.stop_discovery(discovery_id)

    def advertise(self, name: str) -> BluetoothAdvertisementResult:
        advertisement = self._ready_session().register_advertisement({"local_name": name})
        self._advertisement_id = advertisement.id
        return BluetoothAdvertisementResult(True)

    def stop_advertising(self) -> BluetoothAdvertisementResult:
        if self._advertisement_id is not None:
            self._ready_session().unregister_advertisement(self._advertisement_id)
            self._advertisement_id = None
        return BluetoothAdvertisementResult(False)

    def connect(self, address: str) -> BluetoothConnectResult:
        session = self._ready_session()
        normalized = address.upper()
        selected = next((item for item in session.list_devices() if item.address.upper() == normalized), None)
        if selected is None:
            raise BluetoothSelectionError("bluetooth device is not available")
        session.connect_device(selected.id)
        return BluetoothConnectResult(True, selected.address)

    def set_event_callback(self, callback: Callable[[str, dict], None]) -> None:
        setter = getattr(self.session(), "set_event_callback", None)
        if callable(setter):
            setter(callback)

    def _ready_session(self) -> object:
        session = self.session()
        if not getattr(session, "initialized", False):
            self.start()
        return session

    def restart(self) -> object:
        if self._state is BluetoothProviderState.QUARANTINED:
            raise BluetoothSelectionError("bluetooth provider is quarantined")
        previous = self._driver
        self._driver = None
        self._advertisement_id = None
        if previous is not None:
            closer = getattr(previous, "close", None)
            if callable(closer):
                closer()
        self._state = BluetoothProviderState.READY
        return self.start()

    def _record_failure(self) -> None:
        self._failures += 1
        self._state = (
            BluetoothProviderState.QUARANTINED
            if self._failures >= self._maximum_failures
            else BluetoothProviderState.FAILED
        )

    def _validate_claims(self) -> None:
        claims = {
            (claim.kind.strip().casefold(), claim.identifier.strip().casefold())
            for claim in self._claims
        }
        expected = {
            _SERVICE_CLAIM,
            ("interface", self.adapter.casefold()),
            ("phy", self.phy.casefold()),
        }
        if not expected.issubset(claims):
            raise BluetoothSelectionError("bluetooth resource claims are incomplete")

    def _compose_driver(self) -> object:
        if self._driver_factory is not None:
            return self._driver_factory()
        if self._explicit_mock:
            from .drivers.mock_bluetooth import Driver

            return Driver()
        from .drivers.bluez import Driver

        return Driver(runtime=self._runtime)

    def dispatch(
        self,
        message: Mapping[str, object],
        _attachments: Mapping[str, object],
        _context: Mapping[str, object],
    ) -> dict[str, object]:
        """Versioned Bluetooth SPI; action routing belongs to this provider."""

        message_type = message.get("type")
        try:
            if message_type == "bluetooth.session.discover":
                return {"ok": True, "discovery": self.discover().to_json_value()}
            if message_type == "bluetooth.session.advertise":
                return {"ok": True, "advertisement": self.advertise(message.get("name")).to_json_value()}
            if message_type == "bluetooth.session.stop_advertise":
                return {"ok": True, "advertisement": self.stop_advertising().to_json_value()}
            if message_type == "bluetooth.session.connect":
                return {"ok": True, "connection": self.connect(message.get("address")).to_json_value()}
        except (TypeError, ValueError):
            return {"ok": False, "error": {"code": "invalid_request"}}
        return {"ok": False, "error": {"code": "unknown_type"}}


def create_provider(bootstrap: object = None) -> BluetoothProvider:
    """Return a side-effect-free product; composition injects facts and leases later."""

    selected = BuiltinBootstrap.parse(bootstrap)
    if selected.capability_id != "bluetooth.session@1":
        raise BluetoothSelectionError("bluetooth bootstrap capability is invalid")
    settings = selected.settings
    return BluetoothProvider(
        adapter=settings.get("adapter"), phy=settings.get("phy"), claims=selected.claims,
        compatibility_group=settings.get("compatibility_group", "bluetooth"),
        explicit_mock=settings.get("explicit_mock", False) is True,
    )
