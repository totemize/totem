"""Public contract for bounded NFC tag reads, writes, and presence polling."""

from __future__ import annotations

import base64
from dataclasses import dataclass

from ..identifiers import CapabilityId, ContractError


NFC_TAG = CapabilityId("nfc.tag", 1)
NFC_MAX_PAYLOAD_BYTES = 4096


def _payload(value: object) -> bytes:
    if not isinstance(value, bytes):
        raise ContractError("nfc payload must be bytes")
    if len(value) > NFC_MAX_PAYLOAD_BYTES:
        raise ContractError("nfc payload exceeds maximum size")
    return value


@dataclass(frozen=True)
class NfcReadResult:
    """A bounded NFC tag value encoded as a JSON-safe base64 object."""

    data: bytes

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", _payload(self.data))

    def to_json_value(self) -> dict[str, object]:
        return {"data_b64": base64.b64encode(self.data).decode("ascii")}


@dataclass(frozen=True)
class NfcWriteRequest:
    """A caller-supplied, bounded tag value decoded before provider dispatch."""

    data: bytes

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", _payload(self.data))

    @classmethod
    def from_json_value(cls, value: object) -> "NfcWriteRequest":
        if not isinstance(value, dict) or set(value) != {"data_b64"}:
            raise ContractError("nfc write request must contain only data_b64")
        encoded = value["data_b64"]
        if not isinstance(encoded, str):
            raise ContractError("nfc data_b64 must be a string")
        try:
            data = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError) as exc:
            raise ContractError("nfc data_b64 is invalid") from exc
        return cls(data)


@dataclass(frozen=True)
class NfcPollResult:
    """The explicit public outcome of a tag presence check."""

    present: bool

    def __post_init__(self) -> None:
        if not isinstance(self.present, bool):
            raise ContractError("nfc present must be boolean")

    def to_json_value(self) -> dict[str, object]:
        return {"present": self.present}
