"""Phase-level local regression contract for the capability runtime.

This test keeps final architectural checks intentionally thin: detailed
behavior stays in the focused modules it invokes, while this file verifies the
published ownership, import-boundary, compatibility-inventory, and validation
ledger seams together.
"""

from __future__ import annotations

import multiprocessing
from pathlib import Path
import subprocess
import sys

import pytest


pytestmark = pytest.mark.unit

ROOT = Path(__file__).parents[2]
VALIDATION = ROOT / ".planning/phases/HW-01-capability-oriented-hardware-runtime/01-VALIDATION.md"
FOCUSED_CONTRACTS = (
    "tests/unit/hardware_runtime/test_import_boundaries.py",
    "tests/unit/hardware_runtime/test_runtime.py",
    "tests/unit/hardware_runtime/test_process_host.py",
    "tests/unit/hardware_runtime/test_conformance.py",
    "tests/unit/test_api_facades.py",
    "tests/unit/test_manager_facades.py",
    "tests/unit/test_cli_compat.py",
)
COMPATIBILITY_INVENTORY = (
    "tests/unit/test_display_2in13_compat.py",
    "tests/unit/test_display_aux_compat.py",
    "tests/unit/test_wifi_provider_compat.py",
    "tests/unit/test_device_display_power_facades.py",
    "tests/unit/test_device_nfc_storage_facades.py",
    "tests/unit/test_device_radio_facades.py",
    "tests/unit/test_driver_registry.py",
    "tests/unit/test_registry_facade.py",
)


def test_phase1_contracts_keep_one_owner_and_a_one_way_runtime_boundary() -> None:
    runtime_source = (ROOT / "src/totem/hardware/runtime/runtime.py").read_text(encoding="utf-8")
    supervisor_source = (ROOT / "src/totem/hardware/runtime/supervisor.py").read_text(encoding="utf-8")

    assert "class HardwareRuntime" in runtime_source
    assert "_owners" in runtime_source
    assert "totem.hardware.builtin" not in runtime_source
    assert "DeviceManager" not in runtime_source
    assert "device_type" not in supervisor_source
    assert "DriverRegistry" not in supervisor_source


def test_phase1_compatibility_inventory_and_public_contract_remain_present() -> None:
    for relative_path in COMPATIBILITY_INVENTORY:
        assert (ROOT / relative_path).is_file(), relative_path

    runtime_contract = (ROOT / "docs/hardware-driver-runtime.md").read_text(encoding="utf-8")
    benchmark_contract = (ROOT / "docs/hardware-driver-benchmark.md").read_text(encoding="utf-8")
    assert "NIP-5D-shaped" in runtime_contract
    assert "Process isolation" in runtime_contract
    assert "armv6l" in benchmark_contract
    assert "armv7l" in benchmark_contract
    assert "aarch64" in benchmark_contract
    assert "pending explicit allocation" in benchmark_contract


def test_focused_runtime_facade_and_conformance_fixtures_pass_without_leaks() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *FOCUSED_CONTRACTS],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert multiprocessing.active_children() == []


def test_validation_ledger_marks_all_local_commands_green_but_keeps_pi_manual() -> None:
    validation = VALIDATION.read_text(encoding="utf-8")

    assert "nyquist_compliant: true" in validation
    assert "wave_0_complete: true" in validation
    assert "| pending" not in validation
    assert "Pi/cutover remain deferred" in validation
    assert "Controller-only results never satisfy either row" in validation
