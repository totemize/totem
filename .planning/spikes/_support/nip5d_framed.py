#!/usr/bin/env python3
"""NIP-5D-shaped logical envelopes over a bounded framed byte stream.

The module is spike code, not a production API. It keeps logical message
semantics independent from the header codec so JSON and MessagePack can be
compared without changing request, result, event, or attachment behavior.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import platform
import re
import socket
import struct
import threading
import time
from dataclasses import dataclass
from statistics import median
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple


MAGIC = b"THW1"
PROTOCOL_VERSION = 1
PREFIX = struct.Struct("!4sBBHII")
MAX_HEADER_BYTES = 64 * 1024
MAX_ATTACHMENT_BYTES = 16 * 1024 * 1024
MAX_ATTACHMENTS = 16
TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$")

AttachmentInput = Mapping[str, Tuple[str, bytes]]


class ProtocolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_json_value(value: Any, depth: int = 0) -> None:
    """Reject MessagePack-only values so every codec has JSON object semantics."""

    if depth > 64:
        raise ProtocolError("invalid_envelope", "message nesting exceeds 64 levels")
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        if -(2**63) <= value <= 2**63 - 1:
            return
        raise ProtocolError("invalid_envelope", "integer is outside the signed 64-bit range")
    if isinstance(value, float):
        if math.isfinite(value):
            return
        raise ProtocolError("invalid_envelope", "non-finite numbers are not permitted")
    if isinstance(value, list):
        for item in value:
            validate_json_value(item, depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProtocolError("invalid_envelope", "object keys must be strings")
            validate_json_value(item, depth + 1)
        return
    raise ProtocolError(
        "invalid_envelope", f"{type(value).__name__} is not a JSON-compatible value"
    )


def canonicalize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: canonicalize_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonicalize_json(item) for item in value]
    return value


class JsonCodec:
    name = "canonical-json"
    wire_id = 1
    invalid_example = b"{"
    library_version = "Python standard library"

    @staticmethod
    def encode(value: Mapping[str, Any]) -> bytes:
        try:
            return json.dumps(
                canonicalize_json(value),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ProtocolError("invalid_header", f"JSON encoding failed: {exc}") from exc

    @staticmethod
    def decode(data: bytes) -> Dict[str, Any]:
        try:
            value = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtocolError("invalid_header", f"JSON decoding failed: {exc}") from exc
        if not isinstance(value, dict):
            raise ProtocolError("invalid_envelope", "message header must decode to an object")
        return value


class MessagePackCodec:
    name = "messagepack-json-subset"
    wire_id = 2
    invalid_example = b"\xc1"  # Reserved byte in the MessagePack format.

    def __init__(self, pure_python: bool = False) -> None:
        try:
            import msgpack
        except ImportError as exc:
            raise RuntimeError(
                "MessagePack spike requires msgpack; install 002-b requirements first"
            ) from exc
        self._msgpack = msgpack
        self._pure_python = pure_python
        if pure_python:
            from msgpack import fallback

            self._fallback = fallback
            self._unpackb = fallback.unpackb
            self.name = "messagepack-json-subset-pure-python"
            self.library_version = f"{msgpack.__version__} fallback"
        else:
            self._unpackb = msgpack.unpackb
            self.name = "messagepack-json-subset-native"
            self.library_version = f"{msgpack.__version__} {msgpack.Packer.__module__}"

    def encode(self, value: Mapping[str, Any]) -> bytes:
        try:
            canonical = canonicalize_json(value)
            if self._pure_python:
                return self._fallback.Packer(
                    use_bin_type=True, strict_types=True
                ).pack(canonical)
            return self._msgpack.packb(canonical, use_bin_type=True, strict_types=True)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ProtocolError(
                "invalid_header", f"MessagePack encoding failed: {exc}"
            ) from exc

    def decode(self, data: bytes) -> Dict[str, Any]:
        try:
            value = self._unpackb(
                data,
                raw=False,
                strict_map_key=True,
                use_list=True,
                max_str_len=MAX_HEADER_BYTES,
                max_bin_len=MAX_HEADER_BYTES,
                max_array_len=MAX_HEADER_BYTES,
                max_map_len=MAX_HEADER_BYTES,
                max_ext_len=MAX_HEADER_BYTES,
            )
        except Exception as exc:
            # The library documents several ValueError/FormatError/StackError
            # paths. The try block is intentionally only the decode operation.
            raise ProtocolError(
                "invalid_header", f"MessagePack decoding failed: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise ProtocolError("invalid_envelope", "message header must decode to an object")
        return value


@dataclass(frozen=True)
class Frame:
    message: Dict[str, Any]
    attachments: Dict[str, bytes]
    media_types: Dict[str, str]
    wire_bytes: int
    header_bytes: int
    attachment_bytes: int


class BytesReader:
    """A recv-compatible reader that can force arbitrary stream fragmentation."""

    def __init__(self, data: bytes, chunk_size: Optional[int] = None) -> None:
        self._data = data
        self._offset = 0
        self._chunk_size = chunk_size

    def recv(self, requested: int) -> bytes:
        if self._offset >= len(self._data):
            return b""
        size = requested
        if self._chunk_size is not None:
            size = min(size, self._chunk_size)
        end = min(self._offset + size, len(self._data))
        chunk = self._data[self._offset : end]
        self._offset = end
        return chunk


def validate_message(message: Mapping[str, Any]) -> None:
    validate_json_value(message)
    message_type = message.get("type")
    if not isinstance(message_type, str) or not TYPE_PATTERN.fullmatch(message_type):
        raise ProtocolError(
            "invalid_envelope", "type must be a lower-case domain.action-style string"
        )
    if "id" in message and (
        not isinstance(message["id"], str) or not message["id"].strip()
    ):
        raise ProtocolError("invalid_envelope", "id must be a non-empty string when present")
    if "_attachments" in message:
        raise ProtocolError("reserved_field", "_attachments is owned by the carrier")


def encode_frame(
    codec: Any,
    message: Mapping[str, Any],
    attachments: Optional[AttachmentInput] = None,
) -> bytes:
    validate_message(message)
    attachment_map = attachments or {}
    if len(attachment_map) > MAX_ATTACHMENTS:
        raise ProtocolError("too_many_attachments", f"maximum is {MAX_ATTACHMENTS}")

    descriptors: List[Dict[str, Any]] = []
    payload_parts: List[bytes] = []
    total_attachment_bytes = 0
    for attachment_id in sorted(attachment_map):
        value = attachment_map[attachment_id]
        if not isinstance(attachment_id, str) or not attachment_id:
            raise ProtocolError("invalid_attachments", "attachment id must be non-empty")
        if (
            not isinstance(value, tuple)
            or len(value) != 2
            or not isinstance(value[0], str)
            or not isinstance(value[1], bytes)
        ):
            raise ProtocolError(
                "invalid_attachments", "attachment value must be (media_type, bytes)"
            )
        media_type, payload = value
        total_attachment_bytes += len(payload)
        if total_attachment_bytes > MAX_ATTACHMENT_BYTES:
            raise ProtocolError(
                "attachment_too_large",
                f"attachment payload exceeds {MAX_ATTACHMENT_BYTES} bytes",
            )
        descriptors.append(
            {
                "id": attachment_id,
                "media_type": media_type,
                "length": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
        payload_parts.append(payload)

    header: MutableMapping[str, Any] = dict(message)
    if descriptors:
        header["_attachments"] = descriptors
    encoded_header = codec.encode(header)
    if len(encoded_header) > MAX_HEADER_BYTES:
        raise ProtocolError("header_too_large", f"header exceeds {MAX_HEADER_BYTES} bytes")

    prefix = PREFIX.pack(
        MAGIC,
        PROTOCOL_VERSION,
        codec.wire_id,
        0,
        len(encoded_header),
        total_attachment_bytes,
    )
    return prefix + encoded_header + b"".join(payload_parts)


def receive_exact(stream: Any, size: int) -> bytes:
    chunks: List[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.recv(remaining)
        if not chunk:
            raise ProtocolError(
                "unexpected_eof", f"stream ended with {remaining} bytes still required"
            )
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame(stream: Any, codec: Any) -> Frame:
    prefix = receive_exact(stream, PREFIX.size)
    magic, version, codec_id, flags, header_length, attachment_length = PREFIX.unpack(prefix)
    if magic != MAGIC:
        raise ProtocolError("invalid_magic", "frame magic does not match")
    if version != PROTOCOL_VERSION:
        raise ProtocolError("unsupported_version", f"unsupported protocol version {version}")
    if codec_id != codec.wire_id:
        raise ProtocolError("unsupported_codec", f"unexpected header codec id {codec_id}")
    if flags != 0:
        raise ProtocolError("unsupported_flags", f"unknown flags 0x{flags:04x}")
    if header_length > MAX_HEADER_BYTES:
        raise ProtocolError("header_too_large", f"header length is {header_length}")
    if attachment_length > MAX_ATTACHMENT_BYTES:
        raise ProtocolError(
            "attachment_too_large", f"attachment length is {attachment_length}"
        )

    encoded_header = receive_exact(stream, header_length)
    payload = receive_exact(stream, attachment_length)
    header = codec.decode(encoded_header)
    descriptors = header.pop("_attachments", [])
    validate_message(header)
    if not isinstance(descriptors, list) or len(descriptors) > MAX_ATTACHMENTS:
        raise ProtocolError("invalid_attachments", "invalid attachment descriptor list")

    attachments: Dict[str, bytes] = {}
    media_types: Dict[str, str] = {}
    offset = 0
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            raise ProtocolError("invalid_attachments", "descriptor must be an object")
        attachment_id = descriptor.get("id")
        media_type = descriptor.get("media_type")
        length = descriptor.get("length")
        checksum = descriptor.get("sha256")
        if (
            not isinstance(attachment_id, str)
            or not attachment_id
            or attachment_id in attachments
            or not isinstance(media_type, str)
            or not media_type
            or not isinstance(length, int)
            or isinstance(length, bool)
            or length < 0
            or not isinstance(checksum, str)
            or not re.fullmatch(r"[0-9a-f]{64}", checksum)
        ):
            raise ProtocolError("invalid_attachments", "malformed or duplicate descriptor")
        end = offset + length
        if end > len(payload):
            raise ProtocolError("invalid_attachments", "descriptor exceeds attachment payload")
        value = payload[offset:end]
        actual_checksum = hashlib.sha256(value).hexdigest()
        if not hmac.compare_digest(actual_checksum, checksum):
            raise ProtocolError("checksum_mismatch", f"checksum failed for {attachment_id}")
        attachments[attachment_id] = value
        media_types[attachment_id] = media_type
        offset = end

    if offset != len(payload):
        raise ProtocolError("invalid_attachments", "unclaimed bytes remain in attachment payload")

    return Frame(
        message=header,
        attachments=attachments,
        media_types=media_types,
        wire_bytes=PREFIX.size + header_length + attachment_length,
        header_bytes=header_length,
        attachment_bytes=attachment_length,
    )


def send_frame(
    stream: socket.socket,
    codec: Any,
    message: Mapping[str, Any],
    attachments: Optional[AttachmentInput] = None,
) -> None:
    stream.sendall(encode_frame(codec, message, attachments))


def error_result(message: Mapping[str, Any], code: str, detail: str) -> Dict[str, Any]:
    return {
        "type": f"{message['type']}.result",
        "id": message["id"],
        "ok": False,
        "error": {"code": code, "message": detail},
    }


def dispatch(frame: Frame) -> List[Tuple[Dict[str, Any], AttachmentInput]]:
    """Small reference dispatcher matching Totem's NIP-5D-shaped bus rules."""

    message = frame.message
    message_type = message["type"]
    request_id = message.get("id")

    # NIP-5D's forward-compatible rule applies to uncorrelated pushes.
    if request_id is None:
        return []

    if message_type == "totem.status.get":
        return [
            (
                {
                    "type": "totem.status.get.result",
                    "id": request_id,
                    "ok": True,
                    "status": {"driver_host": "ready"},
                },
                {},
            )
        ]

    if message_type == "display.frame.write":
        frame_spec = message.get("frame")
        attachment_id = (
            frame_spec.get("attachment") if isinstance(frame_spec, dict) else None
        )
        if not isinstance(attachment_id, str) or attachment_id not in frame.attachments:
            return [
                (
                    error_result(
                        message,
                        "missing_attachment",
                        "frame.attachment must identify a verified attachment",
                    ),
                    {},
                )
            ]
        return [
            (
                {
                    "type": "display.frame.write.result",
                    "id": request_id,
                    "ok": True,
                    "accepted_bytes": len(frame.attachments[attachment_id]),
                },
                {},
            ),
            (
                {
                    "type": "display.refresh.completed",
                    "binding": message.get("binding"),
                    "cause": {"id": request_id},
                },
                {},
            ),
        ]

    # Totemd already returns a correlated `.result` error for unknown requests.
    return [(error_result(message, "unknown_type", f"unknown type: {message_type}"), {})]


