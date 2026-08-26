"""Safe, immutable diagnostics for metadata and startup configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class CatalogDiagnostic:
    """Actionable rejection evidence that intentionally carries no input values."""

    code: str
    distribution_name: str = ""
    entry_point_name: str = ""
    plugin_id: str = ""
    binding_id: str = ""
    field: str = ""

    @property
    def sort_key(self) -> Tuple[str, str, str, str, str, str]:
        return (
            self.distribution_name,
            self.entry_point_name,
            self.plugin_id,
            self.binding_id,
            self.field,
            self.code,
        )

    def to_json_value(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "code": self.code,
                "distribution_name": self.distribution_name,
                "entry_point_name": self.entry_point_name,
                "plugin_id": self.plugin_id,
                "binding_id": self.binding_id,
                "field": self.field,
            }.items()
            if value
        }

    def to_json(self) -> str:
        return json.dumps(self.to_json_value(), sort_keys=True, separators=(",", ":"))
