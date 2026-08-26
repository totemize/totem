"""Exact-read Unix stream transport for the bounded driver frame codec."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Union

from totem_driver_api.messages import LogicalMessage

from .protocol import FrameCodec


class UnixFrameStream:
    """A stream adapter that preserves frame boundaries across fragmentation."""

    def __init__(self, stream: Any, codec: Optional[FrameCodec] = None) -> None:
        self._stream = stream
        self._codec = codec or FrameCodec()

    def receive(self) -> dict:
        return self._codec.receive(self._stream)

    def send(self, message: Union[LogicalMessage, Mapping[str, object]], attachments: Optional[Mapping[str, object]] = None) -> None:
        self._codec.send(self._stream, message, attachments)
