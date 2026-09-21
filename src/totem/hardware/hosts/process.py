"""Default external-process host for already-claimed provider bindings."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from totem.hardware.capabilities.display import DisplayHandle
from totem.hardware.runtime.broker import ClaimRecord

from .base import DriverHost
from .protocol import ProtocolError, receive_frame, send_frame


class HostError(RuntimeError):
    """A child host failed without exposing provider internals."""


class ProcessDriverHost(DriverHost):
    """A session/generation-bound process host that never imports a provider."""

    def __init__(self, claims: Sequence[ClaimRecord], process: subprocess.Popen[Any], carrier: socket.socket, session_id: str, generation: int) -> None:
        if not claims:
            raise ValueError("process host requires one claimed binding")
        self._claims = tuple(claims)
        self._claims_by_binding = {claim.binding_id: claim for claim in claims}
        self._process = process
        self._carrier = carrier
        self._session_id = session_id
        self.generation = generation
        self._lock = threading.Lock()
        self._invalidated = False
        self._ready: Optional[Dict[str, object]] = None

    @classmethod
    def start(cls, claim: ClaimRecord, *, site_packages: Path, generation: int = 1, startup_deadline: float = 10.0) -> "ProcessDriverHost":
        """Compatibility entry point for one binding in its own process group."""

        return cls.start_group((claim,), site_packages=site_packages, generation=generation, startup_deadline=startup_deadline)

    @classmethod
    def start_group(
        cls,
        claims: Sequence[ClaimRecord],
        *,
        site_packages: Path,
        generation: int,
        startup_deadline: float = 10.0,
        extra_descriptors: Sequence[int] = (),
    ) -> "ProcessDriverHost":
        """Spawn one provider group and wait for a generation-bound ready event."""

        ordered_claims = tuple(claims)
        if not ordered_claims:
            raise ValueError("process host requires one claimed binding")
        entry_points = {claim.binding.provider_record.entry_point_value for claim in ordered_claims}
        if len(entry_points) != 1:
            raise ValueError("one process group must use one provider entry point")
        parent, child = socket.socketpair()
        session_id = uuid.uuid4().hex
        source_root = Path(__file__).resolve().parents[4] / "src"
        # Do not inherit daemon environment or pass undeclared descriptors.
        environment = {"PYTHONPATH": os.pathsep.join((str(site_packages), str(source_root))), "PYTHONNOUSERSITE": "1"}
        descriptor_fds = tuple(int(descriptor) for descriptor in extra_descriptors)
        bootstrap = json.dumps(
            {
                "bindings": [
                    {
                        "binding_id": claim.binding_id,
                        "capability_id": claim.binding.capability_id,
                        "settings": dict(claim.binding.config),
                        "claims": [resource.to_json_value() for resource in claim.binding.claims],
                    }
                    for claim in ordered_claims
                ],
                "descriptors": list(descriptor_fds),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        command = [
            sys.executable, "-m", "totem.hardware.hosts.worker", "--fd", str(child.fileno()),
            "--entry-point", next(iter(entry_points)), "--session-id", session_id,
            "--generation", str(generation),
            "--bootstrap-json", bootstrap,
        ]
        for claim in ordered_claims:
            command.extend(("--binding-id", claim.binding_id))
        try:
            process = subprocess.Popen(
                command, pass_fds=(child.fileno(),) + descriptor_fds, close_fds=True, env=environment,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        finally:
            child.close()
        host = cls(ordered_claims, process, parent, session_id, generation)
        try:
            host.await_ready(startup_deadline)
        except (OSError, ProtocolError, TimeoutError, HostError) as exc:
            host.close(startup_deadline)
            raise HostError("host did not become ready") from exc
        return host

    def await_ready(self, deadline: float) -> Dict[str, object]:
        """Validate session, generation, and complete binding membership."""

        if self._ready is not None:
            return dict(self._ready)
        if deadline <= 0:
            raise TimeoutError("startup deadline elapsed")
        self._carrier.settimeout(deadline)
        try:
            ready = receive_frame(self._carrier)
        except socket.timeout as exc:
            raise TimeoutError("startup deadline elapsed") from exc
        finally:
            self._carrier.settimeout(None)
        expected = tuple(sorted(self._claims_by_binding))
        actual = ready.get("binding_ids")
        if (
            ready.get("type") != "host.ready" or ready.get("session_id") != self._session_id
            or ready.get("generation") != self.generation or not isinstance(actual, list)
            or tuple(sorted(actual)) != expected
        ):
            raise HostError("host ready identity mismatch")
        self._ready = {"type": "host.ready", "generation": self.generation, "binding_ids": expected}
        return dict(self._ready)

    def display_handle(self, binding_id: str) -> DisplayHandle:
        if binding_id not in self._claims_by_binding:
            raise HostError("binding is not hosted by this process")
        return DisplayHandle(binding_id, self)

    def request(self, message: Mapping[str, object], attachments: Optional[Mapping[str, object]] = None, deadline: Optional[float] = None) -> Dict[str, object]:
        """Round-trip one correlated envelope on the active session/generation."""

        request = dict(message)
        if attachments is not None:
            if "_attachments" in request:
                raise HostError("attachments supplied twice")
            request["_attachments"] = dict(attachments)
        request_id = request.get("id")
        binding_id = request.get("binding_id")
        if not isinstance(request_id, str) or not request_id:
            raise HostError("request id is required")
        if not isinstance(binding_id, str) or binding_id not in self._claims_by_binding:
            raise HostError("binding identity mismatch")
        with self._lock:
            if self._invalidated or self._process.poll() is not None:
                raise HostError("host is unavailable")
            if deadline is not None and deadline <= 0:
                raise TimeoutError("operation deadline elapsed")
            if deadline is not None:
                self._carrier.settimeout(deadline)
            try:
                send_frame(self._carrier, request)
                result = receive_frame(self._carrier)
            except socket.timeout as exc:
                raise TimeoutError("operation deadline elapsed") from exc
            except (OSError, ProtocolError) as exc:
                raise HostError("host exchange failed") from exc
            finally:
                if deadline is not None:
                    self._carrier.settimeout(None)
        if (
            result.get("id") != request_id or result.get("session_id") != self._session_id
            or result.get("binding_id") != binding_id or result.get("generation") != self.generation
        ):
            raise HostError("host result identity mismatch")
        result.pop("session_id", None)
        result.pop("binding_id", None)
        result["generation"] = self.generation
        return result

    def events(self) -> Iterable[Mapping[str, object]]:
        return ()

    def invalidate_correlations(self) -> None:
        with self._lock:
            self._invalidated = True

    def terminate(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()

    def kill(self) -> None:
        if self._process.poll() is None:
            self._process.kill()

    def wait_for_exit(self, deadline: float) -> bool:
        try:
            self._process.wait(timeout=deadline)
        except (subprocess.TimeoutExpired, TimeoutError):
            return False
        return self._process.poll() is not None

    def close_carrier(self) -> None:
        self._carrier.close()

    def close(self, deadline: Optional[float] = None) -> None:
        """Stop a child; only the supervisor may release its resource leases."""

        grace = 2.0 if deadline is None else max(deadline, 0.001)
        self.invalidate_correlations()
        self.terminate()
        if not self.wait_for_exit(grace):
            self.kill()
            self.wait_for_exit(grace)
        self.close_carrier()
