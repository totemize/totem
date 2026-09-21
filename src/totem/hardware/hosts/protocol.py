"""Bounded canonical-JSON framing for carrier-neutral driver messages."""

from __future__ import annotations

import hashlib
import json
import struct
from typing import Any, Dict, Mapping, Optional, Tuple, Union

from totem_driver_api.identifiers import ContractError
from totem_driver_api.messages import AttachmentDescriptor, LogicalMessage, normalize_message


MAGIC = b"THW1"
PROTOCOL_VERSION = 1
CODEC_CANONICAL_JSON = 1
CODEC_RESERVED_MESSAGEPACK = 2
PREFIX = struct.Struct("!4sBBHII")
MAX_HEADER_BYTES = 64 * 1024
MAX_ATTACHMENT_BYTES = 16 * 1024 * 1024
MAX_ATTACHMENTS = 16
_DEFAULT_MEDIA_TYPE = "application/octet-stream"


class ProtocolError(ValueError):
    """A stable framing failure that is safe to surface to the supervisor."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code + ": " + message)
        self.code = code
        self.message = message


def _fail(code: str, message: str) -> ProtocolError:
    return ProtocolError(code, message)


def _no_duplicate_object(pairs: Any) -> Dict[str, object]:
    result: Dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> object:
    raise ValueError("non-finite JSON number")


def _decode_json_object(data: bytes) -> Dict[str, object]:
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_no_duplicate_object,
            parse_constant=_reject_non_finite,
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise _fail("invalid_header", "header is not canonical JSON") from exc
    if not isinstance(value, dict):
        raise _fail("invalid_envelope", "message header must be an object")
    return value


def _encode_json_object(value: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise _fail("invalid_envelope", "message is not strict JSON") from exc


def _validate_prefix(prefix: bytes) -> Tuple[int, int]:
    if len(prefix) != PREFIX.size:
        raise _fail("unexpected_eof", "frame prefix is truncated")
    magic, version, codec, flags, header_length, attachment_length = PREFIX.unpack(prefix)
    if magic != MAGIC:
        raise _fail("invalid_magic", "frame magic does not match")
    if version != PROTOCOL_VERSION:
        raise _fail("unsupported_version", "unsupported protocol version")
    if codec != CODEC_CANONICAL_JSON:
        raise _fail("unsupported_codec", "unsupported header codec")
    if flags != 0:
        raise _fail("unsupported_flags", "unknown frame flags")
    if header_length > MAX_HEADER_BYTES:
        raise _fail("header_too_large", "header length exceeds runtime bound")
    if attachment_length > MAX_ATTACHMENT_BYTES:
        raise _fail("attachment_too_large", "attachment length exceeds runtime bound")
    return header_length, attachment_length


def _attachment_inputs(value: object) -> Tuple[Dict[str, Tuple[str, bytes]], Dict[str, object]]:
    if not isinstance(value, Mapping):
        raise _fail("invalid_attachments", "attachments must be a mapping")
    normalized: Dict[str, Tuple[str, bytes]] = {}
    for attachment_id, attachment in value.items():
        if not isinstance(attachment_id, str) or not attachment_id:
            raise _fail("invalid_attachments", "attachment id must be non-empty")
        media_type = _DEFAULT_MEDIA_TYPE
        payload = attachment
        if isinstance(attachment, tuple) and len(attachment) == 2:
            media_type, payload = attachment
        if not isinstance(media_type, str) or not media_type or "/" not in media_type:
            raise _fail("invalid_attachments", "attachment media type is invalid")
        if not isinstance(payload, bytes):
            raise _fail("invalid_attachments", "attachment payload must be bytes")
        normalized[attachment_id] = (media_type, payload)
    if len(normalized) > MAX_ATTACHMENTS:
        raise _fail("too_many_attachments", "attachment count exceeds runtime bound")
    return normalized, {}


def _descriptors_from_inputs(attachments: Mapping[str, Tuple[str, bytes]]) -> Tuple[list, bytes]:
    descriptors = []
    payloads = []
    total = 0
    for attachment_id in sorted(attachments):
        media_type, payload = attachments[attachment_id]
        total += len(payload)
        if total > MAX_ATTACHMENT_BYTES:
            raise _fail("attachment_too_large", "attachment payload exceeds runtime bound")
        descriptor = AttachmentDescriptor(
            attachment_id,
            media_type,
            len(payload),
            hashlib.sha256(payload).hexdigest(),
        )
        descriptors.append(descriptor.to_json_value())
        payloads.append(payload)
    return descriptors, b"".join(payloads)


def _parse_header(encoded_header: bytes, declared_attachments: int) -> Tuple[Dict[str, object], Tuple[AttachmentDescriptor, ...]]:
    header = _decode_json_object(encoded_header)
    descriptor_values = header.pop("_attachments", [])
    if not isinstance(descriptor_values, list) or len(descriptor_values) > MAX_ATTACHMENTS:
        raise _fail("invalid_attachments", "attachment descriptor list is invalid")
    descriptors = []
    previous_id: Optional[str] = None
    total = 0
    for value in descriptor_values:
        try:
            descriptor = AttachmentDescriptor.from_json_value(value)
        except ContractError as exc:
            raise _fail("invalid_attachments", "attachment descriptor is invalid") from exc
        if previous_id is not None and descriptor.id <= previous_id:
            raise _fail("invalid_attachments", "attachment descriptors must be unique and sorted")
        previous_id = descriptor.id
        total += descriptor.length
        if total > declared_attachments:
            raise _fail("invalid_attachments", "attachment descriptors exceed declared bytes")
        descriptors.append(descriptor)
    if total != declared_attachments:
        raise _fail("invalid_attachments", "attachment descriptors do not cover declared bytes")
    try:
        normalized = normalize_message(header)
    except ContractError as exc:
        raise _fail("invalid_envelope", "logical message is invalid") from exc
    return normalized, tuple(descriptors)


def _attach(message: Dict[str, object], descriptors: Tuple[AttachmentDescriptor, ...], payload: bytes) -> Dict[str, object]:
    attachments: Dict[str, bytes] = {}
    media_types: Dict[str, str] = {}
    offset = 0
    for descriptor in descriptors:
        end = offset + descriptor.length
        attachment = payload[offset:end]
        if hashlib.sha256(attachment).hexdigest() != descriptor.sha256:
            raise _fail("checksum_mismatch", "attachment checksum does not match")
        attachments[descriptor.id] = attachment
        media_types[descriptor.id] = descriptor.media_type
        offset = end
    if offset != len(payload):
        raise _fail("invalid_attachments", "unclaimed attachment bytes remain")
    if descriptors:
        message["_attachments"] = attachments
        message["_attachment_media_types"] = media_types
    return message


class FrameCodec:
    """Codec 1: canonical UTF-8 JSON header plus bounded raw attachments."""

    def encode(self, message: Union[LogicalMessage, Mapping[str, object]], attachments: Optional[Mapping[str, object]] = None) -> bytes:
        if isinstance(message, LogicalMessage):
            message_value = message.to_json_value()
        elif isinstance(message, Mapping):
            message_value = dict(message)
        else:
            raise _fail("invalid_envelope", "message must be an object")
        if attachments is None:
            attachments = message_value.pop("_attachments", {})
            media_types = message_value.pop("_attachment_media_types", None)
            if media_types is not None:
                if not isinstance(media_types, Mapping) or not isinstance(attachments, Mapping):
                    raise _fail("invalid_attachments", "carrier media metadata is invalid")
                if set(media_types) != set(attachments):
                    raise _fail("invalid_attachments", "carrier media metadata does not cover attachments")
                attachments = {
                    attachment_id: (media_types[attachment_id], attachment)
                    for attachment_id, attachment in attachments.items()
                }
        elif "_attachments" in message_value:
            raise _fail("invalid_attachments", "attachments supplied twice")
        elif "_attachment_media_types" in message_value:
            raise _fail("invalid_envelope", "carrier media metadata is reserved")
        try:
            normalized = normalize_message(message_value)
        except ContractError as exc:
            raise _fail("invalid_envelope", "logical message is invalid") from exc
        attachment_inputs, _ = _attachment_inputs(attachments)
        descriptors, payload = _descriptors_from_inputs(attachment_inputs)
        header_value = dict(normalized)
        if descriptors:
            header_value["_attachments"] = descriptors
        header = _encode_json_object(header_value)
        if len(header) > MAX_HEADER_BYTES:
            raise _fail("header_too_large", "header exceeds runtime bound")
        return PREFIX.pack(MAGIC, PROTOCOL_VERSION, CODEC_CANONICAL_JSON, 0, len(header), len(payload)) + header + payload

    def decode(self, frame: bytes) -> Dict[str, object]:
        if not isinstance(frame, bytes) or len(frame) < PREFIX.size:
            raise _fail("unexpected_eof", "frame prefix is truncated")
        header_length, attachment_length = _validate_prefix(frame[:PREFIX.size])
        expected = PREFIX.size + header_length + attachment_length
        if len(frame) != expected:
            raise _fail("unexpected_eof", "frame length does not match prefix")
        header_start = PREFIX.size
        header_end = header_start + header_length
        message, descriptors = _parse_header(frame[header_start:header_end], attachment_length)
        return _attach(message, descriptors, frame[header_end:])

    def receive(self, stream: Any) -> Dict[str, object]:
        prefix = receive_exact(stream, PREFIX.size)
        header_length, attachment_length = _validate_prefix(prefix)
        header = receive_exact(stream, header_length)
        message, descriptors = _parse_header(header, attachment_length)
        payload = receive_exact(stream, attachment_length)
        return _attach(message, descriptors, payload)

    def send(self, stream: Any, message: Union[LogicalMessage, Mapping[str, object]], attachments: Optional[Mapping[str, object]] = None) -> None:
        stream.sendall(self.encode(message, attachments))


def receive_exact(stream: Any, size: int) -> bytes:
    """Read exactly ``size`` bytes without a one-``recv`` assumption."""
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.recv(remaining)
        if not chunk:
            raise _fail("unexpected_eof", "stream ended before frame completion")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


_DEFAULT_CODEC = FrameCodec()


def encode_frame(message: Union[LogicalMessage, Mapping[str, object]]) -> bytes:
    """Compatibility wrapper for callers that carry raw attachments in the mapping."""
    return _DEFAULT_CODEC.encode(message)


def decode_frame(frame: bytes) -> Dict[str, object]:
    """Compatibility wrapper for one complete received frame."""
    return _DEFAULT_CODEC.decode(frame)


def receive_frame(stream: Any) -> Dict[str, object]:
    """Compatibility wrapper for a stream-carried frame."""
    return _DEFAULT_CODEC.receive(stream)


def send_frame(stream: Any, message: Union[LogicalMessage, Mapping[str, object]]) -> None:
    """Compatibility wrapper that always relies on ``sendall``."""
    _DEFAULT_CODEC.send(stream, message)
