#!/usr/bin/env python3
"""Shared provider and two host adapters for Spike 003."""

from __future__ import annotations

import os
import queue
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from nip5d_framed import (
    AttachmentInput,
    BytesReader,
    Frame,
    JsonCodec,
    ProtocolError,
    dispatch,
    encode_frame,
    error_result,
    read_frame,
    send_frame,
)


CRASH_EXIT_CODE = 86
WORKER = Path(__file__).with_name("driver_host_worker.py")

ProviderOutput = List[Tuple[Dict[str, Any], AttachmentInput]]


class ProviderFailure(Exception):
    pass


class ProviderCancelled(Exception):
    pass


def deadline_result(message: Mapping[str, Any]) -> Dict[str, Any]:
    return error_result(
        message, "deadline_exceeded", "operation exceeded its deadline"
    )


def host_crashed_result(message: Mapping[str, Any]) -> Dict[str, Any]:
    return error_result(message, "host_crashed", "driver host exited during request")


class FixtureProvider:
    """One provider implementation used unchanged by both host modes."""

    def __init__(self, emergency_stop: Optional[threading.Event] = None) -> None:
        self.emergency_stop = emergency_stop or threading.Event()

    def handle(self, frame: Frame, cancel: threading.Event) -> ProviderOutput:
        message = frame.message
        message_type = message["type"]
        request_id = message.get("id")

        if message_type == "fixture.echo":
            return [
                (
                    {
                        "type": "fixture.echo.result",
                        "id": request_id,
                        "ok": True,
                        "value": message.get("value"),
                    },
                    {},
                )
            ]

        if message_type == "fixture.fail":
            raise ProviderFailure("fixture requested a provider failure")

        if message_type == "fixture.delay":
            seconds = message.get("seconds", 0)
            if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
                raise ProviderFailure("seconds must be numeric")
            deadline = time.monotonic() + max(0.0, float(seconds))
            while time.monotonic() < deadline:
                if cancel.wait(timeout=min(0.005, max(0.0, deadline - time.monotonic()))):
                    raise ProviderCancelled("cooperative cancellation observed")
            return [
                (
                    {
                        "type": "fixture.delay.result",
                        "id": request_id,
                        "ok": True,
                        "completed": True,
                    },
                    {},
                )
            ]

        if message_type == "fixture.hang":
            # Deliberately ignores the host cancellation event. emergency_stop
            # exists only so the spike can clean up its test thread afterward.
            while not self.emergency_stop.wait(timeout=0.01):
                pass
            raise ProviderCancelled("test-only emergency cleanup")

        if message_type == "fixture.crash":
            os._exit(CRASH_EXIT_CODE)

        return dispatch(frame)


def execute_provider(
    provider: FixtureProvider, frame: Frame, cancel: threading.Event
) -> ProviderOutput:
    message = frame.message
    try:
        return provider.handle(frame, cancel)
    except ProviderFailure as exc:
        return [(error_result(message, "provider_failure", str(exc)), {})]
    except ProviderCancelled as exc:
        return [(error_result(message, "cancelled", str(exc)), {})]
    except Exception:
        # The public error is stable and does not expose a plugin traceback.
        return [
            (
                error_result(message, "provider_exception", "provider raised an exception"),
                {},
            )
        ]


class InProcessHost:
    mode = "in_process"

    def __init__(self, cancellation_grace: float = 0.1) -> None:
        self.codec = JsonCodec()
        self.cancellation_grace = cancellation_grace
        self.emergency_stop = threading.Event()
        self.provider = FixtureProvider(self.emergency_stop)
        self.events: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._request_lock = threading.Lock()
        self._threads: List[threading.Thread] = []
        self.contaminated = False
        self.cooperative_cancellations = 0
        self.uncooperative_timeouts = 0

    def request(
        self,
        message: Mapping[str, Any],
        attachments: Optional[AttachmentInput] = None,
        timeout: float = 1.0,
    ) -> Dict[str, Any]:
        with self._request_lock:
            if self.contaminated:
                return error_result(
                    message,
                    "host_contaminated",
                    "an in-process call is still running; daemon restart required",
                )

            # Deliberately cross the same logical serialization boundary as the
            # process host so Python object identity cannot fork behavior.
            incoming_wire = encode_frame(self.codec, message, attachments)
            incoming = read_frame(BytesReader(incoming_wire), self.codec)
            cancel = threading.Event()
            outcome: "queue.Queue[Tuple[str, Any]]" = queue.Queue(maxsize=1)

            def invoke() -> None:
                try:
                    outcome.put(("outputs", execute_provider(self.provider, incoming, cancel)))
                except Exception as exc:
                    outcome.put(("exception", exc))

            thread = threading.Thread(
                target=invoke,
                name=f"in-process-{message.get('id', 'uncorrelated')}",
                daemon=True,
            )
            self._threads.append(thread)
            thread.start()
            try:
                kind, value = outcome.get(timeout=timeout)
            except queue.Empty:
                cancel.set()
                thread.join(timeout=self.cancellation_grace)
                if thread.is_alive():
                    self.contaminated = True
                    self.uncooperative_timeouts += 1
                else:
                    self.cooperative_cancellations += 1
                return deadline_result(message)

            thread.join(timeout=self.cancellation_grace)
            if kind == "exception":
                raise value
            result: Optional[Dict[str, Any]] = None
            for output_message, output_attachments in value:
                output_wire = encode_frame(self.codec, output_message, output_attachments)
                output = read_frame(BytesReader(output_wire), self.codec).message
                if output.get("id") == message.get("id") and output["type"].endswith(
                    ".result"
                ):
                    result = output
                else:
                    self.events.put(output)
            if result is None:
                raise RuntimeError("provider returned no correlated result")
            return result

    def next_event(self, timeout: float = 1.0) -> Dict[str, Any]:
        return self.events.get(timeout=timeout)

    def stats(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "generation": 1,
            "restarts": 0,
            "contaminated": self.contaminated,
            "cooperative_cancellations": self.cooperative_cancellations,
            "uncooperative_timeouts": self.uncooperative_timeouts,
            "live_invocation_threads": sum(thread.is_alive() for thread in self._threads),
        }

    def close(self) -> None:
        self.emergency_stop.set()
        for thread in self._threads:
            thread.join(timeout=0.5)


