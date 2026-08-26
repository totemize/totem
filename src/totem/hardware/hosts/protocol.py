"""Small bounded framed carrier for the runtime tracer.

The logical message remains a JSON object while raw attachments follow the
header.  This deliberately small v1 seam gives the app and process host the
same envelope; the full codec conformance surface belongs to a later phase.
"""

from __future__ import annotations

import hashlib
import json
import struct
from typing import Any, Dict, Mapping, Tuple


MAX_HEADER_BYTES = 64 * 1024
MAX_ATTACHMENT_BYTES = 16 * 1024 * 1024
MAX_ATTACHMENTS = 16
_HEADER_LENGTH = struct.Struct("!I")


class ProtocolError(ValueError):
    """The peer sent a malformed or over-limit carrier frame."""


def _error(message: str) -> ProtocolError:
    return ProtocolError(message)


def encode_frame(message: Mapping[str, Any]) -> bytes:
    """Encode one strict JSON envelope and its raw, bounded attachments."""

    value = dict(message)
    attachments = value.pop("_attachments", {})
    if not isinstance(attachments, Mapping) or len(attachments) > MAX_ATTACHMENTS:
        raise _error("invalid attachment collection")
    payloads = []
    descriptors = []
    for attachment_id in sorted(attachments):
        payload = attachments[attachment_id]
        if not isinstance(attachment_id, str) or not attachment_id or not isinstance(payload, bytes):
            raise _error("attachments must map non-empty ids to bytes")
        payloads.append(payload)
        descriptors.append(
            {
                "id": attachment_id,
                "length": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    total = sum(len(payload) for payload in payloads)
    if total > MAX_ATTACHMENT_BYTES:
        raise _error("attachments exceed runtime bound")
    value["_attachments"] = descriptors
    try:
        header = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _error("message is not strict JSON") from exc
    if len(header) > MAX_HEADER_BYTES:
        raise _error("header exceeds runtime bound")
    return _HEADER_LENGTH.pack(len(header)) + header + b"".join(payloads)


def decode_frame(frame: bytes) -> Dict[str, Any]:
    """Decode one complete frame, rejecting malformed size and hash metadata."""

    if len(frame) < _HEADER_LENGTH.size:
        raise _error("frame is truncated")
    (header_size,) = _HEADER_LENGTH.unpack(frame[: _HEADER_LENGTH.size])
    if header_size > MAX_HEADER_BYTES or len(frame) < _HEADER_LENGTH.size + header_size:
        raise _error("invalid header length")
    try:
        message = json.loads(frame[_HEADER_LENGTH.size : _HEADER_LENGTH.size + header_size])
    except (UnicodeDecodeError, ValueError) as exc:
        raise _error("header is not valid JSON") from exc
    if not isinstance(message, dict):
        raise _error("message must be an object")
    descriptors = message.get("_attachments", [])
    if not isinstance(descriptors, list) or len(descriptors) > MAX_ATTACHMENTS:
        raise _error("invalid attachment descriptors")
    payload = frame[_HEADER_LENGTH.size + header_size :]
    if len(payload) > MAX_ATTACHMENT_BYTES:
        raise _error("attachments exceed runtime bound")
    offset = 0
    attachments: Dict[str, bytes] = {}
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            raise _error("invalid attachment descriptor")
        attachment_id = descriptor.get("id")
        length = descriptor.get("length")
        digest = descriptor.get("sha256")
        if (
            not isinstance(attachment_id, str)
            or not attachment_id
            or attachment_id in attachments
            or isinstance(length, bool)
            or not isinstance(length, int)
            or length < 0
            or not isinstance(digest, str)
        ):
            raise _error("invalid attachment descriptor")
        end = offset + length
        if end > len(payload):
            raise _error("attachment payload is truncated")
        attachment = payload[offset:end]
        if hashlib.sha256(attachment).hexdigest() != digest:
            raise _error("attachment checksum mismatch")
        attachments[attachment_id] = attachment
        offset = end
    if offset != len(payload):
        raise _error("unclaimed attachment bytes")
    message["_attachments"] = attachments
    return message


def receive_frame(stream: Any) -> Dict[str, Any]:
    """Read one length-prefixed frame from a Unix stream without short-read assumptions."""

    header_size = _HEADER_LENGTH.unpack(_receive_exact(stream, _HEADER_LENGTH.size))[0]
    if header_size > MAX_HEADER_BYTES:
        raise _error("header exceeds runtime bound")
    header = _receive_exact(stream, header_size)
    try:
        value = json.loads(header)
    except (UnicodeDecodeError, ValueError) as exc:
        raise _error("header is not valid JSON") from exc
    if not isinstance(value, dict):
        raise _error("message must be an object")
    descriptors = value.get("_attachments", [])
    if not isinstance(descriptors, list) or len(descriptors) > MAX_ATTACHMENTS:
        raise _error("invalid attachment descriptors")
    total = 0
    for descriptor in descriptors:
        if not isinstance(descriptor, dict) or isinstance(descriptor.get("length"), bool):
            raise _error("invalid attachment descriptor")
        length = descriptor.get("length")
        if not isinstance(length, int) or length < 0:
            raise _error("invalid attachment descriptor")
        total += length
    if total > MAX_ATTACHMENT_BYTES:
        raise _error("attachments exceed runtime bound")
    return decode_frame(_HEADER_LENGTH.pack(header_size) + header + _receive_exact(stream, total))


def send_frame(stream: Any, message: Mapping[str, Any]) -> None:
    """Write a complete framed envelope using the stream's reliable sendall."""

    stream.sendall(encode_frame(message))


def _receive_exact(stream: Any, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.recv(remaining)
        if not chunk:
            raise _error("frame is truncated")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
