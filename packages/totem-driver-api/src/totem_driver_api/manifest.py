"""Import-independent public manifest contract for driver distributions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Sequence, Tuple

from .identifiers import API_MAJOR, CapabilityId, ContractError, IncompatibleApiMajor
from .resources import ResourceClaim


MANIFEST_MAJOR = 1


class IncompatibleManifestMajor(ContractError):
    """The package-data manifest format is newer than this runtime supports."""


@dataclass(frozen=True)
class ManifestPredicate:
    """One exact observed-hardware fact required by a provider."""

    fact: str
    equals: str

    def __post_init__(self) -> None:
        if not isinstance(self.fact, str) or not self.fact.strip():
            raise ContractError("manifest predicate fact must be non-empty")
        if not isinstance(self.equals, str) or not self.equals.strip():
            raise ContractError("manifest predicate equals must be non-empty")

    def to_json_value(self) -> dict[str, str]:
        return {"fact": self.fact, "equals": self.equals}

    @classmethod
    def from_json_value(cls, value: object) -> "ManifestPredicate":
        if not isinstance(value, Mapping):
            raise ContractError("manifest predicate must be a JSON object")
        if set(value) != {"fact", "equals"}:
            raise ContractError("manifest predicate has unknown or missing field")
        fact = value.get("fact")
        equals = value.get("equals")
        if not isinstance(fact, str) or not isinstance(equals, str):
            raise ContractError("manifest predicate values must be strings")
        return cls(fact=fact, equals=equals)


@dataclass(frozen=True)
class DriverManifest:
    """Validated provider metadata consumed before a provider module is imported."""

    api_major: int
    provider_id: str
    provider_version: str
    capabilities: tuple[CapabilityId, ...]
    resources: tuple[ResourceClaim, ...]
    manifest_major: int = MANIFEST_MAJOR
    predicates: tuple[ManifestPredicate, ...] = ()
    prerequisites: tuple[str, ...] = ()
    config_schema: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    defaults: Mapping[str, object] = field(default_factory=dict)
    privileges: tuple[str, ...] = ()
    grouping: str = "provider"
    factory: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.manifest_major, bool) or not isinstance(self.manifest_major, int):
            raise ContractError("manifest manifest_major must be an integer")
        if self.manifest_major != MANIFEST_MAJOR:
            raise IncompatibleManifestMajor(
                "manifest major {} is incompatible with host major {}".format(
                    self.manifest_major, MANIFEST_MAJOR
                )
            )
        if isinstance(self.api_major, bool) or not isinstance(self.api_major, int) or self.api_major < 1:
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
        if len(set(self.predicates)) != len(self.predicates):
            raise ContractError("manifest predicates must be unique")
        if any(not isinstance(item, str) or not item.strip() for item in self.prerequisites):
            raise ContractError("manifest prerequisites must be non-empty strings")
        if any(not isinstance(item, str) or not item.strip() for item in self.privileges):
            raise ContractError("manifest privileges must be non-empty strings")
        if self.grouping not in {"provider", "binding"}:
            raise ContractError("manifest grouping must be provider or binding")
        if self.factory and (
            self.factory.count(":") != 1
            or not all(part.strip() for part in self.factory.split(":", 1))
        ):
            raise ContractError("manifest factory must be package.module:factory")
        schema = _freeze_schema(self.config_schema)
        defaults = _freeze_mapping(self.defaults)
        unknown_defaults = set(defaults).difference(schema)
        if unknown_defaults:
            raise ContractError(
                "manifest defaults has unknown field {}".format(sorted(unknown_defaults)[0])
            )
        if any(rule["type"] == "secret-reference" for rule in (schema[name] for name in defaults)):
            raise ContractError("manifest defaults cannot contain secret references or values")
        object.__setattr__(self, "config_schema", schema)
        object.__setattr__(self, "defaults", defaults)

    def require_api_major(self, expected_major: int = API_MAJOR) -> None:
        if self.api_major != expected_major:
            raise IncompatibleApiMajor(
                "provider API major {} is incompatible with host major {}".format(
                    self.api_major, expected_major
                )
            )

    def to_json_value(self) -> dict[str, object]:
        return {
            "manifest_major": self.manifest_major,
            "api_major": self.api_major,
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "capabilities": [capability.identifier for capability in self.capabilities],
            "resources": [resource.to_json_value() for resource in self.resources],
            "predicates": [predicate.to_json_value() for predicate in self.predicates],
            "prerequisites": list(self.prerequisites),
            "config_schema": _thaw(self.config_schema),
            "defaults": _thaw(self.defaults),
            "privileges": list(self.privileges),
            "grouping": self.grouping,
            "factory": self.factory,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_json_value(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, value: Mapping[str, object]) -> "DriverManifest":
        if not isinstance(value, Mapping):
            raise ContractError("manifest must be a JSON object")
        allowed = {
            "manifest_major", "api_major", "provider_id", "provider_version", "capabilities",
            "predicates", "prerequisites", "config_schema", "defaults", "resources",
            "privileges", "grouping", "factory",
        }
        unknown = set(value).difference(allowed)
        if unknown:
            raise ContractError("manifest has unknown field {}".format(sorted(unknown)[0]))
        api_major = value.get("api_major")
        provider_id = value.get("provider_id")
        provider_version = value.get("provider_version")
        capabilities = value.get("capabilities")
        resources = value.get("resources", ())
        manifest_major = value.get("manifest_major", MANIFEST_MAJOR)
        predicates = value.get("predicates", ())
        prerequisites = value.get("prerequisites", ())
        config_schema = value.get("config_schema", {})
        defaults = value.get("defaults", {})
        privileges = value.get("privileges", ())
        grouping = value.get("grouping", "provider")
        factory = value.get("factory", "")
        if isinstance(api_major, bool) or not isinstance(api_major, int):
            raise ContractError("manifest api_major must be an integer")
        if not isinstance(provider_id, str) or not isinstance(provider_version, str):
            raise ContractError("manifest provider identity fields must be strings")
        if not isinstance(capabilities, Sequence) or isinstance(capabilities, (str, bytes)):
            raise ContractError("manifest capabilities must be a JSON array")
        if not isinstance(resources, Sequence) or isinstance(resources, (str, bytes)):
            raise ContractError("manifest resources must be a JSON array")
        for name, sequence in (("predicates", predicates), ("prerequisites", prerequisites), ("privileges", privileges)):
            if not isinstance(sequence, Sequence) or isinstance(sequence, (str, bytes)):
                raise ContractError("manifest {} must be a JSON array".format(name))
        if not isinstance(config_schema, Mapping) or not isinstance(defaults, Mapping):
            raise ContractError("manifest config_schema and defaults must be JSON objects")
        if not isinstance(grouping, str) or not isinstance(factory, str):
            raise ContractError("manifest grouping and factory must be strings")
        return cls(
            manifest_major=manifest_major,
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
            predicates=tuple(ManifestPredicate.from_json_value(predicate) for predicate in predicates),
            prerequisites=tuple(prerequisites),
            config_schema=config_schema,
            defaults=defaults,
            privileges=tuple(privileges),
            grouping=grouping,
            factory=factory,
        )


def _freeze_schema(value: Mapping[str, Mapping[str, object]]) -> Mapping[str, Mapping[str, object]]:
    if not isinstance(value, Mapping):
        raise ContractError("manifest config_schema must be a JSON object")
    frozen = {}
    for field_name, rule in value.items():
        if not isinstance(field_name, str) or not field_name.strip() or not isinstance(rule, Mapping):
            raise ContractError("manifest config_schema fields must map to JSON objects")
        rule_type = rule.get("type")
        if rule_type not in {"string", "integer", "boolean", "secret-reference"}:
            raise ContractError("manifest config_schema {} has invalid type".format(field_name))
        allowed = {"type", "enum", "minimum"}
        unknown = set(rule).difference(allowed)
        if unknown:
            raise ContractError("manifest config_schema {} has unknown rule".format(field_name))
        frozen[field_name] = MappingProxyType(dict(rule))
    return MappingProxyType(frozen)


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("manifest defaults must be a JSON object")
    return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})


def _freeze_json(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_freeze_json(item) for item in value)
    raise ContractError("manifest values must be JSON-compatible")


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
