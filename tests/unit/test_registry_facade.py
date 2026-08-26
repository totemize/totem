"""Compatibility tests for the catalog-backed legacy registry facade."""

from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path

import pytest

from totem.devices.registry import (
    DriverLoadError,
    DriverRegistry,
    MockDriverNotAllowedError,
    UnknownDriverError,
)
from totem.hardware.catalog.metadata import CatalogRecord, CatalogSnapshot
from totem_driver_api import DriverManifest


pytestmark = pytest.mark.unit


def _record(provider_id: str = "fixture.display") -> CatalogRecord:
    return CatalogRecord(
        distribution_name="totem-driver-fixture",
        distribution_version="1.0.0",
        entry_point_name="fixture-display",
        entry_point_value="registry_sentinel_provider:create_provider",
        manifest=DriverManifest.from_json(
            {
                "api_major": 1,
                "provider_id": provider_id,
                "provider_version": "1.0.0",
                "capabilities": ["display.frame-sink@1"],
                "resources": [],
            }
        ),
    )


def _registry(*records: CatalogRecord, client: object | None = None) -> DriverRegistry:
    return DriverRegistry(
        catalog=CatalogSnapshot(records=records, diagnostics=()),
        binding_client=client,
    )


def test_catalog_lookup_discovers_an_installed_provider_without_importing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = tmp_path / "registry_sentinel_provider.py"
    provider.write_text(
        "import os\nos.environ['TOTEM_REGISTRY_SENTINEL_IMPORTED'] = 'yes'\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    os.environ.pop("TOTEM_REGISTRY_SENTINEL_IMPORTED", None)

    registry = _registry(_record())

    assert registry.names == ("fixture.display",)
    assert registry.lookup(" FIXTURE.DISPLAY ").capability_id == "display.frame-sink@1"
    assert os.environ.get("TOTEM_REGISTRY_SENTINEL_IMPORTED") is None


def test_load_delegates_only_to_an_existing_runtime_handle() -> None:
    class Runtime:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []
            self.handle_value = object()

        def handle(self, capability_id: str, binding_id: str) -> object:
            self.calls.append((capability_id, binding_id))
            return self.handle_value

    runtime = Runtime()
    registry = _registry(_record(), client=runtime)

    assert registry.load("fixture.display") is runtime.handle_value
    assert runtime.calls == [("display.frame-sink@1", "fixture.display:display.frame-sink@1")]


def test_legacy_errors_remain_actionable_without_provider_loading() -> None:
    registry = _registry()
    with pytest.raises(UnknownDriverError, match="expected one of"):
        registry.lookup("missing")

    handleless_registry = _registry(_record())
    with pytest.raises(DriverLoadError, match="canonical runtime handle"):
        handleless_registry.load("fixture.display")

    mock_registry = _registry(_record("fixture.mock"))
    with pytest.raises(MockDriverNotAllowedError, match="allow_mock=True"):
        mock_registry.load("fixture.mock")


def test_registry_source_has_no_provider_load_or_ownership_surface() -> None:
    source = Path(inspect.getfile(DriverRegistry)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]

    assert "importlib" not in source
    assert all(not module.startswith("totem.hardware.builtin") for module in imports)
    assert not {"init", "close", "claim", "release"}.intersection(
        name.name for name in ast.walk(tree) if isinstance(name, ast.FunctionDef)
    )
