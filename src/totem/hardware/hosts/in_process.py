"""Explicit opt-in in-process implementation of the driver host contract.

This adapter deliberately shares the framed logical boundary used by the
process host.  It cannot force-stop Python provider code: a deadline first
signals cooperative cancellation and then, if the invocation is still live,
contaminates the binding until a controlled daemon restart.
"""

from __future__ import annotations

import importlib
import inspect
import threading
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from totem.hardware.capabilities.display import DisplayHandle
from totem.hardware.runtime.broker import ClaimRecord

from .base import DriverHost
from .protocol import FrameCodec, ProtocolError
from .worker import _dispatch


class InProcessHostError(TimeoutError):
    """A stable host failure that never implies an invocation was killed."""


class _CancelableProvider:
    """Pass a cancellation event only to providers that explicitly accept it."""

    def __init__(self, provider: object, cancellation: threading.Event) -> None:
        self._provider = provider
        self._cancellation = cancellation

    def write_frame(self, request: object) -> object:
        method = getattr(self._provider, "write_frame")
        try:
            accepts_cancel = "cancel_event" in inspect.signature(method).parameters
        except (TypeError, ValueError):
            accepts_cancel = False
        if accepts_cancel:
            return method(request, cancel_event=self._cancellation)
        return method(request)

    def snapshot(self) -> object:
        """Forward read-only power telemetry through the same host boundary."""

        return getattr(self._provider, "snapshot")()

    def telemetry_push(self) -> object:
        """Forward typed power telemetry events through the same boundary."""

        return getattr(self._provider, "telemetry_push")()

    def read(self, *args: object) -> object:
        """Forward NFC or storage reads through the same logical host boundary."""

        return getattr(self._provider, "read")(*args)

    def write(self, *args: object) -> object:
        """Forward NFC or storage writes through the same logical host boundary."""

        return getattr(self._provider, "write")(*args)

    def poll(self) -> object:
        """Forward one NFC presence poll through the same host boundary."""

        return getattr(self._provider, "poll")()

    def list(self, path: str) -> object:
        """Forward one validated storage list through the same host boundary."""

        return getattr(self._provider, "list")(path)

    def delete(self, path: str) -> object:
        """Forward one validated storage deletion through the same host boundary."""

        return getattr(self._provider, "delete")(path)

    def scan(self) -> object:
        return getattr(self._provider, "scan")()

    def connect(self, address_or_ssid: str, password: Optional[str] = None) -> object:
        if password is None:
            return getattr(self._provider, "connect")(address_or_ssid)
        return getattr(self._provider, "connect")(address_or_ssid, password)

    def disconnect(self) -> object:
        return getattr(self._provider, "disconnect")()

    def create_hotspot(self, ssid: str, password: str = "") -> object:
        return getattr(self._provider, "create_hotspot")(ssid, password)

    def discover(self) -> object:
        return getattr(self._provider, "discover")()

    def advertise(self, name: str) -> object:
        return getattr(self._provider, "advertise")(name)



