"""Stable, secret-safe failures returned by radio drivers."""

import re
from typing import Any


_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(password|passwd|psk|pin|secret|credential)\s*[:=]\s*([^\s,;]+)"
)


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if str(key).lower()
                in {"password", "passwd", "psk", "pin", "secret", "credential"}
                else redact_secrets(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    if isinstance(value, str):
        return _SECRET_ASSIGNMENT.sub(
            lambda match: match.group(1) + "=[REDACTED]", value
        )
    return value


class RadioOperationError(RuntimeError):
    code = "radio_operation_failed"
    http_status = 502

    def __init__(self, detail: str):
        self.detail = str(redact_secrets(detail))
        super().__init__(self.detail)


class UnsupportedFeatureError(RadioOperationError):
    code = "unsupported_feature"
    http_status = 501


class RadioConflictError(RadioOperationError):
    code = "radio_concurrency_conflict"
    http_status = 409


class RadioTimeoutError(RadioOperationError):
    code = "radio_operation_timeout"
    http_status = 504


class RadioResourceNotFoundError(RadioOperationError):
    code = "radio_resource_not_found"
    http_status = 404


class InvalidRadioRequestError(RadioOperationError):
    code = "invalid_radio_request"
    http_status = 422