class ProcessHost:
    mode = "process"

    def __init__(self) -> None:
        self.codec = JsonCodec()
        self.events: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._pending: Dict[str, Tuple[int, "queue.Queue[Tuple[str, Any]]"]] = {}
        self._pending_lock = threading.Lock()
        self._request_lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._closing = False
        self.process: Optional[subprocess.Popen] = None
        self.stream: Optional[socket.socket] = None
        self.reader: Optional[threading.Thread] = None
        self.generation = 0
        self.restarts = 0
        self.last_exit_code: Optional[int] = None
        self._spawn()

    def _spawn(self) -> None:
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        child.set_inheritable(True)
        command = [sys.executable, str(WORKER), "--fd", str(child.fileno())]
        process = subprocess.Popen(
            command,
            pass_fds=(child.fileno(),),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        child.close()
        parent.settimeout(3.0)
        try:
            ready = read_frame(parent, self.codec).message
        except Exception:
            process.terminate()
            process.wait(timeout=2.0)
            detail = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
            parent.close()
            raise RuntimeError(f"driver host failed to become ready: {detail}")
        if ready.get("type") != "host.ready":
            process.terminate()
            process.wait(timeout=2.0)
            parent.close()
            raise RuntimeError(f"unexpected ready message: {ready!r}")

        parent.settimeout(None)
        self.process = process
        self.stream = parent
        self.generation += 1
        generation = self.generation
        self.reader = threading.Thread(
            target=self._read_loop,
            args=(generation, parent),
            name=f"process-host-reader-{generation}",
            daemon=True,
        )
        self.reader.start()

    def _read_loop(self, generation: int, stream: socket.socket) -> None:
        failure: Optional[BaseException] = None
        try:
            while True:
                message = read_frame(stream, self.codec).message
                request_id = message.get("id")
                delivered = False
                if isinstance(request_id, str) and message["type"].endswith(".result"):
                    with self._pending_lock:
                        pending = self._pending.get(request_id)
                        if pending is not None and pending[0] == generation:
                            self._pending.pop(request_id, None)
                            pending[1].put(("result", message))
                            delivered = True
                if not delivered:
                    self.events.put(message)
        except (OSError, ProtocolError) as exc:
            failure = exc
        finally:
            if not self._closing:
                with self._pending_lock:
                    affected = [
                        (request_id, item)
                        for request_id, item in self._pending.items()
                        if item[0] == generation
                    ]
                    for request_id, item in affected:
                        self._pending.pop(request_id, None)
                        item[1].put(("failed", failure))

    def _stop_child(self) -> None:
        process = self.process
        stream = self.stream
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=0.5)
        if process is not None:
            self.last_exit_code = process.poll()
        if stream is not None:
            try:
                stream.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            stream.close()
        if self.reader is not None and self.reader is not threading.current_thread():
            self.reader.join(timeout=0.5)
        self.process = None
        self.stream = None
        self.reader = None

    def _replace_child(self) -> None:
        self._stop_child()
        self.restarts += 1
        self._spawn()

    def request(
        self,
        message: Mapping[str, Any],
        attachments: Optional[AttachmentInput] = None,
        timeout: float = 1.0,
    ) -> Dict[str, Any]:
        # Encode before registering a pending request so validation failure
        # cannot leak correlation state.
        wire = encode_frame(self.codec, message, attachments)
        request_id = message.get("id")
        if not isinstance(request_id, str):
            raise ProtocolError("invalid_envelope", "host requests require an id")

        with self._request_lock:
            if self.process is None or self.stream is None:
                raise RuntimeError("process host is closed")
            generation = self.generation
            outcome: "queue.Queue[Tuple[str, Any]]" = queue.Queue(maxsize=1)
            with self._pending_lock:
                self._pending[request_id] = (generation, outcome)
            try:
                with self._send_lock:
                    self.stream.sendall(wire)
            except OSError:
                with self._pending_lock:
                    self._pending.pop(request_id, None)
                self._replace_child()
                return host_crashed_result(message)

            try:
                kind, value = outcome.get(timeout=timeout)
            except queue.Empty:
                with self._pending_lock:
                    self._pending.pop(request_id, None)
                exited = self.process.poll() if self.process is not None else None
                self._replace_child()
                if exited is not None:
                    return host_crashed_result(message)
                return deadline_result(message)

            if kind == "failed":
                self._replace_child()
                return host_crashed_result(message)
            return value

    def next_event(self, timeout: float = 1.0) -> Dict[str, Any]:
        return self.events.get(timeout=timeout)

    def stats(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "generation": self.generation,
            "restarts": self.restarts,
            "contaminated": False,
            "last_exit_code": self.last_exit_code,
            "child_alive": self.process is not None and self.process.poll() is None,
        }

    def close(self) -> None:
        if self.process is None:
            return
        try:
            self.request({"type": "host.shutdown", "id": "host-close"}, timeout=0.5)
        except Exception:
            pass
        self._closing = True
        if self.process is not None:
            try:
                self.process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
        self._stop_child()


