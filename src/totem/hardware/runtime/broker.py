"""Small, atomic resource broker for resolved bindings."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Dict, Tuple

from totem_driver_api import ResourceClaim

from .bindings import BindingRecord


class ClaimConflict(RuntimeError):
    """A normalized resource has already been atomically claimed."""


def _resource_key(claim: ResourceClaim) -> str:
    return "{}:{}".format(claim.kind.strip().lower(), claim.identifier.strip().lower())


@dataclass(frozen=True)
class ClaimRecord:
    """The generation-stamped, immutable runtime input for a future host."""

    binding: BindingRecord
    generation: int
    claims: Tuple[ResourceClaim, ...]


class ResourceBroker:
    """Grant all a binding's resources together, or none of them."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._owners: Dict[str, ClaimRecord] = {}
        self._generations: Dict[str, int] = {}

    def claim(self, binding: BindingRecord) -> ClaimRecord:
        """Claim normalized resources atomically and fail closed on conflicts."""

        claims = tuple(sorted(binding.claims, key=_resource_key))
        keys = tuple(_resource_key(claim) for claim in claims)
        if len(set(keys)) != len(keys):
            raise ClaimConflict("binding declares duplicate normalized resource claims")
        with self._lock:
            for key in keys:
                if key in self._owners:
                    raise ClaimConflict("resource claim conflict: {}".format(key))
            generation = self._generations.get(binding.binding_id, 0) + 1
            record = ClaimRecord(
                binding=binding,
                generation=generation,
                claims=claims,
            )
            for key in keys:
                self._owners[key] = record
            self._generations[binding.binding_id] = generation
            return record

    def release(self, record: ClaimRecord) -> None:
        """Release only the exact active generation that owns every resource."""

        keys = tuple(_resource_key(claim) for claim in record.claims)
        with self._lock:
            if any(self._owners.get(key) is not record for key in keys):
                raise ClaimConflict("claim record is not the active resource owner")
            for key in keys:
                del self._owners[key]

