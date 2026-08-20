"""Continuous post-boot state reconciliation and presentation scheduling.

SSE is intentionally only a wake-up signal.  Every notification, reconnect,
and periodic timer is followed by fresh ``totem.status.get``,
``totem.peers.get``, DeviceManager health, and UPS reads before a scene is
selected.  This mirrors the lossy bus contract and keeps presentation from
becoming state authority.
"""

import asyncio
import json
import os
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
)
from urllib import error, request
from urllib.parse import urlsplit

from PIL import Image

from totem.logging import logger
from totem.screen.display import DeviceManagerDisplay
from totem.screen.model import (
    DEFAULT_SCENE_SPECS,
    SCENE_SEQUENCES,
    PeerSnapshot,
    PowerSnapshot,
    RuntimeFrame,
    RuntimeScene,
    RuntimeSnapshot,
    SceneSpec,
)
from totem.screen.render import FrameRenderer

SceneToken = Tuple[str, str, int, str]


class SnapshotUnavailable(RuntimeError):
    """The authoritative control-plane snapshot could not be reconciled."""


@dataclass(frozen=True)
class RuntimePolicy:
    """Configurable scheduling and power-presentation policy."""

    low_battery_percent: float = 20.0
    critical_battery_percent: float = 8.0
    coalesce_seconds: float = 2.1
    snapshot_poll_seconds: float = 15.0
    reconnect_seconds: float = 2.0
    maximum_pending_scenes: int = 8
    maximum_consumed_tokens: int = 256
    scene_specs: Mapping[RuntimeScene, SceneSpec] = field(
        default_factory=lambda: dict(DEFAULT_SCENE_SPECS)
    )

    def __post_init__(self) -> None:
        if not 0 <= self.critical_battery_percent < self.low_battery_percent <= 100:
            raise ValueError(
                "Battery thresholds must satisfy 0 <= critical < low <= 100"
            )
        if self.coalesce_seconds < 0:
            raise ValueError("Coalescing delay cannot be negative")
        if self.snapshot_poll_seconds <= 0 or self.reconnect_seconds < 0:
            raise ValueError(
                "Polling must be positive and reconnect delay non-negative"
            )
        if self.maximum_pending_scenes < 1:
            raise ValueError("At least one pending scene must be retained")
        if self.maximum_consumed_tokens < self.maximum_pending_scenes:
            raise ValueError(
                "Consumed-token history must fit the complete pending queue"
            )
        if set(self.scene_specs) != set(RuntimeScene):
            raise ValueError("Every and only runtime scenes need scheduling policy")
        for spec in self.scene_specs.values():
            if spec.priority < 0:
                raise ValueError("Scene priority cannot be negative")
            if spec.frame_seconds <= 0 or spec.minimum_dwell < 0:
                raise ValueError("Scene rates must be positive and dwell non-negative")

    def with_frame_rates(self, assignments: Iterable[str]) -> "RuntimePolicy":
        """Return a policy with ``scene=seconds`` frame-rate overrides."""

        specs = dict(self.scene_specs)
        for assignment in assignments:
            name, separator, raw_seconds = assignment.partition("=")
            if not separator:
                raise ValueError("Sequence rates must use scene=seconds")
            try:
                scene = RuntimeScene(name.strip())
                seconds = float(raw_seconds)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    "Invalid sequence rate: {}".format(assignment)
                ) from exc
            if seconds <= 0:
                raise ValueError(
                    "Sequence rate must be positive: {}".format(assignment)
                )
            specs[scene] = replace(specs[scene], frame_seconds=seconds)
        return replace(self, scene_specs=specs)

    def with_minimum_dwells(self, assignments: Iterable[str]) -> "RuntimePolicy":
        """Return a policy with ``scene=seconds`` dwell overrides."""

        specs = dict(self.scene_specs)
        for assignment in assignments:
            name, separator, raw_seconds = assignment.partition("=")
            if not separator:
                raise ValueError("Scene dwells must use scene=seconds")
            try:
                scene = RuntimeScene(name.strip())
                seconds = float(raw_seconds)
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid scene dwell: {}".format(assignment)) from exc
            if seconds < 0:
                raise ValueError(
                    "Scene dwell cannot be negative: {}".format(assignment)
                )
            specs[scene] = replace(specs[scene], minimum_dwell=seconds)
        return replace(self, scene_specs=specs)

    def with_priorities(self, assignments: Iterable[str]) -> "RuntimePolicy":
        """Return a policy with ``scene=integer`` priority overrides."""

        specs = dict(self.scene_specs)
        for assignment in assignments:
            name, separator, raw_priority = assignment.partition("=")
            if not separator:
                raise ValueError("Scene priorities must use scene=integer")
            try:
                scene = RuntimeScene(name.strip())
                priority = int(raw_priority)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    "Invalid scene priority: {}".format(assignment)
                ) from exc
            if priority < 0:
                raise ValueError(
                    "Scene priority cannot be negative: {}".format(assignment)
                )
            specs[scene] = replace(specs[scene], priority=priority)
        return replace(self, scene_specs=specs)


