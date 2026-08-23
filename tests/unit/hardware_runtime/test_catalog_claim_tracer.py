"""Installed-driver catalog, resolver, and resource-claim tracer tests."""

from __future__ import annotations

import importlib.metadata as metadata
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from totem.hardware.catalog.metadata import CatalogScanner
from totem.hardware.discovery.facts import HardwareFacts
from totem.hardware.discovery.resolver import ResolutionStatus, Resolver
from totem.hardware.runtime.broker import ClaimConflict, ResourceBroker


pytestmark = pytest.mark.unit


ROOT = Path(__file__).parents[3]
API_PACKAGE = ROOT / "packages" / "totem-driver-api"
FIXTURE_PACKAGE = ROOT / "tests" / "fixtures" / "totem-driver-fixture"


def _build_and_install_fixture(tmp_path: Path) -> Path:
    """Build two independent wheels and make only their metadata discoverable."""

    wheels = tmp_path / "wheels"
    site = tmp_path / "site"
    wheels.mkdir()
    for package in (API_PACKAGE, FIXTURE_PACKAGE):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--wheel-dir",
                str(wheels),
                str(package),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    for wheel in sorted(wheels.glob("*.whl")):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(site),
                str(wheel),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    return site


def _fixture_distribution(site: Path):
    distributions = tuple(metadata.distributions(path=[str(site)]))
    return next(
        distribution
        for distribution in distributions
        if distribution.metadata["Name"] == "totem-driver-fixture"
    )


def _fixture_catalog(site: Path):
    return CatalogScanner(
        distributions=lambda: (_fixture_distribution(site),),
    ).snapshot()


def _fixture_facts() -> HardwareFacts:
    return HardwareFacts.from_mapping({"resource.spi": "spi0.0"})


class _ManifestDistribution:
    """Metadata-only neighboring distribution; it never imports provider code."""

    def __init__(self, fixture, *, name: str, provider_id: str) -> None:
        self.metadata = {"Name": name, "Version": "1.0.0"}
        self.entry_points = fixture.entry_points
        self.files = fixture.files
        self._fixture = fixture
        self._provider_id = provider_id

    def locate_file(self, path):
        text = self._fixture.locate_file(path).read_text(encoding="utf-8")
        return _TextPath(text.replace("fixture.display", self._provider_id))


def test_installed_fixture_catalogs_resolves_and_claims_without_provider_import(
    tmp_path: Path,
) -> None:
    site = _build_and_install_fixture(tmp_path)
    os.environ.pop("TOTEM_DRIVER_FIXTURE_IMPORTED", None)

    catalog = _fixture_catalog(site)
    resolution = Resolver().resolve(
        catalog,
        facts=_fixture_facts(),
        capability_id="display.frame-sink@1",
    )
    claim = ResourceBroker().claim(resolution.require_binding())

    assert len(catalog.records) == 1
    assert catalog.records[0].provider_id == "fixture.display"
    assert resolution.status is ResolutionStatus.RESOLVED
    assert claim.binding.capability_id == "display.frame-sink@1"
    assert claim.binding.binding_id == "fixture.display:display.frame-sink@1"
    assert claim.binding.config == ()
    assert claim.generation == 1
    assert os.environ.get("TOTEM_DRIVER_FIXTURE_IMPORTED") is None


def test_empty_catalog_returns_structured_unavailable_before_provider_import() -> None:
    catalog = CatalogScanner(distributions=lambda: ()).snapshot()

    resolution = Resolver().resolve(
        catalog,
        facts=_fixture_facts(),
        capability_id="display.frame-sink@1",
    )

    assert catalog.records == ()
    assert resolution.status is ResolutionStatus.UNAVAILABLE
    assert resolution.evidence == ("no catalog record declares display.frame-sink@1",)
    assert os.environ.get("TOTEM_DRIVER_FIXTURE_IMPORTED") is None


def test_api_major_mismatch_is_catalog_diagnostic_before_resolution(tmp_path: Path) -> None:
    site = _build_and_install_fixture(tmp_path)
    fixture = _fixture_distribution(site)

    class _IncompatibleDistribution(_ManifestDistribution):
        def locate_file(self, path):
            text = super().locate_file(path).read_text(encoding="utf-8")
            return _TextPath(text.replace('"api_major": 1', '"api_major": 2'))

    catalog = CatalogScanner(
        distributions=lambda: (
            _IncompatibleDistribution(
                fixture,
                name="incompatible-display",
                provider_id="fixture.display",
            ),
        ),
    ).snapshot()

    assert catalog.records == ()
    assert catalog.diagnostics[0].code == "incompatible_api_major"
    assert os.environ.get("TOTEM_DRIVER_FIXTURE_IMPORTED") is None


