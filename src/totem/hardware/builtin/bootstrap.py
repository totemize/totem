"""Validated selected-binding input for built-in child providers.

The parent serialises this value only after catalog resolution and broker
admission.  It is deliberately data-only: factories receive settings, the
claims they are allowed to use, and the numeric descriptor ids inherited by
the child, never an opened parent-side transport.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from totem_driver_api import ResourceClaim


class BootstrapError(ValueError):
    """The child was not started with one valid selected binding."""


@dataclass(frozen=True)
class BuiltinBootstrap:
    binding_id: str
    capability_id: str
    settings: Mapping[str, object]
    claims: Tuple[ResourceClaim, ...]
    descriptor_ids: Tuple[int, ...]

    @classmethod
    def parse(cls, value: object) -> "BuiltinBootstrap":
        if not isinstance(value, Mapping):
            raise BootstrapError("builtin bootstrap must be an object")
        bindings = value.get("bindings")
        descriptors = value.get("descriptors", ())
        if not isinstance(bindings, list) or len(bindings) != 1:
            raise BootstrapError("builtin provider requires one selected binding")
        if not isinstance(descriptors, list) or any(
            isinstance(item, bool) or not isinstance(item, int) or item < 0
            for item in descriptors
        ):
            raise BootstrapError("bootstrap descriptors must be non-negative integers")
        binding = bindings[0]
        if not isinstance(binding, Mapping):
            raise BootstrapError("bootstrap binding must be an object")
        binding_id = binding.get("binding_id")
        capability_id = binding.get("capability_id")
        settings = binding.get("settings")
        raw_claims = binding.get("claims")
        if (
            not isinstance(binding_id, str)
            or not binding_id
            or not isinstance(capability_id, str)
            or not capability_id
            or not isinstance(settings, Mapping)
            or not isinstance(raw_claims, list)
        ):
            raise BootstrapError("bootstrap binding fields are invalid")
        try:
            claims = tuple(ResourceClaim.from_json_value(item) for item in raw_claims)
        except Exception as exc:
            raise BootstrapError("bootstrap claims are invalid") from exc
        return cls(
            binding_id=binding_id,
            capability_id=capability_id,
            settings=dict(settings),
            claims=claims,
            descriptor_ids=tuple(descriptors),
        )
