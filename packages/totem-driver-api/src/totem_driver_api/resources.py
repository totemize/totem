"""Data-only resource declarations a provider asks the host to lease."""

from __future__ import annotations

from dataclasses import dataclass

from .identifiers import ContractError


@dataclass(frozen=True)
class ResourceClaim:
    """A provider-declared resource key, without any open handle or secret."""

    kind: str
    identifier: str
    exclusive: bool = True

    def __post_init__(self) -> None:
        if not self.kind or not self.kind.strip():
            raise ContractError("resource kind must be non-empty")
        if not self.identifier or not self.identifier.strip():
            raise ContractError("resource identifier must be non-empty")
        if not isinstance(self.exclusive, bool):
            raise ContractError("resource exclusivity must be boolean")

    def to_json_value(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "identifier": self.identifier,
            "exclusive": self.exclusive,
        }

    @classmethod
    def from_json_value(cls, value: object) -> "ResourceClaim":
        if not isinstance(value, dict):
            raise ContractError("resource claim must be a JSON object")
        kind = value.get("kind")
        identifier = value.get("identifier")
        exclusive = value.get("exclusive", True)
        if not isinstance(kind, str) or not isinstance(identifier, str):
            raise ContractError("resource claim kind and identifier must be strings")
        return cls(kind=kind, identifier=identifier, exclusive=exclusive)