class TotemdBus:
    """Small loopback-only JSON client for authoritative bus snapshots."""

    def __init__(self, bus_url: str = "http://127.0.0.1:8081/bus"):
        parsed = urlsplit(bus_url)
        if parsed.scheme != "http" or not parsed.netloc:
            raise ValueError("totemd bus URL must be an http URL")
        self.bus_url = bus_url
        self.event_address = parsed.netloc
        self._opener = request.build_opener(request.ProxyHandler({}))

    def _request(self, message_type: str) -> Dict[str, Any]:
        payload = json.dumps({"type": message_type, "id": "screen"}).encode("utf-8")
        operation = request.Request(
            self.bus_url,
            data=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        with self._opener.open(operation, timeout=5.0) as response:
            value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict) or value.get("ok") is not True:
            raise SnapshotUnavailable("totemd rejected {}".format(message_type))
        return value

    async def call(self, message_type: str) -> Dict[str, Any]:
        try:
            return await asyncio.to_thread(self._request, message_type)
        except (error.URLError, OSError, TimeoutError, ValueError) as exc:
            raise SnapshotUnavailable(
                "totemd snapshot unavailable: {}".format(message_type)
            ) from exc


class TotemSnapshotClient:
    """Reconcile one orthogonal snapshot from both local authorities."""

    def __init__(self, bus: TotemdBus, display: DeviceManagerDisplay):
        self.bus = bus
        self.display = display

    @staticmethod
    def _count(value: Any, fallback: int = 0) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return fallback
        return max(0, int(value))

    @staticmethod
    def _optional_count(value: Any) -> Optional[int]:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return max(0, int(value))

    @classmethod
    def _peer(cls, value: Any) -> Optional[PeerSnapshot]:
        if not isinstance(value, dict):
            return None
        npub = value.get("npub")
        if not isinstance(npub, str) or not npub:
            return None
        verdict = value.get("probe_verdict")
        sync_state = value.get("sync_state")
        return PeerSnapshot(
            npub=npub,
            encounter=cls._count(value.get("first_seen")),
            probe_verdict=verdict if isinstance(verdict, str) else None,
            recognized=value.get("recognized") is True,
            known_before=value.get("known_before") is True,
            sync_state=sync_state if isinstance(sync_state, str) else None,
            sync_attempt=cls._optional_count(value.get("sync_attempt")),
            present=value.get("present") is not False,
        )

    @staticmethod
    def _power(value: Any) -> PowerSnapshot:
        if not isinstance(value, dict):
            return PowerSnapshot()
        percent = value.get("battery_percent")
        if isinstance(percent, bool) or not isinstance(percent, (int, float)):
            return PowerSnapshot()
        plugged = value.get("power_plugged")
        return PowerSnapshot(
            available=True,
            battery_percent=max(0.0, min(100.0, float(percent))),
            power_plugged=plugged if isinstance(plugged, bool) else None,
        )

    @classmethod
    def _event_counts(cls, value: Any) -> Tuple[Tuple[str, int], ...]:
        if not isinstance(value, dict):
            return ()
        return tuple(
            sorted(
                (name, cls._count(count))
                for name, count in value.items()
                if isinstance(name, str)
                and isinstance(count, (int, float))
                and not isinstance(count, bool)
            )
        )

    async def fetch(self) -> RuntimeSnapshot:
        status_reply, peers_reply, ups, health = await asyncio.gather(
            self.bus.call("totem.status.get"),
            self.bus.call("totem.peers.get"),
            self.display.ups_status(),
            self.display.health(),
        )
        status = status_reply.get("status")
        rows = peers_reply.get("peers")
        if not isinstance(status, dict) or not isinstance(rows, list):
            raise SnapshotUnavailable("totemd returned an incomplete snapshot")

        peers = tuple(
            peer for peer in (self._peer(row) for row in rows) if peer is not None
        )
        live_peers = tuple(peer for peer in peers if peer.present)
        config = status.get("config")
        fips = status.get("fips")
        config = config if isinstance(config, dict) else {}
        fips = fips if isinstance(fips, dict) else {}
        device_name = config.get("device_name")
        managers = (
            health.get("initialized_managers") if isinstance(health, dict) else []
        )
        return RuntimeSnapshot(
            device_name=(
                device_name if isinstance(device_name, str) and device_name else "TOTEM"
            ),
            fips_connected=fips.get("connected") is True,
            mesh_size=self._count(fips.get("mesh_size")),
            # Peer rows and scenes come from one peers.get response.  Derive
            # its badges from those same live rows so a concurrent departure
            # cannot mix a tombstone scene with older status counters.
            peer_count=len(live_peers),
            recognized_count=sum(1 for peer in live_peers if peer.recognized),
            power=self._power(ups),
            peers=peers,
            device_managers=len(managers) if isinstance(managers, list) else 0,
            event_counts=self._event_counts(status.get("events")),
        )


