"""Lease-gated, independently hosted Wi-Fi provider composition."""

from __future__ import annotations

from enum import Enum
from typing import Callable, Iterable, Mapping, Optional, Tuple

from totem_driver_api import ResourceClaim
from totem_driver_api.capabilities.radio.wifi import (
    WifiConnectResult,
    WifiDisconnectResult,
    WifiHotspotResult,
    WifiNetwork,
    WifiScanResult,
)

from totem.hardware.builtin.radio.models import RadioService
from totem.hardware.capabilities.radio.shared import RadioConstraint
from totem.hardware.builtin.bootstrap import BuiltinBootstrap


_SERVICE_CLAIM = ("dbus", RadioService.NETWORK_MANAGER.destination.casefold())


class WiFiSelectionError(ValueError):
    """Wi-Fi selection was invalid before a provider backend was invoked."""


class WiFiProviderState(Enum):
    READY = "ready"
    RUNNING = "running"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class WiFiProvider:
    """Compose one validated Wi-Fi session without owning another radio provider.

    A resolver/broker owns admission and coexistence. This class accepts only
    granted service, interface, and PHY facts, then lazily imports its selected
    implementation after catalog resolution. A request cannot select a different
    interface or make catalog scanning import NetworkManager code.
    """

    def __init__(
        self,
        *,
        interface: Optional[str] = None,
        phy: Optional[str] = None,
        claims: Iterable[ResourceClaim] = (),
        runtime: object = None,
        driver: object = None,
        driver_factory: Optional[Callable[[], object]] = None,
        explicit_mock: bool = False,
        compatibility_group: str = "wifi",
        maximum_failures: int = 5,
    ) -> None:
        self.interface = self._required_text(interface, "interface")
        self.phy = self._required_text(phy, "phy")
        self._claims: Tuple[ResourceClaim, ...] = tuple(claims)
        self._runtime = runtime
        self._driver = driver
        self._driver_factory = driver_factory
        self._explicit_mock = explicit_mock
        self._compatibility_group = self._required_text(compatibility_group, "compatibility group")
        if not isinstance(maximum_failures, int) or maximum_failures < 1:
            raise ValueError("maximum failures must be a positive integer")
        self._maximum_failures = maximum_failures
        self._state = WiFiProviderState.READY
        self._failures = 0

    @staticmethod
    def _required_text(value: object, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise WiFiSelectionError("wifi {} is not declared".format(field))
        return value.strip()

    @property
    def state(self) -> WiFiProviderState:
        return self._state

    def radio_constraint(self, mode: str) -> RadioConstraint:
        """Expose data-only shared-PHY policy facts; it never acquires a lease."""

        return RadioConstraint(
            phy=self.phy,
            interface=self.interface,
            adapter=self.interface,
            mode=mode,
            compatibility_group=self._compatibility_group,
        )

    def session(self) -> object:
        """Return a selected session only after validating broker-granted facts."""

        self._validate_claims()
        if self._state is WiFiProviderState.QUARANTINED:
            raise WiFiSelectionError("wifi provider is quarantined")
        if self._driver is None:
            self._driver = self._compose_driver()
        return self._driver

    def start(self) -> object:
        """Initialize only this provider's selected session."""

        session = self.session()
        initializer = getattr(session, "init", None)
        if not callable(initializer):
            raise WiFiSelectionError("wifi driver does not provide initialization")
        try:
            initializer()
        except Exception:
            self._record_failure()
            raise
        self._state = WiFiProviderState.RUNNING
        return session

    def validate_startup(self) -> None:
        self.start()

    def scan(self) -> WifiScanResult:
        """Expose a selected session's scan through the narrow public contract."""

        networks = self._ready_session().scan_networks()
        return WifiScanResult(
            tuple(
                WifiNetwork(
                    ssid=item.ssid,
                    signal_dbm=int(item.signal_percent),
                    secure=bool(item.security),
                )
                for item in networks
            )
        )

    def connect(self, ssid: str, password: str = "") -> WifiConnectResult:
        session = self._ready_session()
        session.connect(ssid, password)
        return WifiConnectResult(True, ssid)

    def disconnect(self) -> WifiDisconnectResult:
        self._ready_session().disconnect()
        return WifiDisconnectResult(True)

    def create_hotspot(self, ssid: str, password: str = "") -> WifiHotspotResult:
        self._ready_session().create_hotspot(ssid, password)
        return WifiHotspotResult(True)

    def _ready_session(self) -> object:
        session = self.session()
        if not getattr(session, "initialized", False):
            initializer = getattr(session, "init", None)
            if not callable(initializer):
                raise WiFiSelectionError("wifi driver does not provide initialization")
            initializer()
        return session

    def restart(self) -> object:
        """Discard and recreate only this provider's session after a local failure."""

        if self._state is WiFiProviderState.QUARANTINED:
            raise WiFiSelectionError("wifi provider is quarantined")
        previous = self._driver
        self._driver = None
        if previous is not None:
            closer = getattr(previous, "close", None)
            if callable(closer):
                closer()
        self._state = WiFiProviderState.READY
        return self.start()

    def _record_failure(self) -> None:
        self._failures += 1
        self._state = (
            WiFiProviderState.QUARANTINED
            if self._failures >= self._maximum_failures
            else WiFiProviderState.FAILED
        )

    def _validate_claims(self) -> None:
        claims = {
            (claim.kind.strip().casefold(), claim.identifier.strip().casefold())
            for claim in self._claims
        }
        expected = {
            _SERVICE_CLAIM,
            ("interface", self.interface.casefold()),
            ("phy", self.phy.casefold()),
        }
        if not expected.issubset(claims):
            raise WiFiSelectionError("wifi resource claims are incomplete")

    def _compose_driver(self) -> object:
        if self._driver_factory is not None:
            return self._driver_factory()
        if self._explicit_mock:
            from .drivers.mock_wifi import Driver

            return Driver()
        from .drivers.network_manager_wifi import NetworkManagerWiFiDriver

        return NetworkManagerWiFiDriver(self.interface, runtime=self._runtime)

    def dispatch(
        self,
        message: Mapping[str, object],
        _attachments: Mapping[str, object],
        _context: Mapping[str, object],
    ) -> dict[str, object]:
        """Versioned Wi-Fi SPI; the generic worker never knows these types."""

        message_type = message.get("type")
        try:
            if message_type == "wifi.connection.scan":
                return {"ok": True, "scan": self.scan().to_json_value()}
            if message_type == "wifi.connection.connect":
                ssid = message.get("ssid")
                password = message.get("password", "")
                return {"ok": True, "connection": self.connect(ssid, password).to_json_value()}
            if message_type == "wifi.connection.disconnect":
                return {"ok": True, "disconnect": self.disconnect().to_json_value()}
            if message_type == "wifi.connection.hotspot":
                ssid = message.get("ssid")
                password = message.get("password", "")
                return {"ok": True, "hotspot": self.create_hotspot(ssid, password).to_json_value()}
        except (TypeError, ValueError):
            return {"ok": False, "error": {"code": "invalid_request"}}
        return {"ok": False, "error": {"code": "unknown_type"}}


def create_provider(bootstrap: object = None) -> WiFiProvider:
    """Return a side-effect-free product; composition injects facts and leases later."""

    selected = BuiltinBootstrap.parse(bootstrap)
    if selected.capability_id != "wifi.connection@1":
        raise WiFiSelectionError("wifi bootstrap capability is invalid")
    settings = selected.settings
    return WiFiProvider(
        interface=settings.get("interface"), phy=settings.get("phy"), claims=selected.claims,
        compatibility_group=settings.get("compatibility_group", "wifi"),
        explicit_mock=settings.get("explicit_mock", False) is True,
    )
