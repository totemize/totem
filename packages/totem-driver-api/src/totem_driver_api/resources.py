"""Data-only resource declarations a provider asks the host to lease."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from .identifiers import ContractError


@dataclass(frozen=True)
class ResourceClaim:
    """A provider-declared resource key, without any open handle or secret."""

    kind: str
    identifier: str
    exclusive: bool = True
    group: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.kind or not self.kind.strip():
            raise ContractError("resource kind must be non-empty")
        if not self.identifier or not self.identifier.strip():
            raise ContractError("resource identifier must be non-empty")
        if not isinstance(self.exclusive, bool):
            raise ContractError("resource exclusivity must be boolean")
        if self.group is not None and (not isinstance(self.group, str) or not self.group.strip()):
            raise ContractError("resource group must be a non-empty string when supplied")

    def to_json_value(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "identifier": self.identifier,
            "exclusive": self.exclusive,
            **({"group": self.group} if self.group is not None else {}),
        }

    @classmethod
    def from_json_value(cls, value: object) -> "ResourceClaim":
        if not isinstance(value, Mapping):
            raise ContractError("resource claim must be a JSON object")
        unknown = set(value).difference({"kind", "identifier", "exclusive", "group"})
        if unknown:
            raise ContractError("resource claim has unknown field {}".format(sorted(unknown)[0]))
        kind = value.get("kind")
        identifier = value.get("identifier")
        exclusive = value.get("exclusive", True)
        group = value.get("group")
        if not isinstance(kind, str) or not isinstance(identifier, str):
            raise ContractError("resource claim kind and identifier must be strings")
        if group is not None and not isinstance(group, str):
            raise ContractError("resource claim group must be a string")
        return cls(kind=kind, identifier=identifier, exclusive=exclusive, group=group)
