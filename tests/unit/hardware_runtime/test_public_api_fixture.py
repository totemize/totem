"""Distribution-boundary tests for the public driver API fixture."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[3]
API_PACKAGE = ROOT / "packages" / "totem-driver-api"
FIXTURE_PACKAGE = ROOT / "tests" / "fixtures" / "totem-driver-fixture"


def _build_wheel(package: Path, destination: Path) -> Path:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(destination),
            str(package),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return next(destination.glob("*.whl"))


def _install_wheel(wheel: Path, target: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(target),
            str(wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_public_api_is_import_independent_and_python_39_compatible() -> None:
    """The public contract stays a stdlib-only third-party boundary."""
    api_sources = API_PACKAGE / "src" / "totem_driver_api"
    assert (API_PACKAGE / "pyproject.toml").is_file()

    forbidden_prefixes = ("totem", "fastapi")
    forbidden_parts = {"manager", "managers", "builtin", "driver", "drivers"}
    for source in api_sources.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            imported = ()
            if isinstance(node, ast.Import):
                imported = (alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = (node.module,)
            for name in imported:
                parts = name.split(".")
                assert not name.startswith(forbidden_prefixes)
                assert not forbidden_parts.intersection(parts)

    pyproject = (API_PACKAGE / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.9' in pyproject


def test_wheels_install_separately_include_manifest_and_register_entry_point(
    tmp_path: Path,
) -> None:
    """A provider wheel supplies metadata and code without Totem-core packaging."""
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    api_wheel = _build_wheel(API_PACKAGE, wheels)
    fixture_wheel = _build_wheel(FIXTURE_PACKAGE, wheels)

    with zipfile.ZipFile(fixture_wheel) as archive:
        files = set(archive.namelist())
        assert "totem_driver_fixture/totem-driver-manifest.json" in files
        entry_points = next(name for name in files if name.endswith("entry_points.txt"))
        assert "[totem.hardware.drivers]" in archive.read(entry_points).decode("utf-8")

    site = tmp_path / "site"
    _install_wheel(api_wheel, site)
    _install_wheel(fixture_wheel, site)
    check = """
import importlib.metadata as metadata
import json
import os
from totem_driver_api import API_MAJOR, DriverManifest, IncompatibleApiMajor

assert os.environ.get('TOTEM_DRIVER_FIXTURE_IMPORTED') is None
distribution = metadata.distribution('totem-driver-fixture')
manifest = DriverManifest.from_json(json.loads(
    distribution.read_text('totem_driver_fixture/totem-driver-manifest.json')
))
assert manifest.capabilities[0].identifier == 'display.frame-sink@1'
assert manifest.api_major == API_MAJOR
try:
    manifest.require_api_major(API_MAJOR + 1)
except IncompatibleApiMajor:
    pass
else:
    raise AssertionError('incompatible API major was accepted')
assert os.environ.get('TOTEM_DRIVER_FIXTURE_IMPORTED') is None
"""
    environment = {**os.environ, "PYTHONPATH": str(site)}
    subprocess.run(
        [sys.executable, "-c", check],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_frozen_contract_values_reject_mutation_and_reuse_concurrently() -> None:
    """Catalog snapshots can share contract values safely across callers."""
    from totem_driver_api import CapabilityId, DriverManifest, ResourceClaim
    from totem_driver_api.capabilities.display import FrameSinkRequest

    capability = CapabilityId("display.frame-sink", 1)
    request = FrameSinkRequest(
        attachment_id="frame-1",
        width=250,
        height=122,
        pixel_format="mono1",
    )
    manifest = DriverManifest(
        api_major=1,
        provider_id="fixture.display",
        provider_version="1.0.0",
        capabilities=(capability,),
        resources=(ResourceClaim("spi", "spi0.0"),),
    )

    with pytest.raises(FrozenInstanceError):
        request.width = 1  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        manifest.provider_id = "different.provider"  # type: ignore[misc]

    with ThreadPoolExecutor(max_workers=8) as executor:
        values = list(
            executor.map(
                lambda _index: (manifest.to_json(), request.to_json()), range(64)
            )
        )

    assert len(set(values)) == 1
    assert json.loads(values[0][0])["capabilities"] == ["display.frame-sink@1"]
