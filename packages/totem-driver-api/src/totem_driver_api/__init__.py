"""Stable, dependency-free contracts shared by Totem driver distributions."""

from .identifiers import API_MAJOR, CapabilityId, ContractError, IncompatibleApiMajor
from .manifest import MANIFEST_MAJOR, DriverManifest, IncompatibleManifestMajor, ManifestPredicate
from .messages import LogicalMessage, ResultError
from .resources import ResourceClaim

__all__ = [
    "API_MAJOR",
    "CapabilityId",
    "ContractError",
    "DriverManifest",
    "IncompatibleManifestMajor",
    "IncompatibleApiMajor",
    "LogicalMessage",
    "MANIFEST_MAJOR",
    "ManifestPredicate",
    "ResourceClaim",
    "ResultError",
]
