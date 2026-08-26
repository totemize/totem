"""Stable, dependency-free contracts shared by Totem driver distributions."""

from .identifiers import API_MAJOR, CapabilityId, ContractError, IncompatibleApiMajor
from .lifecycle import BindingState, HealthState, LifecycleEvent
from .manifest import MANIFEST_MAJOR, DriverManifest, IncompatibleManifestMajor, ManifestPredicate
from .messages import LogicalMessage, ResultError
from .resources import ResourceClaim

__all__ = [
    "API_MAJOR",
    "BindingState",
    "CapabilityId",
    "ContractError",
    "DriverManifest",
    "HealthState",
    "IncompatibleManifestMajor",
    "IncompatibleApiMajor",
    "LogicalMessage",
    "LifecycleEvent",
    "MANIFEST_MAJOR",
    "ManifestPredicate",
    "ResourceClaim",
    "ResultError",
]