class TotemdEventStream:
    """Follow the official ``totemctl events`` SSE client as notifications."""

    def __init__(
        self,
        executable: str = "totemctl",
        bus_address: Optional[str] = None,
    ):
        self.executable = executable
        self.bus_address = bus_address
        self.process = None

    async def connect(self) -> None:
        environment = None
        if self.bus_address:
            environment = os.environ.copy()
            environment["TOTEMD_BUS_ADDR"] = self.bus_address
        self.process = await asyncio.create_subprocess_exec(
            self.executable,
            "events",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment,
        )
        assert self.process.stderr is not None
        line = await asyncio.wait_for(self.process.stderr.readline(), timeout=5.0)
        if b"connected" not in line.lower():
            raise ConnectionError("totemctl did not subscribe to the event stream")

    @staticmethod
    def parse_line(line: bytes) -> Optional[Dict[str, Any]]:
        text = line.decode("utf-8", errors="replace").strip()
        if not text or text.startswith(":") or text.startswith("event:"):
            return None
        if text.startswith("data:"):
            text = text[5:].lstrip()
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    async def next_event(self) -> Dict[str, Any]:
        if self.process is None or self.process.stdout is None:
            raise ConnectionError("event stream is not connected")
        while True:
            line = await self.process.stdout.readline()
            if not line:
                raise ConnectionError("totemd event stream ended")
            value = self.parse_line(line)
            if value is not None:
                return value

    async def close(self) -> None:
        process = self.process
        self.process = None
        if process is None or process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()


@dataclass(frozen=True)
class SourceUpdate:
    snapshot: RuntimeSnapshot
    notification: Optional[Mapping[str, Any]] = None
    reconnected: bool = False


class RuntimeSource:
    """Reconnect SSE and periodically poll even when no push arrives."""

    def __init__(
        self,
        snapshots: TotemSnapshotClient,
        *,
        stream_factory: Callable[[], TotemdEventStream] = TotemdEventStream,
        poll_seconds: float = 15.0,
        reconnect_seconds: float = 2.0,
    ):
        self.snapshots = snapshots
        self.stream_factory = stream_factory
        self.poll_seconds = poll_seconds
        self.reconnect_seconds = reconnect_seconds

    async def updates(self) -> AsyncIterator[SourceUpdate]:
        while True:
            stream = self.stream_factory()
            event_task = None
            try:
                await stream.connect()
                yield SourceUpdate(await self.snapshots.fetch(), reconnected=True)
                while True:
                    if event_task is None:
                        event_task = asyncio.create_task(stream.next_event())
                    done, _ = await asyncio.wait(
                        {event_task}, timeout=self.poll_seconds
                    )
                    notification = None
                    if done:
                        notification = event_task.result()
                        event_task = None
                    # The notification is only a wake-up.  Always reconcile.
                    yield SourceUpdate(
                        await self.snapshots.fetch(),
                        notification=notification,
                    )
            except asyncio.CancelledError:
                raise
            except (
                ConnectionError,
                SnapshotUnavailable,
                OSError,
                asyncio.TimeoutError,
            ) as exc:
                logger.warning("Screen state source reconnecting: %s", exc)
                await asyncio.sleep(self.reconnect_seconds)
            finally:
                if event_task is not None:
                    event_task.cancel()
                    await asyncio.gather(event_task, return_exceptions=True)
                await stream.close()