def run_worker(fd: int) -> int:
    codec = JsonCodec()
    provider = FixtureProvider()
    stream = socket.socket(fileno=fd)
    try:
        send_frame(stream, codec, {"type": "host.ready"})
        while True:
            incoming = read_frame(stream, codec)
            if incoming.message["type"] == "host.shutdown":
                send_frame(
                    stream,
                    codec,
                    {
                        "type": "host.shutdown.result",
                        "id": incoming.message["id"],
                        "ok": True,
                    },
                )
                return 0
            cancel = threading.Event()
            for output_message, output_attachments in execute_provider(
                provider, incoming, cancel
            ):
                send_frame(stream, codec, output_message, output_attachments)
    except (OSError, ProtocolError):
        return 1
    finally:
        stream.close()


def functional_conformance(host: Any) -> Dict[str, Any]:
    checks: List[str] = []
    transcript: List[Dict[str, Any]] = []

    def record(name: str, actual: Dict[str, Any], expected: Dict[str, Any]) -> None:
        assert actual == expected, f"{host.mode} {name}: {actual!r} != {expected!r}"
        checks.append(name)
        transcript.append({"case": name, "message": actual})

    record(
        "nested_json_echo",
        host.request(
            {
                "type": "fixture.echo",
                "id": "echo-1",
                "value": {"items": [1, True, None, "totem"]},
            }
        ),
        {
            "type": "fixture.echo.result",
            "id": "echo-1",
            "ok": True,
            "value": {"items": [1, True, None, "totem"]},
        },
    )

    display_bytes = bytes((index * 31) % 256 for index in range((250 * 122 + 7) // 8))
    display_request = {
        "type": "display.frame.write",
        "id": "display-1",
        "binding": "display-0",
        "frame": {"attachment": "frame-1", "width": 250, "height": 122},
    }
    record(
        "binary_attachment_result",
        host.request(
            display_request,
            {"frame-1": ("application/x-totem-mono-frame", display_bytes)},
        ),
        {
            "type": "display.frame.write.result",
            "id": "display-1",
            "ok": True,
            "accepted_bytes": len(display_bytes),
        },
    )
    record(
        "typed_push",
        host.next_event(),
        {
            "type": "display.refresh.completed",
            "binding": "display-0",
            "cause": {"id": "display-1"},
        },
    )

    record(
        "provider_error",
        host.request({"type": "fixture.fail", "id": "fail-1"}),
        {
            "type": "fixture.fail.result",
            "id": "fail-1",
            "ok": False,
            "error": {
                "code": "provider_failure",
                "message": "fixture requested a provider failure",
            },
        },
    )
    record(
        "unknown_request",
        host.request({"type": "future.capability.get", "id": "unknown-1"}),
        {
            "type": "future.capability.get.result",
            "id": "unknown-1",
            "ok": False,
            "error": {
                "code": "unknown_type",
                "message": "unknown type: future.capability.get",
            },
        },
    )
    record(
        "short_operation",
        host.request(
            {"type": "fixture.delay", "id": "delay-ok", "seconds": 0.01},
            timeout=0.5,
        ),
        {
            "type": "fixture.delay.result",
            "id": "delay-ok",
            "ok": True,
            "completed": True,
        },
    )
    record(
        "deadline_result",
        host.request(
            {"type": "fixture.delay", "id": "delay-timeout", "seconds": 0.5},
            timeout=0.03,
        ),
        {
            "type": "fixture.delay.result",
            "id": "delay-timeout",
            "ok": False,
            "error": {
                "code": "deadline_exceeded",
                "message": "operation exceeded its deadline",
            },
        },
    )
    record(
        "usable_after_cooperative_or_contained_timeout",
        host.request({"type": "fixture.echo", "id": "echo-after", "value": "ready"}),
        {
            "type": "fixture.echo.result",
            "id": "echo-after",
            "ok": True,
            "value": "ready",
        },
    )
    return {"checks": checks, "transcript": transcript, "stats": host.stats()}
