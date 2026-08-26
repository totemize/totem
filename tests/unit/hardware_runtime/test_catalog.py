"""Complete manifest validation before provider import or resource claims."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from totem.hardware.catalog.manifests import ManifestReadError, manifest_from_document


pytestmark = pytest.mark.unit


def _document() -> dict[str, object]:
    return {
        "manifest_major": 1,
        "api_major": 1,
        "provider_id": "fixture.display",
        "provider_version": "1.0.0",
        "capabilities": ["display.frame-sink@1"],
        "predicates": [{"fact": "resource.spi", "equals": "spi0.0"}],
        "prerequisites": ["linux"],
        "config_schema": {"host_mode": {"type": "string"}},
        "defaults": {"host_mode": "process"},
        "resources": [
            {
                "kind": "spi",
                "identifier": "spi0.0",
                "exclusive": True,
                "group": "display",
            }
        ],
        "privileges": ["device:spi"],
        "grouping": "provider",
        "factory": "totem_driver_fixture.provider:create_provider",
    }


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda value: value.update({"unexpected": True}), "unknown_manifest_field"),
        (lambda value: value.update({"manifest_major": 2}), "incompatible_manifest_major"),
        (lambda value: value.update({"api_major": 2}), "incompatible_api_major"),
        (lambda value: value.update({"factory": "not-a-factory"}), "invalid_factory"),
    ],
)
def test_invalid_or_incompatible_manifest_is_rejected_with_stable_redacted_diagnostics(
    mutate, code: str
) -> None:
    document = _document()
    mutate(document)
    secret = "never-in-a-diagnostic"
    document["defaults"] = {"credential": secret}

    with pytest.raises(ManifestReadError) as raised:
        manifest_from_document(document, distribution_name="fixture-package", entry_point_name="fixture")

    diagnostic = raised.value.diagnostic
    assert diagnostic.code == code
    assert diagnostic.plugin_id == "fixture.display"
    assert diagnostic.field
    assert secret not in str(diagnostic)
    assert secret not in diagnostic.to_json()
    assert os.environ.get("TOTEM_DRIVER_FIXTURE_IMPORTED") is None


def test_complete_manifest_is_immutable_and_safe_for_concurrent_catalog_readers() -> None:
    manifest = manifest_from_document(
        _document(), distribution_name="fixture-package", entry_point_name="fixture"
    )

    assert manifest.factory == "totem_driver_fixture.provider:create_provider"
    assert manifest.grouping == "provider"
    assert manifest.privileges == ("device:spi",)
    assert manifest.resources[0].group == "display"
    assert manifest.predicates[0].fact == "resource.spi"
    with ThreadPoolExecutor(max_workers=8) as executor:
        serialized = list(executor.map(lambda _item: manifest.to_json(), range(32)))
    assert len(set(serialized)) == 1
    assert json.loads(serialized[0])["factory"] == manifest.factory


def test_manifest_never_accepts_a_secret_value_even_for_secret_reference_schema() -> None:
    document = _document()
    document["config_schema"] = {"credential": {"type": "secret-reference"}}
    document["defaults"] = {"credential": "raw-provider-secret"}

    with pytest.raises(ManifestReadError) as raised:
        manifest_from_document(document, distribution_name="fixture-package", entry_point_name="fixture")

    assert raised.value.diagnostic.code == "invalid_manifest"
    assert "raw-provider-secret" not in raised.value.diagnostic.to_json()