@dataclass(frozen=True)
class SceneChoice:
    scene: RuntimeScene
    snapshot: RuntimeSnapshot
    tokens: Tuple[SceneToken, ...] = ()


class ProjectionEngine:
    """Pure-ish snapshot projector with bounded, coalesced transient facts."""

    def __init__(self, policy: RuntimePolicy):
        self.policy = policy
        self._consumed: "OrderedDict[SceneToken, None]" = OrderedDict()
        self._pending: "OrderedDict[SceneToken, RuntimeScene]" = OrderedDict()

    def _consume(self, token: SceneToken) -> None:
        """Remember a payoff without allowing a long-lived process to grow."""

        kind, npub, encounter, _ = token
        sync_kind = kind.startswith("sync_")
        for previous in tuple(self._consumed):
            previous_kind, previous_npub, previous_encounter, _ = previous
            same_axis = previous_kind == kind or (
                sync_kind and previous_kind.startswith("sync_")
            )
            if previous_npub == npub and same_axis and previous_encounter <= encounter:
                self._consumed.pop(previous, None)
        self._consumed.pop(token, None)
        self._consumed[token] = None
        while len(self._consumed) > self.policy.maximum_consumed_tokens:
            self._consumed.popitem(last=False)

    def _prune_consumed(self, snapshot: RuntimeSnapshot) -> None:
        """Drop departed and superseded encounter tokens before reconciliation."""

        encounters = {peer.npub: peer.encounter for peer in snapshot.peers}
        for token in tuple(self._consumed):
            _, npub, encounter, _ = token
            latest = encounters.get(npub)
            if latest is None or encounter < latest:
                self._consumed.pop(token, None)

    @staticmethod
    def _token(peer: PeerSnapshot, kind: str, detail: str = "") -> SceneToken:
        return (kind, peer.npub, peer.encounter, detail)

    def _record_transients(self, snapshot: RuntimeSnapshot) -> None:
        self._prune_consumed(snapshot)
        active: Set[SceneToken] = set()
        for peer in snapshot.peers:
            if peer.present and peer.recognized:
                token = self._token(peer, "recognized")
                active.add(token)
                if token not in self._consumed:
                    scene = (
                        RuntimeScene.RETURNING_RECOGNIZED
                        if peer.known_before
                        else RuntimeScene.NEWLY_RECOGNIZED
                    )
                    self._pending.setdefault(token, scene)

            if peer.present and peer.sync_state == "succeeded":
                detail = str(peer.sync_attempt if peer.sync_attempt is not None else "")
                token = self._token(peer, "sync_succeeded", detail)
                active.add(token)
                if token not in self._consumed:
                    self._pending.setdefault(token, RuntimeScene.SYNC_SUCCEEDED)
            elif peer.sync_state == "cancelled" or (
                peer.present and peer.sync_state == "timed_out"
            ):
                detail = "{}:{}".format(
                    peer.sync_attempt if peer.sync_attempt is not None else "",
                    peer.sync_state,
                )
                token = self._token(peer, "sync_interrupted", detail)
                active.add(token)
                if token not in self._consumed:
                    self._pending.setdefault(token, RuntimeScene.SYNC_INTERRUPTED)

        # A queued payoff remains truthful only while its encounter/result is
        # still present in the newest authoritative peer snapshot.
        for token in tuple(self._pending):
            if token not in active:
                self._pending.pop(token, None)
        while len(self._pending) > self.policy.maximum_pending_scenes:
            token, _ = self._pending.popitem(last=False)
            self._consume(token)

    def seed(self, snapshot: RuntimeSnapshot) -> None:
        """Suppress stale one-shot payoff/result scenes on process startup."""

        for peer in snapshot.peers:
            if peer.present and peer.recognized:
                self._consume(self._token(peer, "recognized"))
            if peer.present and peer.sync_state == "succeeded":
                detail = str(peer.sync_attempt if peer.sync_attempt is not None else "")
                self._consume(self._token(peer, "sync_succeeded", detail))
            elif peer.sync_state == "cancelled" or (
                peer.present and peer.sync_state == "timed_out"
            ):
                detail = "{}:{}".format(
                    peer.sync_attempt if peer.sync_attempt is not None else "",
                    peer.sync_state,
                )
                self._consume(self._token(peer, "sync_interrupted", detail))

    def _persistent_scenes(self, snapshot: RuntimeSnapshot) -> List[RuntimeScene]:
        scenes: List[RuntimeScene] = []
        percent = snapshot.power.battery_percent
        if snapshot.power.available and percent is not None:
            if percent <= self.policy.critical_battery_percent:
                scenes.append(RuntimeScene.CRITICAL_BATTERY)

        if any(
            peer.present and peer.sync_state == "running" for peer in snapshot.peers
        ):
            scenes.append(RuntimeScene.SYNC_RUNNING)
        if any(
            peer.present and peer.probe_verdict == "candidate" and not peer.recognized
            for peer in snapshot.peers
        ):
            scenes.append(RuntimeScene.CANDIDATE)
        if any(
            peer.present and peer.probe_verdict is None and not peer.recognized
            for peer in snapshot.peers
        ):
            scenes.append(RuntimeScene.PEER_SEEN)

        if (
            snapshot.power.available
            and percent is not None
            and self.policy.critical_battery_percent
            < percent
            <= self.policy.low_battery_percent
        ):
            scenes.append(RuntimeScene.LOW_BATTERY)
        if any(
            peer.present and peer.probe_verdict == "not_totem"
            for peer in snapshot.peers
        ):
            scenes.append(RuntimeScene.NON_TOTEM_PEER)
        if snapshot.power.available and snapshot.power.power_plugged is True:
            scenes.append(RuntimeScene.CHARGING)
        if not snapshot.fips_connected:
            scenes.append(RuntimeScene.MESH_DEGRADED)
        scenes.append(RuntimeScene.ALONE_IDLE)
        return scenes

    def select(self, snapshot: RuntimeSnapshot) -> SceneChoice:
        self._record_transients(snapshot)
        candidates: List[Tuple[int, int, RuntimeScene, Tuple[SceneToken, ...]]] = []
        for order, scene in enumerate(self._persistent_scenes(snapshot)):
            candidates.append(
                (self.policy.scene_specs[scene].priority, -order, scene, ())
            )
        for order, (token, scene) in enumerate(self._pending.items()):
            candidates.append(
                (
                    self.policy.scene_specs[scene].priority,
                    -1000 - order,
                    scene,
                    (token,),
                )
            )
        _, _, winner, tokens = max(candidates, key=lambda item: (item[0], item[1]))
        if tokens:
            # Coalesce simultaneous activity of the same class into one frame.
            tokens = tuple(
                token for token, scene in self._pending.items() if scene == winner
            )
        return SceneChoice(winner, snapshot, tokens)

    def mark_presented(self, choice: SceneChoice) -> None:
        for token in choice.tokens:
            self._pending.pop(token, None)
            self._consume(token)


