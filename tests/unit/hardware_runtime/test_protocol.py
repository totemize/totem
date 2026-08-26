"""Production-independent conformance checks for the driver IPC contract."""

from __future__ import annotations

import hashlib
import json
import socket
import threading
from typing import Optional

import pytest

from totem.hardware.hosts.protocol import (
    CODEC_CANONICAL_JSON,
    MAGIC,
    MAX_ATTACHMENT_BYTES,
    MAX_HEADER_BYTES,
    PREFIX,
    FrameCodec,
    ProtocolError,
)
from totem.hardware.hosts.unix import UnixFrameStream
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


def _raw_frame(header: object, payload: bytes = b"", *, magic: bytes = MAGIC, version: int = 1,
               codec: int = CODEC_CANONICAL_JSON, flags: int = 0,
               header_length: Optional[int] = None, attachment_length: Optional[int] = None) -> bytes:
    encoded = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return PREFIX.pack(
        magic, version, codec, flags,
        len(encoded) if header_length is None else header_length,
        len(payload) if attachment_length is None else attachment_length,
    ) + encoded + payload


class _BytesReader:
    def __init__(self, data: bytes, chunk_size: Optional[int] = None) -> None:
        self.data = data
        self.offset = 0
        self.chunk_size = chunk_size
        self.calls = 0

    def recv(self, size: int) -> bytes:
        self.calls += 1
        if self.offset >= len(self.data):
            return b""
        end = min(len(self.data), self.offset + min(size, self.chunk_size or size))
        out = self.data[self.offset:end]
        self.offset = end
        return out


class _PartialWriter:
    def sendall(self, data: bytes) -> None:
        raise AssertionError("UnixFrameStream must use sendall")




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


def test_control_round_trip_and_canonical_json() -> None:
    codec = FrameCodec()
    encoded = codec.encode({"z": 1, "type": "totem.status.get", "id": "control"})
    assert encoded[PREFIX.size:] == b'{"id":"control","type":"totem.status.get","z":1}'
    assert codec.decode(encoded)["type"] == "totem.status.get"


def test_one_byte_fragmentation_and_pipelined_frames() -> None:
    codec = FrameCodec()
    wire = codec.encode(_request("first")) + codec.encode(_request("second"))
    stream = UnixFrameStream(_BytesReader(wire, 1))
    assert stream.receive()["id"] == "first"
    assert stream.receive()["id"] == "second"


def test_multiple_verified_attachments_sort_canonically_and_round_trip_4000_bytes() -> None:
    codec = FrameCodec()
    display = bytes(range(250)) * 16
    wire = codec.encode(
        _request(),
        {"z": ("application/z", b"z"), "frame": ("application/x-totem-mono-frame", display)},
    )
    decoded = codec.decode(wire)
    assert list(decoded["_attachments"]) == ["frame", "z"]
    assert decoded["_attachments"]["frame"] == display
    assert decoded["_attachment_media_types"]["frame"] == "application/x-totem-mono-frame"


@pytest.mark.parametrize(
    "wire,code",
    [
        (b"", "unexpected_eof"),
        (_raw_frame({"type": "x.y"}, magic=b"NOPE"), "invalid_magic"),
        (_raw_frame({"type": "x.y"}, version=2), "unsupported_version"),
        (_raw_frame({"type": "x.y"}, codec=2), "unsupported_codec"),
        (_raw_frame({"type": "x.y"}, flags=1), "unsupported_flags"),
        (_raw_frame({"type": "x.y"}, header_length=MAX_HEADER_BYTES + 1), "header_too_large"),
        (_raw_frame({"type": "x.y"}, attachment_length=MAX_ATTACHMENT_BYTES + 1), "attachment_too_large"),
        (PREFIX.pack(MAGIC, 1, 1, 0, 1, 0) + b"{", "invalid_header"),
        (_raw_frame(["not", "object"]), "invalid_envelope"),
        (_raw_frame({"type": "x.y", "x": float("nan")}), "invalid_header"),
    ],
)
def test_malformed_prefix_and_header_vectors_fail_stably(wire: bytes, code: str) -> None:
    with pytest.raises(ProtocolError, match=code):
        FrameCodec().decode(wire)


def test_duplicate_json_keys_are_rejected() -> None:
    header = b'{"type":"x.y","type":"z.q"}'
    wire = PREFIX.pack(MAGIC, 1, 1, 0, len(header), 0) + header
    with pytest.raises(ProtocolError, match="invalid_header"):
        FrameCodec().decode(wire)


def test_descriptor_damage_duplicate_ids_and_unclaimed_bytes_fail() -> None:
    digest = hashlib.sha256(b"a").hexdigest()
    cases = [
        ({"type": "x.y", "_attachments": [{"id": "a", "media_type": "text/plain", "length": 1, "sha256": digest}]}, b"b", "checksum_mismatch"),
        ({"type": "x.y", "_attachments": [{"id": "a", "media_type": "text/plain", "length": 1, "sha256": digest}, {"id": "a", "media_type": "text/plain", "length": 0, "sha256": hashlib.sha256(b"").hexdigest()}]}, b"a", "invalid_attachments"),
        ({"type": "x.y", "_attachments": []}, b"x", "invalid_attachments"),
    ]
    for header, payload, code in cases:
        with pytest.raises(ProtocolError, match=code):
            FrameCodec().decode(_raw_frame(header, payload))


def test_oversized_declarations_fail_before_body_read() -> None:
    reader = _BytesReader(PREFIX.pack(MAGIC, 1, 1, 0, MAX_HEADER_BYTES + 1, 0))
    with pytest.raises(ProtocolError, match="header_too_large"):
        UnixFrameStream(reader).receive()
    assert reader.calls == 1


def test_sendall_is_required_not_partial_send() -> None:
    with pytest.raises(AssertionError, match="sendall"):
        UnixFrameStream(_PartialWriter()).send(_request())


def test_real_socketpair_request_result_push_and_unknown_request() -> None:
    client, server = socket.socketpair()
    failures = []

    def serve() -> None:
        try:
            peer = UnixFrameStream(server)
            request = peer.receive()
            peer.send(error_result(request, "unknown_type", "unknown type: display.frame.write"))
            peer.send({"type": "display.refresh.completed", "cause": {"id": request["id"]}})
        except BaseException as exc:  # pragma: no cover - re-raised below
            failures.append(exc)
        finally:
            server.close()

    thread = threading.Thread(target=serve)
    thread.start()
    peer = UnixFrameStream(client)
    peer.send(_request("socket-request"))
    assert peer.receive()["id"] == "socket-request"
    assert peer.receive()["type"] == "display.refresh.completed"
    client.close()
    thread.join(timeout=2)
    assert not failures
