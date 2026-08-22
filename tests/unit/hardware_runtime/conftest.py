"""Deterministic seams for hardware-runtime unit tests.

These fakes model local protocol and lifecycle behavior only.  They do not open
sockets, sleep, spawn processes, access D-Bus, or allocate Totem hardware.
"""

import ast
import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import pytest


FORBIDDEN_LEGACY_IMPORTS = ("totem.api", "totem.devices", "totem.managers")
_FORBIDDEN_TOP_LEVEL_NAMES = {module.rsplit(".", 1)[-1] for module in FORBIDDEN_LEGACY_IMPORTS}


@dataclass
class FakeClock:
    """Monotonic test clock whose ``sleep`` advances time instead of blocking."""

    now: float = 0.0
    sleep_calls: List[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.now

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> float:
        if seconds < 0:
            raise ValueError("fake clock cannot move backwards")
        self.now += seconds
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.advance(seconds)

    def deadline_after(self, seconds: float) -> float:
        if seconds < 0:
            raise ValueError("deadline duration must not be negative")
        return self.monotonic() + seconds

    @staticmethod
    def exponential_backoff(attempt: int, base: float, maximum: float) -> float:
        if attempt < 0 or base < 0 or maximum < 0:
            raise ValueError("backoff inputs must not be negative")
        return min(base * (2 ** attempt), maximum)


@dataclass
class FakeProcess:
    """Popen-shaped lifecycle double with explicit confirmed-death semantics."""

    terminate_exits: bool = False
    terminate_returncode: int = -15
    kill_returncode: int = -9
    returncode: Optional[int] = None
    actions: List[str] = field(default_factory=list)
    confirmed_dead: bool = False

    def poll(self) -> Optional[int]:
        return self.returncode

    def terminate(self) -> None:
        self.actions.append("terminate")
        if self.terminate_exits:
            self.returncode = self.terminate_returncode

    def kill(self) -> None:
        self.actions.append("kill")
        self.returncode = self.kill_returncode

    def wait(self, timeout: Optional[float] = None) -> int:
        del timeout
        self.actions.append("wait")
        if self.returncode is None:
            raise TimeoutError("fake process is still running")
        self.confirmed_dead = True
        return self.returncode


class FragmentingSocket:
    """In-memory stream socket that deliberately fragments reads and writes."""

    def __init__(
        self,
        incoming: Iterable[bytes] = (),
        recv_sizes: Sequence[int] = (),
        send_sizes: Sequence[int] = (),
    ) -> None:
        self._incoming = bytearray(b"".join(incoming))
        self._recv_sizes = tuple(recv_sizes)
        self._send_sizes = tuple(send_sizes)
        self._recv_index = 0
        self._send_index = 0
        self._sent = bytearray()
        self.send_calls: List[int] = []

    @property
    def sent(self) -> bytes:
        return bytes(self._sent)

    def recv(self, size: int) -> bytes:
        if size < 0:
            raise ValueError("recv size must not be negative")
        if not self._incoming or size == 0:
            return b""
        chunk_size = size
        if self._recv_sizes:
            scheduled = self._recv_sizes[self._recv_index % len(self._recv_sizes)]
            self._recv_index += 1
            chunk_size = min(chunk_size, scheduled)
        chunk_size = min(chunk_size, len(self._incoming))
        result = bytes(self._incoming[:chunk_size])
        del self._incoming[:chunk_size]
        return result

    def send(self, data: bytes) -> int:
        if not data:
            return 0
        chunk_size = len(data)
        if self._send_sizes:
            scheduled = self._send_sizes[self._send_index % len(self._send_sizes)]
            self._send_index += 1
            chunk_size = min(chunk_size, scheduled)
        self._sent.extend(data[:chunk_size])
        self.send_calls.append(chunk_size)
        return chunk_size

    def sendall(self, data: bytes) -> None:
        offset = 0
        while offset < len(data):
            written = self.send(data[offset:])
            if written <= 0:
                raise ConnectionError("fragmenting socket made no write progress")
            offset += written


@dataclass(frozen=True)
class FakeLease:
    resource: str


@dataclass
class FakeBroker:
    """Small in-memory lease broker that fails closed on duplicate ownership."""

    active: Dict[str, FakeLease] = field(default_factory=dict)
    released: List[str] = field(default_factory=list)

    def claim(self, resource: str) -> FakeLease:
        if resource in self.active:
            raise RuntimeError("resource is already leased: {0}".format(resource))
        lease = FakeLease(resource=resource)
        self.active[resource] = lease
        return lease

    def release(self, lease: FakeLease) -> None:
        active = self.active.get(lease.resource)
        if active != lease:
            raise RuntimeError("lease is not active: {0}".format(lease.resource))
        del self.active[lease.resource]
        self.released.append(lease.resource)


@dataclass
class ProviderTranscript:
    """Ordered logical envelopes shared by process and in-process test cases."""

    messages: List[Dict[str, Any]] = field(default_factory=list)

    def record_request(self, message: Dict[str, Any]) -> None:
        self.messages.append(copy.deepcopy(message))

    def record_result(self, message: Dict[str, Any]) -> None:
        self.messages.append(copy.deepcopy(message))


def _is_forbidden_module(module: Optional[str], names: Sequence[ast.alias]) -> Optional[str]:
    if module:
        for forbidden in FORBIDDEN_LEGACY_IMPORTS:
            if module == forbidden or module.startswith(forbidden + "."):
                return forbidden
        if module == "totem":
            for alias in names:
                if alias.name in _FORBIDDEN_TOP_LEVEL_NAMES:
                    return "totem.{0}".format(alias.name)
    return None


def find_hardware_import_violations(hardware_root: Path) -> List[Dict[str, Any]]:
    """Return forbidden legacy ownership imports below a hardware source root."""

    if not hardware_root.exists():
        return []

    violations: List[Dict[str, Any]] = []
    for source_path in sorted(hardware_root.rglob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    forbidden = _is_forbidden_module(alias.name, ())
                    if forbidden:
                        violations.append({"file": source_path, "module": forbidden})
            elif isinstance(node, ast.ImportFrom):
                forbidden = _is_forbidden_module(node.module, node.names)
                if forbidden:
                    violations.append({"file": source_path, "module": forbidden})
    return violations


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def fake_process() -> FakeProcess:
    return FakeProcess()


@pytest.fixture
def fragmenting_socket() -> Callable[..., FragmentingSocket]:
    return FragmentingSocket


@pytest.fixture
def fake_broker() -> FakeBroker:
    return FakeBroker()


@pytest.fixture
def provider_transcript() -> ProviderTranscript:
    return ProviderTranscript()


@pytest.fixture
def hardware_import_violations() -> Callable[[Path], List[Dict[str, Any]]]:
    return find_hardware_import_violations
