"""Safe JSON projections for application-facing hardware runtime health."""

from __future__ import annotations

from typing import Any, Dict


def project_health(health: object) -> Dict[str, Any]:
    """Copy only the typed redacted health fields into an HTTP value."""

    return {
        "ready": bool(health.ready),
        "degraded": bool(health.degraded),
        "closed": bool(health.closed),
        "state": getattr(health.state, "value", str(health.state)),
        "bindings": {
            binding_id: {
                "binding_id": binding.binding_id,
                "capability_id": binding.capability_id,
                "required": bool(binding.required),
                "state": binding.state,
                "generation": binding.generation,
                "quarantined": bool(binding.quarantined),
                "contaminated": bool(binding.contaminated),
            }
            for binding_id, binding in health.bindings.items()
        },
    }