class SceneArbitrator:
    """Apply quiet-time coalescing, priority preemption, and minimum dwell."""

    def __init__(self, projector: ProjectionEngine, policy: RuntimePolicy):
        self.projector = projector
        self.policy = policy
        self.latest: Optional[RuntimeSnapshot] = None
        self.last_submit = 0.0
        self.current: Optional[SceneChoice] = None
        self.entered_at = 0.0

    def submit(self, snapshot: RuntimeSnapshot, now: float) -> None:
        if self.latest is None:
            self.projector.seed(snapshot)
        self.latest = snapshot
        self.last_submit = now

    def _activate(self, choice: SceneChoice, now: float) -> SceneChoice:
        self.current = choice
        self.entered_at = now
        return choice

    def mark_presented(self, choice: SceneChoice) -> None:
        """Commit one-shot facts only after a successful display submission."""

        self.projector.mark_presented(choice)

    @staticmethod
    def _same_choice(current: SceneChoice, candidate: SceneChoice) -> bool:
        return candidate.scene == current.scene and (
            not candidate.tokens or candidate.tokens == current.tokens
        )

    def resolve(self, now: float) -> Optional[SceneChoice]:
        if self.latest is None:
            return None
        candidate = self.projector.select(self.latest)
        candidate_spec = self.policy.scene_specs[candidate.scene]
        quiet = now >= self.last_submit + self.policy.coalesce_seconds

        if self.current is None:
            if quiet or candidate_spec.priority >= 100:
                return self._activate(candidate, now)
            return None

        current_spec = self.policy.scene_specs[self.current.scene]
        if self._same_choice(self.current, candidate):
            self.current = replace(self.current, snapshot=self.latest)
            return self.current

        urgent = candidate_spec.priority >= 100
        priority_preemption = candidate_spec.priority > current_spec.priority
        dwelled = now >= self.entered_at + current_spec.minimum_dwell
        if urgent or (quiet and (dwelled or priority_preemption)):
            return self._activate(candidate, now)
        self.current = replace(self.current, snapshot=self.latest)
        return self.current

    def resolution_deadline(self) -> Optional[float]:
        if self.latest is None:
            return None
        quiet_at = self.last_submit + self.policy.coalesce_seconds
        if self.current is None:
            return quiet_at
        candidate = self.projector.select(self.latest)
        if self._same_choice(self.current, candidate):
            return None
        current_spec = self.policy.scene_specs[self.current.scene]
        candidate_spec = self.policy.scene_specs[candidate.scene]
        if candidate_spec.priority > current_spec.priority:
            return quiet_at
        return max(quiet_at, self.entered_at + current_spec.minimum_dwell)


