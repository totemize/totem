"""Minimal default child-process host for one already-claimed binding."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from totem.hardware.capabilities.display import DisplayHandle
from totem.hardware.runtime.broker import ClaimRecord

from .protocol import ProtocolError, receive_frame, send_frame


class HostError(RuntimeError):
    """A child host failed without exposing provider internals."""


class ProcessDriverHost:
    """Spawn an entry-point provider after claim and wait for a bound ready event."""

    def __init__(
        self,
        claim: ClaimRecord,
        process: subprocess.Popen[Any],
        carrier: socket.socket,
        session_id: str,
    ) -> None:
        self._claim = claim
        self._process = process
        self._carrier = carrier
        self._session_id = session_id
        self._lock = threading.Lock()

    @classmethod
    def start(cls, claim: ClaimRecord, *, site_packages: Path) -> "ProcessDriverHost":
        """Start the selected worker and publish only after ``host.ready``."""

        parent, child = socket.socketpair()
        session_id = uuid.uuid4().hex
        source_root = Path(__file__).resolve().parents[4] / "src"
        # The worker receives only the selected fixture/runtime import roots,
        # not the daemon's ambient environment or undeclared file descriptors.
        environment = {
            "PYTHONPATH": os.pathsep.join((str(site_packages), str(source_root))),
            "PYTHONNOUSERSITE": "1",
        }
        command = [
            sys.executable,
            "-m",
            "totem.hardware.hosts.worker",
            "--fd",
            str(child.fileno()),
            "--binding-id",
            claim.binding.binding_id,
            "--entry-point",
            claim.binding.provider_record.entry_point_value,
            "--session-id",
            session_id,
        ]
        try:
            process = subprocess.Popen(
                command,
                pass_fds=(child.fileno(),),
                close_fds=True,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        finally:
            child.close()
        host = cls(claim, process, parent, session_id)
        try:
            ready = receive_frame(parent)
        except (OSError, ProtocolError) as exc:
            host.close()
            raise HostError("host did not become ready") from exc
        if (
            ready.get("type") != "host.ready"
            or ready.get("binding_id") != claim.binding.binding_id
            or ready.get("session_id") != session_id
        ):
            host.close()
            raise HostError("host ready identity mismatch")
        return host

    def display_handle(self, binding_id: str) -> DisplayHandle:
        """Return the narrow handle only for the claimed binding identity."""

        if binding_id != self._claim.binding.binding_id:
            raise HostError("binding is not hosted by this process")
        return DisplayHandle(binding_id, self)

    def request(self, message: Mapping[str, Any]) -> Dict[str, Any]:
        """Round-trip one correlated logical envelope on the session-bound carrier."""

        request_id = message.get("id")
        if not isinstance(request_id, str) or not request_id:
            raise HostError("request id is required")
        if message.get("binding_id") != self._claim.binding.binding_id:
            raise HostError("binding identity mismatch")
        with self._lock:
            if self._process.poll() is not None:
                raise HostError("host is unavailable")
            try:
                send_frame(self._carrier, message)
                result = receive_frame(self._carrier)
            except (OSError, ProtocolError) as exc:
                raise HostError("host exchange failed") from exc
        if (
            result.get("id") != request_id
            or result.get("session_id") != self._session_id
            or result.get("binding_id") != self._claim.binding.binding_id
        ):
            raise HostError("host result identity mismatch")
        result.pop("session_id", None)
        result.pop("binding_id", None)
        return result

    def close(self) -> None:
        """End the tracer child process without releasing broker claims here."""

        try:
            self._carrier.close()
        finally:
            if self._process.poll() is None:
                self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=2)
