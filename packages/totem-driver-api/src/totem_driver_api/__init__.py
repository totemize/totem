"""Stable, dependency-free contracts shared by Totem driver distributions."""

from .identifiers import API_MAJOR, CapabilityId, ContractError, IncompatibleApiMajor
from .lifecycle import BindingState, HealthState, LifecycleEvent
from .manifest import MANIFEST_MAJOR, DriverManifest, IncompatibleManifestMajor, ManifestPredicate
from .messages import LogicalMessage, ResultError
from .resources import ResourceClaim
from .conformance import ConformanceCase, ConformanceProvider, ConformanceTranscript, FixtureProvider, run_host_conformance

__all__ = [
    "API_MAJOR",
    "BindingState",
    "CapabilityId",
    "ContractError",
    "ConformanceCase",
    "ConformanceProvider",
    "ConformanceTranscript",
    "DriverManifest",
    "FixtureProvider",
    "HealthState",
    "IncompatibleManifestMajor",
    "IncompatibleApiMajor",
    "LogicalMessage",
    "LifecycleEvent",
    "MANIFEST_MAJOR",
    "ManifestPredicate",
    "ResourceClaim",
    "ResultError",
    "run_host_conformance",
]
