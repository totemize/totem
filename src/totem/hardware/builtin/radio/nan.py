"""Bounded nl80211/iw Wi-Fi Aware discovery lifecycle.

The controller manages NAN discovery functions only.  Peer selection and data
path policy live above this layer, and ordinary payload traffic remains FIPS
UDP over a separately established NAN data interface.
"""

import base64
import binascii
from datetime import datetime, timezone
import re
import subprocess
import threading
from typing import Any, Callable, Dict, Optional, Union
import uuid

from totem.devices.network.errors import (
    InvalidRadioRequestError,
    RadioConflictError,
    RadioOperationError,
    RadioResourceNotFoundError,
)
from totem.devices.network.models import NanDiscoverySession, NanFollowup, NanMatch


_SERVICE_NAME = re.compile(r"^[A-Za-z0-9.-]{1,255}$")
_FUNCTION_RESULT = re.compile(
    r"instance_id:\s*(?P<instance>\d+),\s*cookie:\s*(?P<cookie>0x[0-9a-fA-F]+|\d+)"
)
_MATCH = re.compile(
    r"NAN\(cookie=(?P<cookie>0x[0-9a-fA-F]+|\d+)\):\s*"
    r"(?:DiscoveryResult|Replied),\s*peer_id=(?P<peer>\d+),\s*"
    r"local_id=(?P<local>\d+),\s*peer_mac=(?P<mac>[0-9A-Fa-f:]{17})"
    r"(?:,\s*info=(?P<info>.*))?$"
)
_FOLLOWUP = re.compile(
    r"NAN\(cookie=(?P<cookie>0x[0-9a-fA-F]+|\d+)\):\s*"
    r"FollowUpReceive,\s*peer_id=(?P<peer>\d+),\s*"
    r"local_id=(?P<local>\d+),\s*peer_mac=(?P<mac>[0-9A-Fa-f:]{17})"
    r"(?:,\s*info=(?P<info>.*))?$"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wire_info(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _api_info(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.urlsafe_b64decode(value + padding)
    except (ValueError, binascii.Error):
        decoded = value.encode("utf-8", "replace")
    return base64.b64encode(decoded).decode("ascii")


class NanDiscoveryController:
    """Own one NAN interface and a bounded set of publish/subscribe pairs."""

    def __init__(
        self,
        *,
        phy_name: str,
        interface: str,
        iw_path: str,
        runner: Callable[[list, float], str],
        popen_factory: Callable[..., Any] = subprocess.Popen,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        maximum_sessions: int = 4,
        maximum_followups: int = 128,
    ):
        self.phy_name = phy_name
        self.interface = interface
        self.iw_path = iw_path
        self._runner = runner
        self._popen_factory = popen_factory
        self._event_callback = event_callback
        self.maximum_sessions = maximum_sessions
        self.maximum_followups = max(1, maximum_followups)
        self._sessions: Dict[str, NanDiscoverySession] = {}
        self._matches: Dict[str, NanMatch] = {}
        self._followups: Dict[str, NanFollowup] = {}
        self._timers: Dict[str, threading.Timer] = {}
        self._monitor = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._cluster_started = False
        self._closed = False

    def _run(self, arguments, timeout):
        return self._runner(arguments, timeout)

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        if self._event_callback:
            self._event_callback(event_type, data)

    @staticmethod
    def _function_result(output: str):
        match = _FUNCTION_RESULT.search(output)
        if not match:
            raise RadioOperationError(
                "iw did not return a NAN function instance and cookie"
            )
        return int(match.group("instance")), int(match.group("cookie"), 0)

    def _start_cluster(self, timeout: float) -> None:
        self._run(
            [
                self.iw_path,
                "phy",
                self.phy_name,
                "interface",
                "add",
                self.interface,
                "type",
                "__nan",
            ],
            timeout,
        )
        try:
            self._run(
                [
                    self.iw_path,
                    "dev",
                    self.interface,
                    "nan",
                    "start",
                    "pref",
                    "128",
                    "bands",
                    "2GHz",
                    "5GHz",
                ],
                timeout,
            )
        except Exception:
            self._delete_interface(timeout)
            raise
        self._cluster_started = True
        try:
            self._start_monitor()
        except Exception:
            try:
                self._stop_cluster(timeout)
            except RadioOperationError:
                pass
            raise

    def _start_monitor(self) -> None:
        try:
            self._monitor = self._popen_factory(
                [self.iw_path, "event", "-t"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                errors="surrogateescape",
                bufsize=1,
            )
        except OSError as exc:
            raise RadioOperationError(
                "Could not monitor NAN discovery events: {}".format(exc)
            )
        self._monitor_thread = threading.Thread(
            target=self._monitor_events,
            name="totem-nan-events",
            daemon=True,
        )
        self._monitor_thread.start()

    def _monitor_events(self) -> None:
        monitor = self._monitor
        if monitor is None or monitor.stdout is None:
            return
        for line in monitor.stdout:
            self.process_event_line(line)

    def process_event_line(self, line: str) -> Optional[Union[NanMatch, NanFollowup]]:
        followup = _FOLLOWUP.search(line.rstrip("\n"))
        if followup:
            return self._record_received_followup(followup)
        found = _MATCH.search(line.rstrip("\n"))
        if not found:
            return None
        cookie = int(found.group("cookie"), 0)
        with self._lock:
            session = next(
                (
                    value
                    for value in self._sessions.values()
                    if cookie in (value.publish_cookie, value.subscribe_cookie)
                ),
                None,
            )
            if session is None:
                return None
            peer_address = found.group("mac").lower()
            local_instance_id = int(found.group("local"))
            peer_instance_id = int(found.group("peer"))
            match_id = "{}_{}_{}_{}".format(
                session.id,
                peer_address.replace(":", "_"),
                local_instance_id,
                peer_instance_id,
            )
            model = NanMatch(
                id=match_id,
                session_id=session.id,
                peer_address=peer_address,
                local_instance_id=local_instance_id,
                peer_instance_id=peer_instance_id,
                service_info_base64=_api_info(found.group("info") or ""),
                last_seen_at=_utc_now(),
            )
            is_new = match_id not in self._matches
            self._matches[match_id] = model
        self._emit(
            "wifi_nan_match_found" if is_new else "wifi_nan_match_updated",
            {
                "match_id": model.id,
                "session_id": model.session_id,
                "peer_address": model.peer_address,
            },
        )
        return model

    def _record_received_followup(self, found: re.Match) -> Optional[NanFollowup]:
        cookie = int(found.group("cookie"), 0)
        peer_address = found.group("mac").lower()
        local_instance_id = int(found.group("local"))
        peer_instance_id = int(found.group("peer"))
        with self._lock:
            session = next(
                (
                    value
                    for value in self._sessions.values()
                    if cookie in (value.publish_cookie, value.subscribe_cookie)
                ),
                None,
            )
            if session is None:
                return None
            match = next(
                (
                    value
                    for value in self._matches.values()
                    if value.session_id == session.id
                    and value.peer_address == peer_address
                    and value.local_instance_id == local_instance_id
                    and value.peer_instance_id == peer_instance_id
                ),
                None,
            )
            if match is None:
                return None
            payload = (found.group("info") or "").encode("utf-8", "surrogateescape")
            model = self._append_followup(
                match=match, payload=payload, direction="received"
            )
        self._emit(
            "wifi_nan_followup_received",
            {
                "followup_id": model.id,
                "match_id": model.match_id,
                "session_id": model.session_id,
                "peer_address": model.peer_address,
            },
        )
        return model

    def _append_followup(
        self, *, match: NanMatch, payload: bytes, direction: str
    ) -> NanFollowup:
        model = NanFollowup(
            id=uuid.uuid4().hex,
            session_id=match.session_id,
            match_id=match.id,
            peer_address=match.peer_address,
            local_instance_id=match.local_instance_id,
            peer_instance_id=match.peer_instance_id,
            payload_base64=base64.b64encode(payload).decode("ascii"),
            direction=direction,
            created_at=_utc_now(),
        )
        self._followups[model.id] = model
        while len(self._followups) > self.maximum_followups:
            self._followups.pop(next(iter(self._followups)))
        return model

    @staticmethod
    def _followup_text(payload: bytes) -> str:
        if len(payload) > 255:
            raise InvalidRadioRequestError(
                "NAN follow-up payload must be at most 255 bytes"
            )
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidRadioRequestError(
                "The iw NAN backend supports UTF-8 follow-up payloads only"
            ) from exc
        if "\x00" in text or "\n" in text or "\r" in text:
            raise InvalidRadioRequestError(
                "NAN follow-up payload cannot contain NUL or line breaks"
            )
        return text

    def send_followup(
        self, match_id: str, payload: bytes, timeout: float = 15.0
    ) -> NanFollowup:
        text = self._followup_text(payload)
        with self._lock:
            if self._closed:
                raise RadioOperationError("NAN discovery controller is closed")
            match = self._matches.get(match_id)
            if match is None:
                raise RadioResourceNotFoundError("NAN match was not found")
            session = self._sessions.get(match.session_id)
            if session is None:
                raise RadioResourceNotFoundError("NAN discovery session was not found")
            arguments = [
                self.iw_path,
                "dev",
                self.interface,
                "nan",
                "add_func",
                "type",
                "followup",
                "name",
                session.service_name,
            ]
            if text:
                arguments.extend(["info", text])
            arguments.extend(
                [
                    "flw_up_id",
                    str(match.local_instance_id),
                    "flw_up_req_id",
                    str(match.peer_instance_id),
                    "flw_up_dest",
                    match.peer_address,
                ]
            )
            output = self._run(arguments, timeout)
            self._function_result(output)
            model = self._append_followup(
                match=match, payload=payload, direction="sent"
            )
        self._emit(
            "wifi_nan_followup_sent",
            {
                "followup_id": model.id,
                "match_id": model.match_id,
                "session_id": model.session_id,
                "peer_address": model.peer_address,
            },
        )
        return model

    def list_followups(self, session_id: Optional[str] = None):
        with self._lock:
            if session_id and session_id not in self._sessions:
                raise RadioResourceNotFoundError("NAN discovery session was not found")
            return [
                value
                for value in self._followups.values()
                if session_id is None or value.session_id == session_id
            ]

    def start_session(
        self,
        *,
        service_name: str,
        service_info: bytes = b"",
        duration_seconds: int = 300,
        timeout: float = 15.0,
    ) -> NanDiscoverySession:
        if not _SERVICE_NAME.fullmatch(service_name):
            raise InvalidRadioRequestError(
                "NAN service name must contain only letters, digits, dot, or hyphen"
            )
        if len(service_info) > 191:
            raise InvalidRadioRequestError(
                "NAN service information must be at most 191 bytes"
            )
        if not 1 <= duration_seconds <= 3600:
            raise InvalidRadioRequestError(
                "NAN discovery duration must be between 1 and 3600 seconds"
            )
        with self._lock:
            if self._closed:
                raise RadioOperationError("NAN discovery controller is closed")
            if len(self._sessions) >= self.maximum_sessions:
                raise RadioConflictError("NAN discovery session limit reached")
            first = not self._cluster_started
            if first:
                self._start_cluster(timeout)
            encoded_info = _wire_info(service_info)
            common = ["name", service_name]
            if encoded_info:
                common.extend(["info", encoded_info])
            common.extend(["ttl", str(duration_seconds)])
            try:
                publish_output = self._run(
                    [
                        self.iw_path,
                        "dev",
                        self.interface,
                        "nan",
                        "add_func",
                        "type",
                        "publish",
                        "solicited",
                        "unsolicited",
                    ]
                    + common,
                    timeout,
                )
                _, publish_cookie = self._function_result(publish_output)
            except Exception:
                if first:
                    try:
                        self._stop_cluster(timeout)
                    except RadioOperationError:
                        pass
                raise
            try:
                subscribe_output = self._run(
                    [
                        self.iw_path,
                        "dev",
                        self.interface,
                        "nan",
                        "add_func",
                        "type",
                        "subscribe",
                        "active",
                    ]
                    + common,
                    timeout,
                )
                _, subscribe_cookie = self._function_result(subscribe_output)
            except Exception:
                try:
                    self._remove_function(publish_cookie, timeout)
                except RadioOperationError:
                    pass
                if first:
                    try:
                        self._stop_cluster(timeout)
                    except RadioOperationError:
                        pass
                raise
            session_id = uuid.uuid4().hex
            session = NanDiscoverySession(
                id=session_id,
                interface=self.interface,
                service_name=service_name,
                publish_cookie=publish_cookie,
                subscribe_cookie=subscribe_cookie,
                service_info_base64=base64.b64encode(service_info).decode("ascii"),
                started_at=_utc_now(),
                duration_seconds=duration_seconds,
                active=True,
            )
            self._sessions[session_id] = session
            timer = threading.Timer(
                duration_seconds, self._expire_session, [session_id]
            )
            timer.daemon = True
            self._timers[session_id] = timer
            timer.start()
            return session

    def _remove_function(self, cookie: int, timeout: float) -> None:
        self._run(
            [
                self.iw_path,
                "dev",
                self.interface,
                "nan",
                "rm_func",
                "cookie",
                str(cookie),
            ],
            timeout,
        )

    def _expire_session(self, session_id: str) -> None:
        try:
            self.stop_session(session_id)
        except RadioOperationError:
            pass

    def stop_session(self, session_id: str, timeout: float = 15.0) -> None:
        with self._lock:
            session = self._sessions.pop(session_id, None)
            timer = self._timers.pop(session_id, None)
            if timer:
                timer.cancel()
            if session is None:
                return
            error = None
            for cookie in (session.publish_cookie, session.subscribe_cookie):
                try:
                    self._remove_function(cookie, timeout)
                except RadioOperationError as exc:
                    error = error or exc
            self._matches = {
                key: value
                for key, value in self._matches.items()
                if value.session_id != session_id
            }
            self._followups = {
                key: value
                for key, value in self._followups.items()
                if value.session_id != session_id
            }
            if not self._sessions:
                try:
                    self._stop_cluster(timeout)
                except RadioOperationError as exc:
                    error = error or exc
            if error:
                raise error

    def list_sessions(self):
        with self._lock:
            return list(self._sessions.values())

    def list_matches(self, session_id: Optional[str] = None):
        with self._lock:
            if session_id and session_id not in self._sessions:
                raise RadioResourceNotFoundError("NAN discovery session was not found")
            return [
                value
                for value in self._matches.values()
                if session_id is None or value.session_id == session_id
            ]

    def _stop_monitor(self) -> None:
        monitor = self._monitor
        thread = self._monitor_thread
        self._monitor = None
        self._monitor_thread = None
        if monitor is None:
            return
        monitor.terminate()
        try:
            monitor.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            monitor.kill()
            monitor.wait(timeout=1.0)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def _delete_interface(self, timeout: float) -> None:
        self._run([self.iw_path, "dev", self.interface, "del"], timeout)

    def _stop_cluster(self, timeout: float) -> None:
        self._stop_monitor()
        error = None
        try:
            self._run([self.iw_path, "dev", self.interface, "nan", "stop"], timeout)
        except RadioOperationError as exc:
            error = exc
        try:
            self._delete_interface(timeout)
        except RadioOperationError as exc:
            error = error or exc
        self._cluster_started = False
        if error:
            raise error

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            session_ids = list(self._sessions)
        for session_id in session_ids:
            try:
                self.stop_session(session_id)
            except RadioOperationError:
                pass
        with self._lock:
            if self._cluster_started:
                try:
                    self._stop_cluster(15.0)
                except RadioOperationError:
                    pass
            self._closed = True
