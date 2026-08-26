"""Atomic, generation-scoped resource ownership for resolved bindings."""

from __future__ import annotations

from dataclasses import dataclass, field
from hmac import compare_digest
from posixpath import normpath
from secrets import token_urlsafe
from threading import Lock
from typing import Dict, Iterable, List, Tuple

from totem_driver_api import ResourceClaim

from .bindings import BindingRecord


_CASEFOLDED_KINDS = frozenset(
    {
        "adapter",
        "block",
        "compatibility",
        "gpio",
        "i2c",
        "interface",
        "phy",
        "spi",
    }
)
_PATH_KINDS = frozenset({"path", "socket"})


@dataclass(frozen=True, order=True)
class ResourceKey:
    """A normalized physical or system resource identity.

    Credential identifiers deliberately retain their internal identity for
    ownership comparisons while rendering only a redacted marker to callers.
    """

    kind: str
    identifier: str = field(repr=False)

    @classmethod
    def from_claim(cls, claim: ResourceClaim) -> "ResourceKey":
        kind = claim.kind.strip().casefold()
        identifier = claim.identifier.strip()
        if kind in _CASEFOLDED_KINDS:
            identifier = identifier.casefold()
        elif kind in _PATH_KINDS:
            identifier = normpath(identifier)
        # Credential and D-Bus identifiers are opaque and case-sensitive.

        if kind == "gpio" and identifier.startswith("gpio") and identifier[4:].isdigit():
            identifier = identifier[4:]
        if kind == "i2c":
            for prefix in ("/dev/i2c-", "i2c-"):
                if identifier.startswith(prefix) and identifier[len(prefix) :].isdigit():
                    identifier = identifier[len(prefix) :]
                    break
        return cls(kind=kind, identifier=identifier)

    @property
    def value(self) -> str:
        """Return a stable diagnostic value without leaking credentials."""

        identifier = "<redacted>" if self.kind == "credential" else self.identifier
        return "{}:{}".format(self.kind, identifier)


@dataclass(frozen=True)
class _NormalizedClaim:
    """Broker-only normalized claim metadata, including future radio policy."""

    key: ResourceKey
    exclusive: bool
    compatibility_group: str | None


@dataclass(frozen=True)
class ResourceLease:
    """The sole capability to release one binding generation's resources."""

    binding: BindingRecord | None = field(repr=False)
    binding_id: str
    generation: int
    owner_token: str = field(repr=False)
    claims: Tuple[_NormalizedClaim, ...] = field(repr=False)

    @property
    def compatibility_groups(self) -> Tuple[str, ...]:
        return tuple(
            sorted(
                {
                    claim.compatibility_group
                    for claim in self.claims
                    if claim.compatibility_group is not None
                }
            )
        )

    @property
    def resources(self) -> Tuple[str, ...]:
        return tuple(claim.key.value for claim in self.claims)


class ResourceConflict(RuntimeError):
    """A transaction conflicts with a current resource owner."""

    def __init__(
        self,
        resource: ResourceKey,
        owner: ResourceLease,
        requesting_binding_id: str,
    ) -> None:
        self.resource = resource
        self.owner = owner
        self.existing_owner = owner
        self.requesting_binding_id = requesting_binding_id
        self.requesting_owner = requesting_binding_id
        super().__init__(
            "resource conflict: {} owned by {} generation {}; requested by {}".format(
                resource.value,
                owner.binding_id,
                owner.generation,
                requesting_binding_id,
            )
        )


class ResourceReleaseError(RuntimeError):
    """A supervisor attempted to release a non-current resource lease."""


# Compatibility names retained while the lifecycle layer is introduced.
ClaimConflict = ResourceConflict
ClaimRecord = ResourceLease


