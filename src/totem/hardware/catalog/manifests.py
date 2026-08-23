"""Read and validate driver package-data manifests without loading providers."""

from __future__ import annotations

import json
from typing import Any

from totem_driver_api import DriverManifest


MANIFEST_FILENAME = "totem-driver-manifest.json"


class ManifestReadError(ValueError):
    """A distribution cannot supply one valid manifest for its entry point."""


def manifest_for_entry_point(distribution: Any, entry_point: Any) -> DriverManifest:
    """Return the entry point's package-data manifest without ``EntryPoint.load``.

    A manifest is tied to the package named by the entry point value.  Requiring
    one exact package-data path prevents a distribution from selecting an
    unrelated or ambiguous manifest file.
    """

    module = str(entry_point.value).split(":", 1)[0]
    package, separator, _leaf = module.rpartition(".")
    if not separator or not package:
        raise ManifestReadError("entry point must name a module below a package")
    expected_path = "{}/{}".format(package.replace(".", "/"), MANIFEST_FILENAME)
    files = tuple(distribution.files or ())
    matches = tuple(path for path in files if str(path) == expected_path)
    if len(matches) != 1:
        raise ManifestReadError(
            "distribution must contain exactly one manifest at {}".format(expected_path)
        )
    try:
        raw_manifest = distribution.locate_file(matches[0]).read_text(encoding="utf-8")
        document = json.loads(raw_manifest)
    except (OSError, TypeError, ValueError) as exc:
        raise ManifestReadError("manifest is not valid UTF-8 JSON") from exc
    try:
        manifest = DriverManifest.from_json(document)
        manifest.require_api_major()
    except ValueError as exc:
        raise ManifestReadError(str(exc)) from exc
    return manifest

