"""Built-in power provider tests using injected, in-memory transports only."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List

import pytest

from totem_driver_api import ResourceClaim
from totem_driver_api.capabilities.power import PowerTelemetrySnapshot
from totem_driver_api.conformance import ConformanceCase, run_host_conformance
from totem.hardware.catalog.metadata import CatalogScanner
from totem.hardware.discovery.facts import HardwareFacts
from totem.hardware.discovery.profiles import DeviceProfile
from totem.hardware.discovery.resolver import ResolutionStatus, Resolver
from totem.hardware.hosts.in_process import InProcessDriverHost
from totem.hardware.hosts.process import ProcessDriverHost
from totem.hardware.runtime.bindings import BindingRecord
from totem.hardware.runtime.broker import ResourceBroker


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


ROOT = Path(__file__).parents[3]
MANIFEST_PATH = ROOT / "src" / "totem" / "hardware" / "builtin" / "power" / "totem-driver-manifest.json"
ENTRY_POINT = "totem.hardware.builtin.power.provider:create_provider"
REQUIRED_CLAIMS = (ResourceClaim("i2c", "1"),)


class _EntryPoint:
    group = "totem.hardware.drivers"
    name = "builtin-power"
    value = ENTRY_POINT


class _Distribution:
    metadata = {"Name": "totem", "Version": "0.2.0"}
    entry_points = (_EntryPoint(),)

    def __init__(self) -> None:
        self.files = (Path("totem/hardware/builtin/power/totem-driver-manifest.json"),)

    def locate_file(self, path: Path) -> Path:
        assert str(path) == "totem/hardware/builtin/power/totem-driver-manifest.json"
        return MANIFEST_PATH


class _RecordingDriver:
    def __init__(self) -> None:
        self.reads = 0

    def get_status(self):
        self.reads += 1
        return SimpleNamespace(
            model="PiSugar 2",
            battery_percent=80.0,
            voltage_volts=4.0,
            current_amps=0.5,
            power_plugged=True,
        )


def _catalog():
    return CatalogScanner(distributions=lambda: (_Distribution(),)).snapshot()


def _facts() -> HardwareFacts:
    return HardwareFacts.from_mapping({"resource.i2c": "1"})


def _profile(address: str = "0x75") -> DeviceProfile:
    return DeviceProfile.from_mapping(
        "bench.power.{}".format(address),
        {
            "components": [
                {
                    "kind": "power",
                    "identifier": "ups",
                    "evidence": {"family": "builtin", "i2c_address": address},
                }
            ]
        },
    )


def _binding() -> BindingRecord:
    return Resolver().resolve(
        _catalog(), facts=_facts(), profile=_profile(), capability_id="power.telemetry@1"
    ).require_binding()


def _request(request_id: str, binding_id: str, message_type: str) -> Dict[str, object]:
    return {"type": message_type, "id": request_id, "binding_id": binding_id}


def test_power_contract_validates_snapshot_and_typed_push() -> None:
    snapshot = PowerTelemetrySnapshot("PiSugar 2", 80.0, 4.0, 0.5, True)

    assert snapshot.to_json_value()["power_plugged"] is True
    assert snapshot.to_push().to_json_value()["type"] == "power.telemetry.push"
    with pytest.raises(ValueError, match="battery_percent"):
        PowerTelemetrySnapshot("PiSugar 2", 101.0, 4.0, 0.5, True)


def test_catalog_reads_power_manifest_without_importing_provider_or_i2c_drivers() -> None:
    for module_name in (
        "totem.hardware.builtin.power.provider",
        "totem.hardware.builtin.power.drivers.pisugar2",
        "totem.hardware.builtin.power.drivers.waveshare_ups_hat_c",
        "smbus",
        "smbus2",
    ):
        importlib.sys.modules.pop(module_name, None)

    catalog = _catalog()

    assert catalog.diagnostics == ()
    assert catalog.records[0].manifest.capabilities[0].identifier == "power.telemetry@1"
    assert catalog.records[0].manifest.factory == ENTRY_POINT
    assert not any(
        name in importlib.sys.modules
        for name in (
            "totem.hardware.builtin.power.provider",
            "totem.hardware.builtin.power.drivers.pisugar2",
            "totem.hardware.builtin.power.drivers.waveshare_ups_hat_c",
            "smbus",
            "smbus2",
        )
    )


def test_profiled_i2c_evidence_resolves_and_claims_before_provider_access() -> None:
    unresolved = Resolver().resolve(_catalog(), facts=_facts(), capability_id="power.telemetry@1")
    selected = Resolver().resolve(
        _catalog(), facts=_facts(), profile=_profile(), capability_id="power.telemetry@1"
    )

    assert unresolved.status is ResolutionStatus.UNAVAILABLE
    assert selected.status is ResolutionStatus.RESOLVED
    assert selected.require_binding().claims == REQUIRED_CLAIMS
    assert "totem.hardware.builtin.power.provider" not in importlib.sys.modules


def test_provider_rejects_missing_claims_or_unknown_hat_before_i2c_access() -> None:
    from totem.hardware.builtin.power.provider import PowerProvider, PowerSelectionError

    driver = _RecordingDriver()
    with pytest.raises(PowerSelectionError, match="claims"):
        PowerProvider(model="pisugar2", driver=driver).snapshot()
    with pytest.raises(PowerSelectionError, match="model"):
        PowerProvider(model="unknown", claims=REQUIRED_CLAIMS, driver=driver).snapshot()

    assert driver.reads == 0


def test_power_provider_has_matching_dual_host_snapshot_and_push_conformance(tmp_path: Path) -> None:
    from totem.hardware.builtin.power.provider import PowerProvider

    binding = _binding()
    claim = ResourceBroker().claim(binding)
    driver = _RecordingDriver()
    cases = (
        ConformanceCase("snapshot", _request("snapshot", claim.binding_id, "power.telemetry.read")),
        ConformanceCase("push", _request("push", claim.binding_id, "power.telemetry.push")),
        ConformanceCase("unknown", _request("unknown", claim.binding_id, "power.unknown")),
    )
    in_process = run_host_conformance(
        lambda: InProcessDriverHost(
            (claim,), PowerProvider(model="pisugar2", claims=REQUIRED_CLAIMS, driver=driver), generation=1
        ),
        cases,
    )

    provider_module = tmp_path / "power_core_fixture.py"
    provider_module.write_text(
        "from totem.hardware.builtin.power.provider import PowerProvider\n"
        "from totem_driver_api import ResourceClaim\n"
        "class Driver:\n"
        "    def get_status(self):\n"
        "        return type('Status', (), {'model': 'PiSugar 2', 'battery_percent': 80.0, "
        "'voltage_volts': 4.0, 'current_amps': 0.5, 'power_plugged': True})()\n"
        "def create_provider():\n"
        "    return PowerProvider(model='pisugar2', claims=(ResourceClaim('i2c', '1'),), driver=Driver())\n",
        encoding="utf-8",
    )
    process_record = SimpleNamespace(
        entry_point_value="power_core_fixture:create_provider",
        provider_id=binding.provider_record.provider_id,
        distribution_version="0.2.0",
        manifest=binding.provider_record.manifest,
    )
    process_binding = BindingRecord(
        binding.capability_id, binding.binding_id, process_record, binding.claims, binding.config
    )
    process_claim = ResourceBroker().claim(process_binding)
    process = run_host_conformance(
        lambda: ProcessDriverHost.start(process_claim, site_packages=tmp_path), cases
    )

    assert in_process.items == process.items
    assert driver.reads == 2


def test_legacy_ups_modules_are_exact_provider_reexports() -> None:
    from totem.devices.ups.drivers.pisugar2 import Driver as LegacyPiSugar
    from totem.devices.ups.drivers.waveshare_ups_hat_c import Driver as LegacyWaveshare
    from totem.hardware.builtin.power.drivers.pisugar2 import Driver as CanonicalPiSugar
    from totem.hardware.builtin.power.drivers.waveshare_ups_hat_c import Driver as CanonicalWaveshare

    assert LegacyPiSugar is CanonicalPiSugar
    assert LegacyWaveshare is CanonicalWaveshare
