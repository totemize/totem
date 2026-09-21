"""Child-only, lease-gated provider for built-in NFC capabilities."""

from __future__ import annotations

from typing import Iterable, Mapping, Optional, Protocol, Tuple

from totem_driver_api import ResourceClaim
from totem_driver_api.capabilities.nfc import NfcPollResult, NfcReadResult, NfcWriteRequest

from totem.hardware.builtin.bootstrap import BuiltinBootstrap


_REQUIRED_CLAIMS = frozenset({("nfc", "reader")})
_USB_EVIDENCE = {
    "acr122": ("04e6", "5591"),
    "pn532": ("0483", "5740"),
}


class NfcSelectionError(ValueError):
    """Selection failed before an NFC transport can receive I/O."""


class NfcDriver(Protocol):
    """Narrow legacy-compatible transport contract after evidence and leasing."""

    def init(self) -> None:
        """Initialize the selected transport."""

    def read(self) -> bytes:
        """Read the current tag payload."""

    def write(self, data: bytes) -> None:
        """Write a validated tag payload."""


class NfcProvider:
    """Expose one selected and leased NFC reader through a versioned capability."""

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        usb_vid: Optional[str] = None,
        usb_pid: Optional[str] = None,
        serial_port: Optional[str] = None,
        i2c_address: Optional[str] = None,
        explicit_mock: bool = False,
        claims: Iterable[ResourceClaim] = (),
        driver: Optional[NfcDriver] = None,
    ) -> None:
        self._model = model.strip().casefold() if isinstance(model, str) else None
        self._usb_vid = usb_vid.strip().casefold() if isinstance(usb_vid, str) else None
        self._usb_pid = usb_pid.strip().casefold() if isinstance(usb_pid, str) else None
        self._serial_port = serial_port.strip() if isinstance(serial_port, str) else None
        self._i2c_address = i2c_address.strip().casefold() if isinstance(i2c_address, str) else None
        self._explicit_mock = explicit_mock
        self._claims: Tuple[ResourceClaim, ...] = tuple(claims)
        self._driver = driver
        self._initialized = False

    def read(self) -> NfcReadResult:
        """Read only after deterministic evidence and lease validation."""

        driver = self._require_ready_driver()
        return NfcReadResult(driver.read())

    def write(self, data: bytes) -> None:
        """Validate caller data before allowing any NFC write I/O."""

        request = NfcWriteRequest(data)
        driver = self._require_ready_driver()
        driver.write(request.data)

    def poll(self) -> NfcPollResult:
        """Return tag presence without treating unsupported hardware as mock hardware."""

        driver = self._require_ready_driver()
        poll = getattr(driver, "poll", None)
        return NfcPollResult(bool(poll()) if callable(poll) else True)

    def validate_startup(self) -> None:
        self._require_ready_driver()

    def _require_ready_driver(self) -> NfcDriver:
        self._validate_selection_and_claims()
        if self._driver is None:
            raise NfcSelectionError("nfc driver is unavailable until child composition")
        if not self._initialized:
            self._driver.init()
            self._initialized = True
        return self._driver

    def _validate_selection_and_claims(self) -> None:
        declared_claims = frozenset(
            (claim.kind.strip().casefold(), claim.identifier.strip().casefold())
            for claim in self._claims
        )
        if not _REQUIRED_CLAIMS.issubset(declared_claims):
            raise NfcSelectionError("nfc resource claims are incomplete")
        if self._model == "mock_nfc":
            if self._explicit_mock is not True:
                raise NfcSelectionError("nfc mock selection must be explicit")
            if any((self._usb_vid, self._usb_pid, self._serial_port, self._i2c_address)):
                raise NfcSelectionError("nfc mock evidence must be absent")
            return
        if self._model not in _USB_EVIDENCE:
            raise NfcSelectionError("nfc model is not declared")
        evidence_modes = int(bool(self._usb_vid or self._usb_pid)) + int(bool(self._serial_port)) + int(bool(self._i2c_address))
        if evidence_modes != 1:
            raise NfcSelectionError("nfc evidence is missing or ambiguous")
        if self._usb_vid or self._usb_pid:
            if (self._usb_vid, self._usb_pid) != _USB_EVIDENCE[self._model]:
                raise NfcSelectionError("nfc USB VID/PID does not match selected model")
        elif self._model != "pn532":
            raise NfcSelectionError("nfc serial/I2C evidence is only supported for PN532")

    def dispatch(
        self,
        message: Mapping[str, object],
        _attachments: Mapping[str, object],
        _context: Mapping[str, object],
    ) -> dict[str, object]:
        message_type = message.get("type")
        try:
            if message_type == "nfc.tag.read":
                return {"ok": True, "tag": self.read().to_json_value()}
            if message_type == "nfc.tag.write":
                request = NfcWriteRequest.from_json_value({"data_b64": message.get("data_b64")})
                self.write(request.data)
                return {"ok": True, "accepted": True}
            if message_type == "nfc.tag.poll":
                return {"ok": True, "poll": self.poll().to_json_value()}
        except (TypeError, ValueError):
            return {"ok": False, "error": {"code": "invalid_request"}}
        return {"ok": False, "error": {"code": "unknown_type"}}


def create_provider(bootstrap: object = None) -> NfcProvider:
    """Return a side-effect-free provider product after catalog resolution."""

    selected = BuiltinBootstrap.parse(bootstrap)
    if selected.capability_id != "nfc.tag@1":
        raise NfcSelectionError("nfc bootstrap capability is invalid")
    settings = selected.settings
    model = settings.get("nfc_model")
    if model == "acr122":
        from .drivers.acr122 import Driver
    elif model == "pn532":
        from .drivers.pn532 import Driver
    elif model == "mock_nfc":
        from .drivers.mock_nfc import Driver
    else:
        raise NfcSelectionError("nfc model is not declared")
    return NfcProvider(
        model=model, usb_vid=settings.get("usb_vid"), usb_pid=settings.get("usb_pid"),
        serial_port=settings.get("serial_port"), i2c_address=settings.get("i2c_address"),
        explicit_mock=settings.get("explicit_mock", False) is True,
        claims=selected.claims, driver=Driver(),
    )
