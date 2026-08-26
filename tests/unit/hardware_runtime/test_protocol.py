"""Production-independent conformance checks for the driver IPC contract."""

from __future__ import annotations

import hashlib

import pytest

from totem_driver_api.identifiers import ContractError
from totem_driver_api.messages import (
    AttachmentDescriptor,
    LogicalMessage,
    PendingRequests,
    error_result,
    normalize_message,
    unknown_type_result,
)


def _request(request_id: str = "request-1") -> dict[str, object]:
    return {"type": "display.frame.write", "id": request_id, "frame": {"mode": "mono"}}




def test_logical_request_result_error_and_normalization_are_carrier_neutral() -> None:
    request = LogicalMessage.request("display.frame.write", "r-1", {"frame": {"mode": "mono"}})
    assert normalize_message(request) == _request("r-1")
    assert LogicalMessage.from_json_value(normalize_message(request)) == request

    result = LogicalMessage.result_for(request, {"accepted": 1})
    assert result.to_json_value() == {
        "type": "display.frame.write.result", "id": "r-1", "ok": True, "accepted": 1
    }
    failed = error_result(request, "unknown_type", "unknown type: display.frame.write")
    assert failed["error"] == {"code": "unknown_type", "message": "unknown type: display.frame.write"}
    assert "traceback" not in failed["error"]


@pytest.mark.parametrize(
    "value",
    [b"binary", ("tuple",), {1: "key"}, float("nan"), float("inf"), -(2**63) - 1, 2**63],
)
def test_logical_values_reject_non_json_subset(value: object) -> None:
    with pytest.raises(ContractError):
        LogicalMessage.request("display.frame.write", "r-1", {"value": value})


@pytest.mark.parametrize("type_value", ["", "display", "Display.write", "display..write", "display.write."])
def test_logical_requests_require_nonempty_action_type(type_value: str) -> None:
    with pytest.raises(ContractError):
        LogicalMessage.request(type_value, "r-1", {})


def test_correlation_rejects_duplicate_id_per_generation_and_stale_result() -> None:
    pending = PendingRequests("generation-a")
    pending.register(_request("same"))
    with pytest.raises(ContractError):
        pending.register(_request("same"))
    assert pending.consume({"type": "display.frame.write.result", "id": "same", "ok": True}) is not None
    assert pending.consume({"type": "display.frame.write.result", "id": "same", "ok": True}) is None
    assert PendingRequests("generation-b").consume({"type": "display.frame.write.result", "id": "same", "ok": True}) is None


def test_unknown_push_is_ignored_and_unknown_request_is_correlated() -> None:
    assert unknown_type_result({"type": "future.push"}) is None
    assert unknown_type_result(_request("r-unknown")) == {
        "type": "display.frame.write.result",
        "id": "r-unknown",
        "ok": False,
        "error": {"code": "unknown_type", "message": "unknown type: display.frame.write"},
    }


def test_attachment_descriptor_requires_media_type_length_and_lowercase_digest() -> None:
    digest = hashlib.sha256(b"a").hexdigest()
    assert AttachmentDescriptor("frame", "application/x-totem-mono-frame", 1, digest).to_json_value()["id"] == "frame"
    for descriptor in [
        ("", "application/octet-stream", 1, digest),
        ("frame", "", 1, digest),
        ("frame", "application/octet-stream", -1, digest),
        ("frame", "application/octet-stream", 1, digest.upper()),
    ]:
        with pytest.raises(ContractError):
            AttachmentDescriptor(*descriptor)