def expect_error(code: str, action: Any) -> None:
    try:
        action()
    except ProtocolError as exc:
        if exc.code != code:
            raise AssertionError(f"expected {code}, received {exc.code}") from exc
    else:
        raise AssertionError(f"expected ProtocolError({code})")


def raw_frame(codec: Any, header: Mapping[str, Any], payload: bytes = b"") -> bytes:
    encoded_header = codec.encode(header)
    return PREFIX.pack(
        MAGIC, PROTOCOL_VERSION, codec.wire_id, 0, len(encoded_header), len(payload)
    ) + encoded_header + payload


def run_socket_conversation(codec: Any, display_bytes: bytes) -> None:
    client, server = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(3.0)
    server.settimeout(3.0)
    server_failures: List[BaseException] = []

    def serve() -> None:
        try:
            for _ in range(4):
                incoming = read_frame(server, codec)
                for response, attachments in dispatch(incoming):
                    send_frame(server, codec, response, attachments)
        except BaseException as exc:  # captured and re-raised in the test thread
            server_failures.append(exc)
        finally:
            server.close()

    thread = threading.Thread(target=serve, name="spike-nip5d-server")
    thread.start()
    try:
        send_frame(
            client,
            codec,
            {
                "type": "display.frame.write",
                "id": "frame-req",
                "binding": "display-0",
                "frame": {"attachment": "frame-1", "width": 250, "height": 122},
            },
            {"frame-1": ("application/x-totem-mono-frame", display_bytes)},
        )
        result = read_frame(client, codec).message
        event = read_frame(client, codec).message
        assert result == {
            "type": "display.frame.write.result",
            "id": "frame-req",
            "ok": True,
            "accepted_bytes": len(display_bytes),
        }
        assert event == {
            "type": "display.refresh.completed",
            "binding": "display-0",
            "cause": {"id": "frame-req"},
        }

        # Unknown unsolicited pushes are ignored, then the next request still works.
        send_frame(client, codec, {"type": "future.capability.event", "value": 7})
        send_frame(client, codec, {"type": "future.capability.get", "id": "unknown-1"})
        unknown = read_frame(client, codec).message
        assert unknown["type"] == "future.capability.get.result"
        assert unknown["id"] == "unknown-1"
        assert unknown["ok"] is False
        assert unknown["error"]["code"] == "unknown_type"

        # This fixture deliberately matches totemd's outer response convention.
        send_frame(client, codec, {"type": "totem.status.get", "id": "status-1"})
        status = read_frame(client, codec).message
        assert status["type"] == "totem.status.get.result"
        assert status["id"] == "status-1"
        assert status["ok"] is True
    finally:
        client.close()
        thread.join(timeout=3.0)
    if thread.is_alive():
        raise AssertionError("server thread did not exit")
    if server_failures:
        raise server_failures[0]