class RuntimeController:
    """Animate the selected scene while coalescing authoritative updates."""

    def __init__(
        self,
        display: DeviceManagerDisplay,
        renderer: FrameRenderer,
        policy: Optional[RuntimePolicy] = None,
    ):
        self.display = display
        self.renderer = renderer
        self.policy = policy or RuntimePolicy()
        self.projector = ProjectionEngine(self.policy)
        self.arbitrator = SceneArbitrator(self.projector, self.policy)

    @staticmethod
    def _presentation_signature(snapshot: RuntimeSnapshot) -> Tuple[Any, ...]:
        percent = snapshot.power.battery_percent
        battery_fill = None if percent is None else round(21 * percent / 100)
        return (
            snapshot.device_name,
            snapshot.fips_connected,
            battery_fill,
            snapshot.power.available,
            snapshot.power.power_plugged,
            snapshot.mesh_size,
            snapshot.peer_count,
            snapshot.recognized_count,
        )

    @staticmethod
    def _advance_index(sequence: Sequence[str], index: int) -> int:
        following = (index + 1) % len(sequence)
        if following == 0 and len(sequence) > 1 and sequence[-1] == sequence[0]:
            return 1
        return following

    async def _produce(self, source: RuntimeSource, queue: asyncio.Queue) -> None:
        async for update in source.updates():
            if update.notification:
                logger.debug(
                    "Screen notification %s; reconciling snapshot",
                    update.notification.get("type", "unknown"),
                )
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(update.snapshot)

    async def run(self, source: RuntimeSource, stop: asyncio.Event) -> None:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        producer = asyncio.create_task(self._produce(source, queue))
        loop = asyncio.get_running_loop()
        active_key = None
        active_signature = None
        sequence_index = 0
        next_frame_at: Optional[float] = None
        last_frame_at: Optional[float] = None
        first_runtime_frame = True
        try:
            while not stop.is_set():
                now = loop.time()
                choice = self.arbitrator.resolve(now)
                if choice is not None:
                    key = (choice.scene, choice.tokens)
                    if key != active_key:
                        active_key = key
                        active_signature = self._presentation_signature(choice.snapshot)
                        sequence_index = 0
                        next_frame_at = now
                    else:
                        signature = self._presentation_signature(choice.snapshot)
                        if signature != active_signature:
                            active_signature = signature
                            if next_frame_at is None:
                                earliest = now
                                if last_frame_at is not None:
                                    earliest = max(
                                        earliest,
                                        last_frame_at
                                        + self.policy.scene_specs[
                                            choice.scene
                                        ].frame_seconds,
                                    )
                                next_frame_at = earliest

                    sequence = SCENE_SEQUENCES[choice.scene]
                    if next_frame_at is not None and now >= next_frame_at:
                        expression = sequence[sequence_index]
                        frame = RuntimeFrame(
                            choice.scene,
                            expression,
                            sequence_index,
                            choice.snapshot,
                        )
                        logger.info(
                            "Screen runtime frame: %s %d/%d %s",
                            choice.scene.value,
                            sequence_index + 1,
                            len(sequence),
                            expression,
                        )
                        try:
                            image = self.renderer.render_runtime(frame)
                            await self.display.show(
                                image,
                                refresh_mode=(
                                    "full" if first_runtime_frame else "partial"
                                ),
                            )
                        except Exception as exc:
                            # Keep one-shot tokens pending until the frame
                            # actually crosses the display boundary.  A fresh
                            # process deliberately seeds current tokens as
                            # stale, so ordinary display outages retry here.
                            logger.warning(
                                "Screen runtime frame failed; retrying: %s", exc
                            )
                            next_frame_at = loop.time() + max(
                                0.05, self.policy.reconnect_seconds
                            )
                        else:
                            self.arbitrator.mark_presented(choice)
                            first_runtime_frame = False
                            last_frame_at = loop.time()
                            sequence_index = self._advance_index(
                                sequence, sequence_index
                            )
                            if len(sequence) > 1:
                                next_frame_at = (
                                    loop.time()
                                    + self.policy.scene_specs[
                                        choice.scene
                                    ].frame_seconds
                                )
                            else:
                                next_frame_at = None

                deadlines = [deadline for deadline in (next_frame_at,) if deadline]
                resolution = self.arbitrator.resolution_deadline()
                if resolution is not None:
                    deadlines.append(resolution)
                timeout = None
                if deadlines:
                    timeout = max(0.0, min(deadlines) - loop.time())

                update_task = asyncio.create_task(queue.get())
                stop_task = asyncio.create_task(stop.wait())
                done, pending = await asyncio.wait(
                    {update_task, stop_task, producer},
                    timeout=timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    if task is not producer:
                        task.cancel()
                await asyncio.gather(
                    *(task for task in pending if task is not producer),
                    return_exceptions=True,
                )
                if producer in done:
                    producer.result()
                    raise RuntimeError("Screen state source ended unexpectedly")
                if stop_task in done and stop_task.result():
                    break
                if update_task in done:
                    self.arbitrator.submit(update_task.result(), loop.time())
        finally:
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)

    async def replay_all_states(
        self,
        snapshot: RuntimeSnapshot,
        *,
        frame_seconds: float = 2.0,
        atlas_output: Optional[str] = None,
    ) -> None:
        """Render every exact runtime frame in catalog order for proofing."""

        if frame_seconds < 0:
            raise ValueError("Replay frame dwell cannot be negative")
        await self.display.wait_ready()
        total = sum(len(SCENE_SEQUENCES[scene]) for scene in RuntimeScene)
        ordinal = 0
        rendered: List[Image.Image] = []
        first_runtime_frame = True
        for scene in RuntimeScene:
            sequence = SCENE_SEQUENCES[scene]
            for index, expression in enumerate(sequence):
                ordinal += 1
                logger.info(
                    "Screen replay frame: %d/%d %s %d/%d %s",
                    ordinal,
                    total,
                    scene.value,
                    index + 1,
                    len(sequence),
                    expression,
                )
                image = self.renderer.render_runtime(
                    RuntimeFrame(scene, expression, index, snapshot)
                )
                rendered.append(image)
                await self.display.show(
                    image,
                    refresh_mode=("full" if first_runtime_frame else "partial"),
                )
                first_runtime_frame = False
                if frame_seconds:
                    await asyncio.sleep(frame_seconds)
        if atlas_output:
            columns = 4
            rows = (len(rendered) + columns - 1) // columns
            atlas = Image.new(
                "1",
                (self.renderer.width * columns, self.renderer.height * rows),
                255,
            )
            for index, image in enumerate(rendered):
                atlas.paste(
                    image,
                    (
                        (index % columns) * self.renderer.width,
                        (index // columns) * self.renderer.height,
                    ),
                )
            output = Path(atlas_output)
            output.parent.mkdir(parents=True, exist_ok=True)
            atlas.save(str(output), format="PNG")
            logger.info("Screen replay atlas: %s", output)


def synthetic_snapshot(device_name: str = "TOTEM") -> RuntimeSnapshot:
    """A visually populated but explicitly synthetic replay snapshot."""

    return RuntimeSnapshot(
        device_name=device_name,
        fips_connected=True,
        mesh_size=12,
        peer_count=3,
        recognized_count=2,
        power=PowerSnapshot(True, 75.0, False),
    )