class InProcessDriverHost(DriverHost):
    """Same logical host contract with honest cooperative-only cancellation."""

    def __init__(
        self,
        claims: Sequence[ClaimRecord],
        provider: object,
        *,
        generation: int,
        cancellation_grace: float = 0.1,
    ) -> None:
        if not claims:
            raise ValueError("in-process host requires one claimed binding")
        if cancellation_grace < 0:
            raise ValueError("cancellation grace must not be negative")
        self._claims = tuple(claims)
        self._claims_by_binding = {claim.binding_id: claim for claim in claims}
        self._provider = provider
        self.generation = generation
        self._cancellation_grace = cancellation_grace
        self._codec = FrameCodec()
        self._lock = threading.Lock()
        self._closed = False
        self._contaminated = False
        self._cancellations = 0
        self._live_thread: Optional[threading.Thread] = None

    @classmethod
    def start_group(
        cls,
        claims: Sequence[ClaimRecord],
        *,
        generation: int,
        cancellation_grace: float = 0.1,
    ) -> "InProcessDriverHost":
        """Import exactly the selected, already-claimed provider entry point."""

        ordered = tuple(claims)
        entry_points = {claim.binding.provider_record.entry_point_value for claim in ordered}
        if len(entry_points) != 1:
            raise ValueError("one in-process group must use one provider entry point")
        module_name, separator, factory_name = next(iter(entry_points)).partition(":")
        if not separator or not module_name or not factory_name:
            raise InProcessHostError("invalid_provider_entry_point")
        module = importlib.import_module(module_name)
        provider = getattr(module, factory_name)()
        return cls(ordered, provider, generation=generation, cancellation_grace=cancellation_grace)

    @property
    def contaminated(self) -> bool:
        return self._contaminated

    def await_ready(self, deadline: float) -> Dict[str, object]:
        if deadline <= 0:
            raise TimeoutError("startup deadline elapsed")
        return {
            "type": "host.ready",
            "generation": self.generation,
            "binding_ids": tuple(sorted(self._claims_by_binding)),
        }

    def display_handle(self, binding_id: str) -> DisplayHandle:
        if binding_id not in self._claims_by_binding:
            raise InProcessHostError("binding is not hosted by this process")
        return DisplayHandle(binding_id, self)

    def request(
        self,
        message: Mapping[str, object],
        attachments: Optional[Mapping[str, object]] = None,
        deadline: Optional[float] = None,
    ) -> Dict[str, object]:
        """Validate the exact carrier value before direct provider dispatch."""

        with self._lock:
            if self._closed:
                raise InProcessHostError("host_unavailable")
            if self._contaminated:
                raise InProcessHostError("contaminated")
            request = self._normalize(message, attachments)
            request_id = request.get("id")
            binding_id = request.get("binding_id")
            if not isinstance(request_id, str) or not request_id:
                raise InProcessHostError("invalid_request")
            if not isinstance(binding_id, str) or binding_id not in self._claims_by_binding:
                raise InProcessHostError("binding_identity_mismatch")
            if deadline is not None and deadline <= 0:
                raise InProcessHostError("deadline_exceeded")
            cancellation = threading.Event()
            outcome: Dict[str, object] = {}

            def invoke() -> None:
                try:
                    outcome["result"] = _dispatch(_CancelableProvider(self._provider, cancellation), request)
                except BaseException:
                    outcome["failed"] = True

            thread = threading.Thread(target=invoke, name="totem-driver-in-process-{}".format(binding_id))
            self._live_thread = thread
            thread.start()
            thread.join(deadline)
            if thread.is_alive():
                self._cancellations += 1
                cancellation.set()
                thread.join(self._cancellation_grace)
                if thread.is_alive():
                    self._contaminated = True
                    raise InProcessHostError("deadline_exceeded_contaminated")
                raise InProcessHostError("deadline_exceeded")
            self._live_thread = None
            if outcome.get("failed"):
                raise InProcessHostError("host_exchange_failed")
            result = outcome.get("result")
            if not isinstance(result, dict) or result.get("id") != request_id:
                raise InProcessHostError("host_result_identity_mismatch")
            result["generation"] = self.generation
            return result

    def _normalize(
        self, message: Mapping[str, object], attachments: Optional[Mapping[str, object]]
    ) -> Dict[str, object]:
        try:
            return self._codec.decode(self._codec.encode(dict(message), attachments=attachments))
        except ProtocolError as exc:
            raise InProcessHostError("invalid_envelope") from exc

    def events(self) -> Iterable[Mapping[str, object]]:
        return ()

    def invalidate_correlations(self) -> None:
        return None

    def terminate(self) -> None:
        """Threads cannot be terminated safely; cancellation is the only signal."""

        return None

    def kill(self) -> None:
        """Threads cannot be killed; contamination preserves that fact."""

        return None

    def wait_for_exit(self, deadline: float) -> bool:
        thread = self._live_thread
        if thread is None:
            return True
        thread.join(max(deadline, 0))
        return not thread.is_alive()

    def close_carrier(self) -> None:
        return None

    def close(self, deadline: Optional[float] = None) -> None:
        """Normal close is idempotent; contamination cannot claim a clean close."""

        del deadline
        if not self._contaminated:
            self._closed = True

    def health(self) -> Dict[str, object]:
        thread = self._live_thread
        return {
            "mode": "in_process",
            "state": "CONTAMINATED" if self._contaminated else ("CLOSED" if self._closed else "READY"),
            "cancellations": self._cancellations,
            "live_invocation": bool(thread is not None and thread.is_alive()),
            "restart_required": self._contaminated,
            "held_leases": tuple(claim.binding_id for claim in self._claims) if self._contaminated else (),
        }
