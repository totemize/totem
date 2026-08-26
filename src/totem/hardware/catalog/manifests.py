"""Read and validate driver package-data manifests without loading providers."""

from __future__ import annotations

import json
from typing import Any

from totem_driver_api import (
    API_MAJOR,
    ContractError,
    DriverManifest,
    IncompatibleApiMajor,
    IncompatibleManifestMajor,
    MANIFEST_MAJOR,
)

from .diagnostics import CatalogDiagnostic


MANIFEST_FILENAME = "totem-driver-manifest.json"


class ManifestReadError(ValueError):
    """A distribution cannot supply one valid manifest for its entry point."""

    def __init__(self, diagnostic: CatalogDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic.code)


def manifest_for_entry_point(distribution: Any, entry_point: Any) -> DriverManifest:
    """Return the entry point's package-data manifest without ``EntryPoint.load``.

    A manifest is tied to the package named by the entry point value.  Requiring
    one exact package-data path prevents a distribution from selecting an
    unrelated or ambiguous manifest file.
    """

    module = str(entry_point.value).split(":", 1)[0]
    package, separator, _leaf = module.rpartition(".")
    if not separator or not package:
        raise ManifestReadError(CatalogDiagnostic(code="invalid_entry_point"))
    package_path = package.replace(".", "/")
    # A built-in package can expose more than one independently-hosted
    # provider.  Prefer an explicit provider-local manifest when present,
    # otherwise retain the original package-manifest lookup for distributions
    # with a single provider.
    leaf = module.rsplit(".", 1)[-1]
    expected_path = "{}/{}".format(package_path, MANIFEST_FILENAME)
    provider_path = None
    if leaf.endswith("_provider"):
        provider_path = "{}/{}-manifest.json".format(package_path, leaf[:-9])
    files = tuple(distribution.files or ())
    matches = tuple(path for path in files if str(path) == provider_path)
    if not matches:
        matches = tuple(path for path in files if str(path) == expected_path)
    if len(matches) != 1:
        raise ManifestReadError(CatalogDiagnostic(code="missing_manifest"))
    try:
        raw_manifest = distribution.locate_file(matches[0]).read_text(encoding="utf-8")
        document = json.loads(raw_manifest)
    except (OSError, TypeError, ValueError) as exc:
        raise ManifestReadError(CatalogDiagnostic(code="invalid_manifest")) from exc
    return manifest_from_document(
        document,
        distribution_name=str(distribution.metadata.get("Name", "")),
        entry_point_name=str(entry_point.name),
    )


def manifest_from_document(
    document: object, *, distribution_name: str = "", entry_point_name: str = ""
) -> DriverManifest:
    """Validate a parsed package-data document before any provider import."""

    plugin_id = ""
    if isinstance(document, dict) and isinstance(document.get("provider_id"), str):
        plugin_id = document["provider_id"]
    if isinstance(document, dict):
        allowed = {
            "manifest_major", "api_major", "provider_id", "provider_version", "capabilities",
            "predicates", "prerequisites", "config_schema", "defaults", "resources",
            "privileges", "grouping", "factory",
        }
        unknown = set(document).difference(allowed)
        if unknown:
            raise _manifest_error(
                "unknown_manifest_field", plugin_id, distribution_name, entry_point_name, sorted(unknown)[0]
            )
        if document.get("manifest_major", MANIFEST_MAJOR) != MANIFEST_MAJOR:
            raise _manifest_error(
                "incompatible_manifest_major", plugin_id, distribution_name, entry_point_name, "manifest_major"
            )
        if document.get("api_major") != API_MAJOR:
            raise _manifest_error(
                "incompatible_api_major", plugin_id, distribution_name, entry_point_name, "api_major"
            )
    try:
        manifest = DriverManifest.from_json(document)
        manifest.require_api_major()
    except IncompatibleManifestMajor as exc:
        raise _manifest_error(
            "incompatible_manifest_major", plugin_id, distribution_name, entry_point_name, "manifest_major"
        ) from exc
    except IncompatibleApiMajor as exc:
        raise _manifest_error(
            "incompatible_api_major", plugin_id, distribution_name, entry_point_name, "api_major"
        ) from exc
    except ContractError as exc:
        message = str(exc)
        code = "invalid_factory" if "factory" in message else "unknown_manifest_field" if "unknown field" in message else "invalid_manifest"
        field = "factory" if code == "invalid_factory" else "manifest"
        raise _manifest_error(code, plugin_id, distribution_name, entry_point_name, field) from exc
    return manifest


def _manifest_error(
    code: str, plugin_id: str, distribution_name: str, entry_point_name: str, field: str
) -> ManifestReadError:
    return ManifestReadError(
        CatalogDiagnostic(
            code=code,
            distribution_name=distribution_name,
            entry_point_name=entry_point_name,
            plugin_id=plugin_id,
            field=field,
        )
    )