def test_ambiguous_resolution_and_atomic_conflict_are_structured(tmp_path: Path) -> None:
    site = _build_and_install_fixture(tmp_path)
    fixture = _fixture_distribution(site)
    neighbor = _ManifestDistribution(
        fixture,
        name="neighbor-display",
        provider_id="neighbor.display",
    )
    catalog = CatalogScanner(distributions=lambda: (fixture, neighbor)).snapshot()
    ambiguous = Resolver().resolve(
        catalog,
        facts=_fixture_facts(),
        capability_id="display.frame-sink@1",
    )

    assert ambiguous.status is ResolutionStatus.AMBIGUOUS
    assert len(ambiguous.evidence) == 2

    binding = Resolver().resolve(
        _fixture_catalog(site),
        facts=_fixture_facts(),
        capability_id="display.frame-sink@1",
    ).require_binding()
    broker = ResourceBroker()
    broker.claim(binding)
    with pytest.raises(ClaimConflict, match="spi:spi0.0"):
        broker.claim(binding)
    assert os.environ.get("TOTEM_DRIVER_FIXTURE_IMPORTED") is None


def test_catalog_snapshots_are_ordered_immutable_and_next_start_is_controlled(
    tmp_path: Path,
) -> None:
    site = _build_and_install_fixture(tmp_path)
    fixture = _fixture_distribution(site)
    current = [fixture]
    scanner = CatalogScanner(distributions=lambda: tuple(current))
    startup_snapshot = scanner.snapshot()
    current.append(
        _ManifestDistribution(
            fixture,
            name="later-display",
            provider_id="later.display",
        )
    )

    assert scanner.snapshot() is startup_snapshot
    assert len(startup_snapshot.records) == 1
    next_snapshot = CatalogScanner(distributions=lambda: tuple(current)).snapshot()
    assert len(next_snapshot.records) == 2
    assert next_snapshot.records == tuple(
        sorted(next_snapshot.records, key=lambda item: item.sort_key)
    )
    with pytest.raises(AttributeError):
        startup_snapshot.records += ()  # type: ignore[misc]
    assert os.environ.get("TOTEM_DRIVER_FIXTURE_IMPORTED") is None


def test_concurrent_catalog_scans_deduplicate_and_atomic_claims_share_snapshot(
    tmp_path: Path,
) -> None:
    site = _build_and_install_fixture(tmp_path)
    fixture = _fixture_distribution(site)
    duplicate = _ManifestDistribution(
        fixture,
        name="totem-driver-fixture",
        provider_id="fixture.display",
    )
    scanner = CatalogScanner(distributions=lambda: (fixture, duplicate))

    with ThreadPoolExecutor(max_workers=8) as executor:
        snapshots = list(executor.map(lambda _index: scanner.snapshot(), range(32)))

    snapshot = snapshots[0]
    assert all(item is snapshot for item in snapshots)
    assert len(snapshot.records) == 1
    binding = Resolver().resolve(
        snapshot,
        facts=_fixture_facts(),
        capability_id="display.frame-sink@1",
    ).require_binding()
    broker = ResourceBroker()
    with ThreadPoolExecutor(max_workers=8) as executor:
        claim_results = list(
            executor.map(
                lambda _index: _claim_status(broker, binding),
                range(16),
            )
        )

    assert len({item.to_json() for item in snapshots}) == 1
    assert claim_results.count("claimed") == 1
    assert claim_results.count("conflict") == 15
    assert os.environ.get("TOTEM_DRIVER_FIXTURE_IMPORTED") is None


def _claim_status(broker: ResourceBroker, binding) -> str:
    try:
        broker.claim(binding)
    except ClaimConflict:
        return "conflict"
    return "claimed"


class _TextPath:
    """Minimal package-data path double for an incompatible metadata test."""

    def __init__(self, text: str) -> None:
        self._text = text

    def read_text(self, *, encoding: str) -> str:
        assert encoding == "utf-8"
        return self._text
