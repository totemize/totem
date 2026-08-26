"""Compatibility exports for canonical radio errors."""

from totem.hardware.builtin.radio.errors import (
    InvalidRadioRequestError,
    RadioConflictError,
    RadioOperationError,
    RadioResourceNotFoundError,
    RadioTimeoutError,
    UnsupportedFeatureError,
    redact_secrets,
)

__all__ = [
    "InvalidRadioRequestError",
    "RadioConflictError",
    "RadioOperationError",
    "RadioResourceNotFoundError",
    "RadioTimeoutError",
    "UnsupportedFeatureError",
    "redact_secrets",
]