def run_conformance(codec: Any) -> List[str]:
    display_bytes = bytes((index * 31) % 256 for index in range((250 * 122 + 7) // 8))
    checks: List[str] = []

    def check(name: str, action: Any) -> None:
        action()
        checks.append(name)

    request = {"type": "totem.status.get", "id": "a1"}
    encoded_request = encode_frame(codec, request)

    def control_round_trip() -> None:
        frame = read_frame(BytesReader(encoded_request), codec)
        assert frame.message == request
        assert not frame.attachments

    check("control_round_trip", control_round_trip)

    def fragmented() -> None:
        frame = read_frame(BytesReader(encoded_request, chunk_size=1), codec)
        assert frame.message == request

    check("one_byte_fragmentation", fragmented)

    def pipelined() -> None:
        second = {"type": "totem.config.get", "id": "a2"}
        stream = BytesReader(encoded_request + encode_frame(codec, second), chunk_size=3)
        assert read_frame(stream, codec).message == request
        assert read_frame(stream, codec).message == second

    check("pipelined_frames", pipelined)

    def multiple_attachments() -> None:
        message = {
            "type": "display.frame.write",
            "id": "multi",
            "frame": {"attachment": "pixels"},
        }
        attachments = {
            "pixels": ("application/octet-stream", display_bytes),
            "lut": ("application/octet-stream", b"\x00\x01\x02"),
        }
        frame = read_frame(BytesReader(encode_frame(codec, message, attachments)), codec)
        assert frame.message == message
        assert frame.attachments == {key: value[1] for key, value in attachments.items()}

    check("multiple_verified_attachments", multiple_attachments)

    def canonical_attachment_order() -> None:
        message = {"type": "totem.test", "id": "ordered"}
        first = {
            "z": ("application/octet-stream", b"z"),
            "a": ("application/octet-stream", b"a"),
        }
        second = {
            "a": ("application/octet-stream", b"a"),
            "z": ("application/octet-stream", b"z"),
        }
        assert encode_frame(codec, message, first) == encode_frame(codec, message, second)

    check("canonical_attachment_order", canonical_attachment_order)

    check(
        "missing_type_rejected",
        lambda: expect_error("invalid_envelope", lambda: encode_frame(codec, {"id": "x"})),
    )
    check(
        "invalid_id_rejected",
        lambda: expect_error(
            "invalid_envelope",
            lambda: encode_frame(codec, {"type": "totem.test", "id": 7}),
        ),
    )
    check(
        "binary_value_outside_attachment_channel_rejected",
        lambda: expect_error(
            "invalid_envelope",
            lambda: encode_frame(
                codec, {"type": "totem.test", "id": "bytes", "value": b"not-json"}
            ),
        ),
    )
    check(
        "non_finite_number_rejected",
        lambda: expect_error(
            "invalid_envelope",
            lambda: encode_frame(
                codec, {"type": "totem.test", "id": "nan", "value": float("nan")}
            ),
        ),
    )
    check(
        "integer_outside_signed_64_bit_rejected",
        lambda: expect_error(
            "invalid_envelope",
            lambda: encode_frame(
                codec, {"type": "totem.test", "id": "huge", "value": 2**63}
            ),
        ),
    )
    check(
        "reserved_attachment_field_rejected",
        lambda: expect_error(
            "reserved_field",
            lambda: encode_frame(codec, {"type": "totem.test", "_attachments": []}),
        ),
    )
    check(
        "truncated_frame_rejected",
        lambda: expect_error(
            "unexpected_eof",
            lambda: read_frame(BytesReader(encoded_request[:-1]), codec),
        ),
    )

    oversized_header = PREFIX.pack(
        MAGIC, PROTOCOL_VERSION, codec.wire_id, 0, MAX_HEADER_BYTES + 1, 0
    )
    check(
        "oversized_header_rejected_before_read",
        lambda: expect_error(
            "header_too_large", lambda: read_frame(BytesReader(oversized_header), codec)
        ),
    )
    oversized_attachment = PREFIX.pack(
        MAGIC, PROTOCOL_VERSION, codec.wire_id, 0, 0, MAX_ATTACHMENT_BYTES + 1
    )
    check(
        "oversized_attachment_rejected_before_read",
        lambda: expect_error(
            "attachment_too_large",
            lambda: read_frame(BytesReader(oversized_attachment), codec),
        ),
    )

    check(
        "oversized_header_rejected_before_write",
        lambda: expect_error(
            "header_too_large",
            lambda: encode_frame(
                codec, {"type": "totem.test", "id": "large", "value": "x" * 70_000}
            ),
        ),
    )

    def invalid_magic() -> None:
        damaged = b"NOPE" + encoded_request[4:]
        expect_error("invalid_magic", lambda: read_frame(BytesReader(damaged), codec))

    check("invalid_magic_rejected", invalid_magic)

    def unsupported_version() -> None:
        magic, version, codec_id, flags, header_len, attachment_len = PREFIX.unpack(
            encoded_request[: PREFIX.size]
        )
        damaged = PREFIX.pack(
            magic, version + 1, codec_id, flags, header_len, attachment_len
        ) + encoded_request[PREFIX.size :]
        expect_error("unsupported_version", lambda: read_frame(BytesReader(damaged), codec))

    check("protocol_version_mismatch_rejected", unsupported_version)

    def unsupported_flags() -> None:
        magic, version, codec_id, _, header_len, attachment_len = PREFIX.unpack(
            encoded_request[: PREFIX.size]
        )
        damaged = PREFIX.pack(
            magic, version, codec_id, 1, header_len, attachment_len
        ) + encoded_request[PREFIX.size :]
        expect_error("unsupported_flags", lambda: read_frame(BytesReader(damaged), codec))

    check("unknown_flags_rejected", unsupported_flags)

    def unsupported_codec() -> None:
        magic, version, codec_id, flags, header_len, attachment_len = PREFIX.unpack(
            encoded_request[: PREFIX.size]
        )
        damaged = PREFIX.pack(
            magic, version, (codec_id + 1) % 255, flags, header_len, attachment_len
        ) + encoded_request[PREFIX.size :]
        expect_error("unsupported_codec", lambda: read_frame(BytesReader(damaged), codec))

    check("codec_mismatch_rejected", unsupported_codec)

    def malformed_header() -> None:
        invalid = codec.invalid_example
        encoded = PREFIX.pack(
            MAGIC, PROTOCOL_VERSION, codec.wire_id, 0, len(invalid), 0
        ) + invalid
        expect_error("invalid_header", lambda: read_frame(BytesReader(encoded), codec))

    check("malformed_header_rejected", malformed_header)

    def checksum_mismatch() -> None:
        encoded = bytearray(
            encode_frame(
                codec,
                {
                    "type": "display.frame.write",
                    "id": "bad-checksum",
                    "frame": {"attachment": "frame-1"},
                },
                {"frame-1": ("application/octet-stream", display_bytes)},
            )
        )
        encoded[-1] ^= 0xFF
        expect_error(
            "checksum_mismatch", lambda: read_frame(BytesReader(bytes(encoded)), codec)
        )

    check("checksum_mismatch_rejected", checksum_mismatch)

    def duplicate_descriptor() -> None:
        payload = b"ab"
        descriptor = {
            "id": "same",
            "media_type": "application/octet-stream",
            "length": 1,
            "sha256": hashlib.sha256(b"a").hexdigest(),
        }
        header = {
            "type": "display.frame.write",
            "id": "duplicate",
            "_attachments": [descriptor, dict(descriptor, sha256=hashlib.sha256(b"b").hexdigest())],
        }
        expect_error(
            "invalid_attachments",
            lambda: read_frame(BytesReader(raw_frame(codec, header, payload)), codec),
        )

    check("duplicate_attachment_id_rejected", duplicate_descriptor)

    def unclaimed_payload() -> None:
        header = {"type": "display.frame.write", "id": "unclaimed"}
        expect_error(
            "invalid_attachments",
            lambda: read_frame(BytesReader(raw_frame(codec, header, b"x")), codec),
        )

    check("unclaimed_attachment_bytes_rejected", unclaimed_payload)

    def missing_attachment_result() -> None:
        frame = read_frame(
            BytesReader(
                encode_frame(
                    codec,
                    {
                        "type": "display.frame.write",
                        "id": "missing",
                        "frame": {"attachment": "not-present"},
                    },
                )
            ),
            codec,
        )
        outputs = dispatch(frame)
        assert len(outputs) == 1
        assert outputs[0][0]["type"] == "display.frame.write.result"
        assert outputs[0][0]["id"] == "missing"
        assert outputs[0][0]["ok"] is False
        assert outputs[0][0]["error"]["code"] == "missing_attachment"

    check("missing_attachment_is_correlated_error", missing_attachment_result)
    check("socket_request_result_event_flow", lambda: run_socket_conversation(codec, display_bytes))
    return checks


def benchmark(codec: Any, iterations: int = 2_000) -> Dict[str, Any]:
    display_bytes = bytes((index * 31) % 256 for index in range((250 * 122 + 7) // 8))
    control = {"type": "totem.status.get", "id": "benchmark-1"}
    display = {
        "type": "display.frame.write",
        "id": "benchmark-frame",
        "binding": "display-0",
        "frame": {"attachment": "frame-1", "width": 250, "height": 122},
    }
    attachments = {"frame-1": ("application/x-totem-mono-frame", display_bytes)}
    control_wire = encode_frame(codec, control)
    display_wire = encode_frame(codec, display, attachments)
    inline = dict(display)
    inline["frame"] = {
        "encoding": "base64",
        "data": base64.b64encode(display_bytes).decode("ascii"),
        "width": 250,
        "height": 122,
    }
    inline_wire = encode_frame(codec, inline)
    _, _, _, _, display_header_length, display_attachment_length = PREFIX.unpack(
        display_wire[: PREFIX.size]
    )

    def measure_decode(wire: bytes, count: int) -> float:
        samples: List[float] = []
        for _ in range(7):
            started = time.perf_counter_ns()
            for _ in range(count):
                read_frame(BytesReader(wire), codec)
            elapsed_us = (time.perf_counter_ns() - started) / 1_000
            samples.append(elapsed_us / count)
        return round(median(samples), 6)

    def measure_encode_decode(
        message: Mapping[str, Any], attachment_map: AttachmentInput, count: int
    ) -> float:
        samples: List[float] = []
        for _ in range(7):
            started = time.perf_counter_ns()
            for _ in range(count):
                wire = encode_frame(codec, message, attachment_map)
                read_frame(BytesReader(wire), codec)
            elapsed_us = (time.perf_counter_ns() - started) / 1_000
            samples.append(elapsed_us / count)
        return round(median(samples), 6)

    return {
        "iterations": iterations,
        "decode_microseconds_per_frame": {
            "control": measure_decode(control_wire, iterations),
            "display_with_raw_attachment": measure_decode(
                display_wire, max(200, iterations // 4)
            ),
        },
        "encode_and_decode_microseconds_per_frame": {
            "control": measure_encode_decode(control, {}, iterations),
            "display_with_raw_attachment": measure_encode_decode(
                display, attachments, max(200, iterations // 4)
            ),
        },
        "wire_sizes_bytes": {
            "control": len(control_wire),
            "display_total": len(display_wire),
            "display_header": display_header_length,
            "display_raw_attachment": display_attachment_length,
            "display_inline_base64_total": len(inline_wire),
            "raw_savings_over_inline_base64": len(inline_wire) - len(display_wire),
        },
    }


def run_spike(codec: Any) -> Dict[str, Any]:
    checks = run_conformance(codec)
    return {
        "schema": "totem.nip5d-framed-ipc-spike@1",
        "codec": codec.name,
        "codec_library_version": codec.library_version,
        "codec_wire_id": codec.wire_id,
        "protocol_version": PROTOCOL_VERSION,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "limits": {
            "header_bytes": MAX_HEADER_BYTES,
            "attachment_bytes": MAX_ATTACHMENT_BYTES,
            "attachments_per_frame": MAX_ATTACHMENTS,
        },
        "conformance": {"passed": len(checks), "checks": checks},
        "benchmark": benchmark(codec),
    }
