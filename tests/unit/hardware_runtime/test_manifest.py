"""Schema-level public manifest contract coverage from the Phase 1 probe ledger."""

from __future__ import annotations

import pytest

from totem.hardware.catalog.manifests import manifest_from_document


pytestmark = pytest.mark.unit


def test_manifest_schema_declares_versioned_selection_and_privilege_contract() -> None:
    manifest = manifest_from_document(
        {
            "manifest_major": 1,
            "api_major": 1,
            "provider_id": "fixture.display",
            "provider_version": "1.0.0",
            "capabilities": ["display.frame-sink@1"],
            "predicates": [{"fact": "resource.spi", "equals": "spi0.0"}],
            "prerequisites": ["linux"],
            "config_schema": {"timeout": {"type": "integer", "minimum": 1}},
            "defaults": {"timeout": 5},
            "resources": [
                {"kind": "spi", "identifier": "spi0.0", "exclusive": True, "group": "display"}
            ],
            "privileges": ["device:spi"],
            "grouping": "provider",
            "factory": "totem_driver_fixture.provider:create_provider",
        },
        distribution_name="fixture-package",
        entry_point_name="fixture",
    )

    assert manifest.manifest_major == 1
    assert manifest.api_major == 1
    assert manifest.capabilities[0].major == 1
    assert manifest.predicates[0].fact == "resource.spi"
    assert manifest.prerequisites == ("linux",)
    assert manifest.defaults["timeout"] == 5
    assert manifest.resources[0].group == "display"
    assert manifest.privileges == ("device:spi",)
    assert manifest.grouping == "provider"
    assert manifest.factory == "totem_driver_fixture.provider:create_provider"
