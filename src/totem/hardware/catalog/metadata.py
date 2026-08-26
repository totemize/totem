"""Immutable catalog snapshots built from installed distribution metadata."""

from __future__ import annotations

import importlib.metadata as metadata
import json
import re
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable, Iterable, Optional, Tuple

from totem_driver_api import DriverManifest

from .diagnostics import CatalogDiagnostic
from .manifests import ManifestReadError, manifest_for_entry_point


DRIVER_ENTRY_POINT_GROUP = "totem.hardware.drivers"
_NORMALIZED_DISTRIBUTION = re.compile(r"[-_.]+")


def _normalize_distribution_name(name: str) -> str:
    return _NORMALIZED_DISTRIBUTION.sub("-", name).lower()


@dataclass(frozen=True)
class CatalogRecord:
    """Validated provider metadata; no field is a loaded provider object."""

    distribution_name: str
    distribution_version: str
    entry_point_name: str
    entry_point_value: str
    manifest: DriverManifest

    @property
    def provider_id(self) -> str:
        return self.manifest.provider_id

    @property
    def sort_key(self) -> Tuple[str, str, str]:
        return (
            _normalize_distribution_name(self.distribution_name),
            self.entry_point_name,
            self.entry_point_value,
        )

    def to_json_value(self) -> dict[str, object]:
        return {
            "distribution_name": self.distribution_name,
            "distribution_version": self.distribution_version,
            "entry_point_name": self.entry_point_name,
            "entry_point_value": self.entry_point_value,
            "manifest": self.manifest.to_json_value(),
        }


@dataclass(frozen=True)
class CatalogSnapshot:
    """One controlled-start, ordered, immutable view of driver metadata."""

    records: Tuple[CatalogRecord, ...]
    diagnostics: Tuple[CatalogDiagnostic, ...]

    def to_json(self) -> str:
        return json.dumps(
            {
                "diagnostics": [item.to_json_value() for item in self.diagnostics],
                "records": [item.to_json_value() for item in self.records],
            },
            separators=(",", ":"),
            sort_keys=True,
        )


class CatalogScanner:
    """Capture one distribution snapshot without loading any entry point."""

    def __init__(
        self,
        distributions: Callable[[], Iterable[Any]] = metadata.distributions,
        entry_point_group: str = DRIVER_ENTRY_POINT_GROUP,
    ) -> None:
        self._distributions = distributions
        self._entry_point_group = entry_point_group
        self._lock = Lock()
        self._snapshot: Optional[CatalogSnapshot] = None

    def snapshot(self) -> CatalogSnapshot:
        """Return the startup snapshot, constructing it once under a lock."""

        if self._snapshot is not None:
            return self._snapshot
        with self._lock:
            if self._snapshot is None:
                self._snapshot = self._scan()
            return self._snapshot

    def _scan(self) -> CatalogSnapshot:
        records: list[CatalogRecord] = []
        diagnostics: list[CatalogDiagnostic] = []
        seen: set[Tuple[str, str, str]] = set()
        for distribution in self._distributions():
            distribution_name = str(distribution.metadata.get("Name", ""))
            distribution_version = str(distribution.metadata.get("Version", ""))
            if not distribution_name:
                continue
            for entry_point in distribution.entry_points:
                if entry_point.group != self._entry_point_group:
                    continue
                identity = (
                    _normalize_distribution_name(distribution_name),
                    entry_point.name,
                    entry_point.value,
                )
                if identity in seen:
                    continue
                seen.add(identity)
                try:
                    manifest = manifest_for_entry_point(distribution, entry_point)
                except ManifestReadError as exc:
                    diagnostic = exc.diagnostic
                    diagnostics.append(
                        CatalogDiagnostic(
                            code=diagnostic.code,
                            distribution_name=diagnostic.distribution_name or distribution_name,
                            entry_point_name=diagnostic.entry_point_name or entry_point.name,
                            plugin_id=diagnostic.plugin_id,
                            binding_id=diagnostic.binding_id,
                            field=diagnostic.field,
                        )
                    )
                    continue
                records.append(
                    CatalogRecord(
                        distribution_name=distribution_name,
                        distribution_version=distribution_version,
                        entry_point_name=entry_point.name,
                        entry_point_value=entry_point.value,
                        manifest=manifest,
                    )
                )
        return CatalogSnapshot(
            records=tuple(sorted(records, key=lambda item: item.sort_key)),
            diagnostics=tuple(sorted(diagnostics, key=lambda item: item.sort_key)),
        )