class ResourceBroker:
    """Validate and atomically commit complete resolved binding claim sets."""

    def __init__(self, compatibility_policy: object | None = None) -> None:
        self._lock = Lock()
        self._owners: Dict[ResourceKey, Tuple[Tuple[ResourceLease, _NormalizedClaim], ...]] = {}
        self._leases: Dict[str, ResourceLease] = {}
        self._generations: Dict[str, int] = {}
        self._compatibility_policy = compatibility_policy

    def claim(self, binding: BindingRecord) -> ResourceLease:
        """Compatibility spelling for acquiring one complete binding lease."""

        return self.acquire(binding)

    def acquire(self, binding: BindingRecord) -> ResourceLease:
        """Acquire every normalized claim for one binding, or acquire nothing."""

        return self.acquire_many((binding,))[0]

    def acquire_many(self, bindings: Iterable[BindingRecord]) -> Tuple[ResourceLease, ...]:
        """Atomically acquire every claim in a complete binding-plan segment.

        All conflicts are discovered while holding the broker lock and before
        a generation counter, owner table, or lease map is changed.
        """

        normalized = tuple(self._normalize_binding(binding) for binding in bindings)
        binding_ids = tuple(binding.binding_id for binding, _claims in normalized)
        if len(set(binding_ids)) != len(binding_ids):
            raise ValueError("binding plan declares duplicate binding identifiers")

        with self._lock:
            requested = sorted(
                (
                    (binding.binding_id, claim)
                    for binding, claims in normalized
                    for claim in claims
                ),
                key=lambda item: (item[1].key.kind, item[1].key.identifier, item[0]),
            )
            self._validate_conflicts(requested)
            self._validate_compatibility(tuple(binding for binding, _claims in normalized))
            for binding_id in binding_ids:
                if binding_id in self._leases:
                    raise ResourceReleaseError("binding already owns an active resource lease")

            leases: List[ResourceLease] = []
            for binding, claims in normalized:
                generation = self._generations.get(binding.binding_id, 0) + 1
                lease = ResourceLease(
                    binding=binding,
                    binding_id=binding.binding_id,
                    generation=generation,
                    owner_token=token_urlsafe(32),
                    claims=claims,
                )
                leases.append(lease)

            for lease in leases:
                self._leases[lease.binding_id] = lease
                self._generations[lease.binding_id] = lease.generation
                for claim in lease.claims:
                    owners = self._owners.get(claim.key, ())
                    self._owners[claim.key] = tuple(
                        sorted(owners + ((lease, claim),), key=lambda item: item[0].binding_id)
                    )
            return tuple(leases)

    def _validate_compatibility(self, requested_bindings: Tuple[BindingRecord, ...]) -> None:
        """Apply an optional pure policy before any lease state is mutated."""

        if self._compatibility_policy is None:
            return
        validate = getattr(self._compatibility_policy, "validate", None)
        if not callable(validate):
            raise TypeError("compatibility policy must define validate")
        active_bindings = tuple(
            lease.binding for lease in self._leases.values() if lease.binding is not None
        )
        validate(active_bindings + requested_bindings)

    def release(self, binding_id: str, generation: int, owner_token: str) -> None:
        """Release resources only after the exact owner confirms its generation died."""

        with self._lock:
            lease = self._leases.get(binding_id)
            if lease is None or lease.generation != generation:
                raise ResourceReleaseError("binding generation is not the active resource owner")
            if not compare_digest(lease.owner_token, owner_token):
                raise ResourceReleaseError("resource owner token does not match the active generation")

            for claim in lease.claims:
                owners = self._owners.get(claim.key, ())
                if not any(item[0] is lease for item in owners):
                    raise ResourceReleaseError("active lease no longer owns every claimed resource")

            for claim in lease.claims:
                owners = self._owners[claim.key]
                remaining = tuple(item for item in owners if item[0] is not lease)
                if remaining:
                    self._owners[claim.key] = remaining
                else:
                    del self._owners[claim.key]
            del self._leases[binding_id]

    def snapshot(self) -> Tuple[dict[str, object], ...]:
        """Return deterministic diagnostic state without secrets or owner tokens."""

        with self._lock:
            return tuple(
                {
                    "binding_id": lease.binding_id,
                    "generation": lease.generation,
                    "resources": lease.resources,
                }
                for lease in sorted(self._leases.values(), key=lambda item: (item.binding_id, item.generation))
            )

    def _normalize_binding(self, binding: BindingRecord) -> Tuple[BindingRecord, Tuple[_NormalizedClaim, ...]]:
        claims = tuple(
            sorted(
                (
                    _NormalizedClaim(
                        key=ResourceKey.from_claim(claim),
                        exclusive=claim.exclusive,
                        compatibility_group=claim.group.strip().casefold() if claim.group else None,
                    )
                    for claim in binding.claims
                ),
                key=lambda item: (item.key.kind, item.key.identifier),
            )
        )
        keys = tuple(claim.key for claim in claims)
        if len(set(keys)) != len(keys):
            raise ValueError("binding declares duplicate normalized resource claims")
        return binding, claims

    def _validate_conflicts(self, requested: List[Tuple[str, _NormalizedClaim]]) -> None:
        for binding_id, requested_claim in requested:
            for owner, owner_claim in self._owners.get(requested_claim.key, ()):
                if requested_claim.exclusive or owner_claim.exclusive:
                    raise ResourceConflict(requested_claim.key, owner, binding_id)

        for index, (binding_id, requested_claim) in enumerate(requested):
            for previous_binding_id, previous_claim in requested[:index]:
                if previous_claim.key != requested_claim.key:
                    continue
                if requested_claim.exclusive or previous_claim.exclusive:
                    pending_owner = ResourceLease(
                        binding=None,
                        binding_id=previous_binding_id,
                        generation=self._generations.get(previous_binding_id, 0) + 1,
                        owner_token="",
                        claims=(),
                    )
                    raise ResourceConflict(requested_claim.key, pending_owner, binding_id)
