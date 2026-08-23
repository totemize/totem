"""Versioned public identifiers for driver capability contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass


API_MAJOR = 1
_CAPABILITY_NAME = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")


class ContractError(ValueError):
    """Raised when a public driver contract is malformed."""


class IncompatibleApiMajor(ContractError):
    """Raised before loading a provider that targets another API major."""


@dataclass(frozen=True)
class CapabilityId:
    """A stable capability name paired with its independently versioned major."""

    name: str
    major: int

    def __post_init__(self) -> None:
        if not _CAPABILITY_NAME.fullmatch(self.name):
            raise ContractError("capability name must be lowercase dotted or dashed text")
        if isinstance(self.major, bool) or self.major < 1:
            raise ContractError("capability major must be a positive integer")

    @property
    def identifier(self) -> str:
        return "{}@{}".format(self.name, self.major)

    @classmethod
    def parse(cls, identifier: str) -> "CapabilityId":
        name, separator, major = identifier.rpartition("@")
        if not separator or not major.isdigit():
            raise ContractError("capability identifier must use name@major")
        return cls(name=name, major=int(major))
