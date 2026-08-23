"""Import-independent public manifest contract for driver distributions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping, Sequence

from .identifiers import API_MAJOR, CapabilityId, ContractError, IncompatibleApiMajor
from .resources import ResourceClaim


@dataclass(frozen=True)
class DriverManifest:
    """Validated provider metadata consumed before a provider module is imported."""

    api_major: int
    provider_id: str
    provider_version: str
    capabilities: tuple[CapabilityId, ...]
    resources: tuple[ResourceClaim, ...]

    def __post_init__(self) -> None:
        if isinstance(self.api_major, bool) or self.api_major < 1:
            raise ContractError("manifest api_major must be a positive integer")
        if not self.provider_id or not self.provider_id.strip():
            raise ContractError("manifest provider_id must be non-empty")
        if not self.provider_version or not self.provider_version.strip():
            raise ContractError("manifest provider_version must be non-empty")
        if not self.capabilities:
            raise ContractError("manifest must declare at least one capability")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ContractError("manifest capabilities must be unique")
        if len(set(self.resources)) != len(self.resources):
            raise ContractError("manifest resource claims must be unique")

    def require_api_major(self, expected_major: int = API_MAJOR) -> None:
        if self.api_major != expected_major:
            raise IncompatibleApiMajor(
                "provider API major {} is incompatible with host major {}".format(
                    self.api_major, expected_major
                )
            )

    def to_json_value(self) -> dict[str, object]:
        return {
            "api_major": self.api_major,
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "capabilities": [capability.identifier for capability in self.capabilities],
            "resources": [resource.to_json_value() for resource in self.resources],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_json_value(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, value: Mapping[str, object]) -> "DriverManifest":
        if not isinstance(value, Mapping):
            raise ContractError("manifest must be a JSON object")
        api_major = value.get("api_major")
        provider_id = value.get("provider_id")
        provider_version = value.get("provider_version")
        capabilities = value.get("capabilities")
        resources = value.get("resources", ())
        if isinstance(api_major, bool) or not isinstance(api_major, int):
            raise ContractError("manifest api_major must be an integer")
        if not isinstance(provider_id, str) or not isinstance(provider_version, str):
            raise ContractError("manifest provider identity fields must be strings")
        if not isinstance(capabilities, Sequence) or isinstance(capabilities, (str, bytes)):
            raise ContractError("manifest capabilities must be a JSON array")
        if not isinstance(resources, Sequence) or isinstance(resources, (str, bytes)):
            raise ContractError("manifest resources must be a JSON array")
        return cls(
            api_major=api_major,
            provider_id=provider_id,
            provider_version=provider_version,
            capabilities=tuple(
                CapabilityId.parse(capability)
                if isinstance(capability, str)
                else (_ for _ in ()).throw(ContractError("capability must be a string"))
                for capability in capabilities
            ),
            resources=tuple(ResourceClaim.from_json_value(resource) for resource in resources),
        )
