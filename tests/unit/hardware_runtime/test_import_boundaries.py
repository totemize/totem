"""Wave-0 seams stay deterministic and keep canonical ownership one-way."""

from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


def test_fake_clock_advances_deadlines_and_backoff_without_sleep(fake_clock):
    deadline = fake_clock.deadline_after(2.5)

    assert fake_clock.monotonic() == 0.0
    assert fake_clock.exponential_backoff(attempt=3, base=0.25, maximum=1.0) == 1.0

    fake_clock.sleep(2.5)

    assert fake_clock.monotonic() == deadline
    assert fake_clock.sleep_calls == [2.5]


def test_fake_process_records_confirmed_death_ordering(fake_process):
    fake_process.terminate()

    with pytest.raises(TimeoutError):
        fake_process.wait(timeout=0.1)

    fake_process.kill()

    assert fake_process.wait(timeout=0.1) == -9
    assert fake_process.actions == ["terminate", "wait", "kill", "wait"]
    assert fake_process.confirmed_dead


def test_fragmenting_socket_models_one_byte_reads_pipelining_eof_and_partial_writes(
    fragmenting_socket,
):
    socket = fragmenting_socket(
        incoming=[b"first", b"second"], recv_sizes=[1], send_sizes=[2, 1]
    )

    assert b"".join(socket.recv(7) for _ in range(7)) == b"firstse"
    assert socket.recv(7) == b"c"
    assert socket.recv(7) == b"o"
    assert socket.recv(7) == b"n"
    assert socket.recv(7) == b"d"
    assert socket.recv(7) == b""
    socket.sendall(b"abcdef")

    assert socket.sent == b"abcdef"
    assert socket.send_calls == [2, 1, 2, 1]


def test_broker_lease_and_provider_transcript_are_deterministic(
    fake_broker, provider_transcript
):
    lease = fake_broker.claim("display:spi0")
    provider_transcript.record_request({"type": "display.render", "id": "req-1"})
    provider_transcript.record_result(
        {"type": "display.render.result", "id": "req-1", "ok": True}
    )

    assert lease.resource == "display:spi0"
    assert provider_transcript.messages == [
        {"type": "display.render", "id": "req-1"},
        {"type": "display.render.result", "id": "req-1", "ok": True},
    ]
    fake_broker.release(lease)
    assert fake_broker.released == ["display:spi0"]


def test_import_guard_reports_forbidden_importing_file_and_module(
    hardware_import_violations, tmp_path
):
    hardware_root = tmp_path / "src" / "totem" / "hardware"
    hardware_root.mkdir(parents=True)
    violating_file = hardware_root / "provider.py"
    violating_file.write_text("from totem.devices import registry\n", encoding="utf-8")

    violations = hardware_import_violations(hardware_root)

    assert violations == [
        {
            "file": violating_file,
            "module": "totem.devices",
        }
    ]


def test_import_guard_accepts_hardware_modules_without_legacy_owners(
    hardware_import_violations, tmp_path
):
    hardware_root = tmp_path / "src" / "totem" / "hardware"
    hardware_root.mkdir(parents=True)
    (hardware_root / "facts.py").write_text(
        "from totem_driver_api import HardwareFacts\n", encoding="utf-8"
    )

    assert hardware_import_violations(hardware_root) == []


def test_current_hardware_tree_has_no_legacy_owner_imports(hardware_import_violations):
    hardware_root = Path(__file__).resolve().parents[3] / "src" / "totem" / "hardware"

    assert hardware_import_violations(hardware_root) == []
