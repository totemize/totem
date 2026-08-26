"""Built-in NFC provider tests using injected in-memory NFC transports only."""

from __future__ import annotations

import ast
import base64
import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Dict

import pytest

from totem_driver_api import ResourceClaim
from totem_driver_api.capabilities.nfc import NFC_MAX_PAYLOAD_BYTES, NfcReadResult
from totem_driver_api.conformance import ConformanceCase, run_host_conformance
from totem.hardware.catalog.metadata import CatalogScanner
from totem.hardware.discovery.facts import HardwareFacts
from totem.hardware.discovery.resolver import ResolutionStatus, Resolver
from totem.hardware.hosts.in_process import InProcessDriverHost
from totem.hardware.hosts.process import ProcessDriverHost
from totem.hardware.runtime.bindings import BindingRecord
from totem.hardware.runtime.broker import ResourceBroker


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


ROOT = Path(__file__).parents[3]
MANIFEST_PATH = ROOT / "src" / "totem" / "hardware" / "builtin" / "nfc" / "totem-driver-manifest.json"
ENTRY_POINT = "totem.hardware.builtin.nfc.provider:create_provider"
REQUIRED_CLAIMS = (ResourceClaim("nfc", "reader"),)


class _EntryPoint:
    group = "totem.hardware.drivers"
    name = "builtin-nfc"
    value = ENTRY_POINT


class _Distribution:
    metadata = {"Name": "totem", "Version": "0.2.0"}
    entry_points = (_EntryPoint(),)

    def __init__(self) -> None:
        self.files = (Path("totem/hardware/builtin/nfc/totem-driver-manifest.json"),)

    def locate_file(self, path: Path) -> Path:
        assert str(path) == "totem/hardware/builtin/nfc/totem-driver-manifest.json"
        return MANIFEST_PATH


class _RecordingDriver:
    def __init__(self, data: bytes = b"Mock NFC Card Data") -> None:
        self.data = data
        self.reads = 0
        self.writes = 0
        self.polls = 0

    def init(self) -> None:
        return None

    def read(self) -> bytes:
        self.reads += 1
        return self.data

    def write(self, data: bytes) -> None:
        self.writes += 1
        self.data = data

    def poll(self) -> bool:
        self.polls += 1
        return True


def _catalog():
    return CatalogScanner(distributions=lambda: (_Distribution(),)).snapshot()


def _facts() -> HardwareFacts:
    return HardwareFacts.from_mapping({"nfc.family": "builtin", "resource.nfc": "reader"})


def _binding() -> BindingRecord:
    return Resolver().resolve(_catalog(), facts=_facts(), capability_id="nfc.tag@1").require_binding()


def _request(request_id: str, binding_id: str, message_type: str, **values: object) -> Dict[str, object]:
    return {"type": message_type, "id": request_id, "binding_id": binding_id, **values}


def test_nfc_contract_uses_strict_bounded_json_safe_values() -> None:
    result = NfcReadResult(b"tag-data")

    assert result.to_json_value() == {"data_b64": base64.b64encode(b"tag-data").decode("ascii")}
    with pytest.raises(ValueError, match="payload"):
        NfcReadResult(b"x" * (NFC_MAX_PAYLOAD_BYTES + 1))


def test_catalog_reads_nfc_manifest_without_importing_provider_or_transports() -> None:
    for module_name in (
        "totem.hardware.builtin.nfc.provider",
        "totem.hardware.builtin.nfc.drivers.acr122",
        "totem.hardware.builtin.nfc.drivers.pn532",
    ):
        importlib.sys.modules.pop(module_name, None)

    catalog = _catalog()

    assert catalog.diagnostics == ()
    assert catalog.records[0].manifest.capabilities[0].identifier == "nfc.tag@1"
    assert catalog.records[0].manifest.factory == ENTRY_POINT
    assert not any(
        name in importlib.sys.modules
        for name in (
            "totem.hardware.builtin.nfc.provider",
            "totem.hardware.builtin.nfc.drivers.acr122",
            "totem.hardware.builtin.nfc.drivers.pn532",
        )
    )


def test_exact_usb_evidence_resolves_but_missing_catalog_evidence_does_not() -> None:
    resolved = Resolver().resolve(_catalog(), facts=_facts(), capability_id="nfc.tag@1")
    missing = Resolver().resolve(
        _catalog(), facts=HardwareFacts.from_mapping({"nfc.family": "builtin"}), capability_id="nfc.tag@1"
    )

    assert resolved.status is ResolutionStatus.RESOLVED
    assert resolved.require_binding().claims == REQUIRED_CLAIMS
    assert missing.status is ResolutionStatus.UNAVAILABLE


def test_provider_requires_exact_evidence_unambiguous_selection_and_leases_before_io() -> None:
    from totem.hardware.builtin.nfc.provider import NfcProvider, NfcSelectionError

    driver = _RecordingDriver()
    with pytest.raises(NfcSelectionError, match="claims"):
        NfcProvider(
            model="acr122", usb_vid="04e6", usb_pid="5591", driver=driver
        ).read()
    with pytest.raises(NfcSelectionError, match="ambiguous"):
        NfcProvider(
            model="pn532",
            usb_vid="0483",
            usb_pid="5740",
            serial_port="/dev/ttyS0",
            claims=REQUIRED_CLAIMS,
            driver=driver,
        ).read()
    with pytest.raises(NfcSelectionError, match="mock"):
        NfcProvider(model="mock_nfc", claims=REQUIRED_CLAIMS, driver=driver).read()

    assert driver.reads == 0


def test_mock_behavior_is_explicit_and_preserves_stored_data_semantics() -> None:
    from totem.hardware.builtin.nfc.provider import NfcProvider

    driver = _RecordingDriver()
    provider = NfcProvider(
        model="mock_nfc", explicit_mock=True, claims=REQUIRED_CLAIMS, driver=driver
    )

    assert provider.read().data == b"Mock NFC Card Data"
    provider.write(b"replacement")
    assert provider.read().data == b"replacement"
    assert provider.poll().present is True


def test_provider_rejects_oversized_write_before_transport_io() -> None:
    from totem.hardware.builtin.nfc.provider import NfcProvider

    driver = _RecordingDriver()
    provider = NfcProvider(
        model="mock_nfc", explicit_mock=True, claims=REQUIRED_CLAIMS, driver=driver
    )

    with pytest.raises(ValueError, match="payload"):
        provider.write(b"x" * (NFC_MAX_PAYLOAD_BYTES + 1))
    assert driver.writes == 0


def test_nfc_provider_has_matching_dual_host_read_write_poll_conformance(tmp_path: Path) -> None:
    from totem.hardware.builtin.nfc.provider import NfcProvider

    binding = _binding()
    claim = ResourceBroker().claim(binding)
    driver = _RecordingDriver()
    payload = base64.b64encode(b"new data").decode("ascii")
    cases = (
        ConformanceCase("read", _request("read", claim.binding_id, "nfc.tag.read")),
        ConformanceCase("write", _request("write", claim.binding_id, "nfc.tag.write", data_b64=payload)),
        ConformanceCase("poll", _request("poll", claim.binding_id, "nfc.tag.poll")),
        ConformanceCase("unknown", _request("unknown", claim.binding_id, "nfc.unknown")),
    )
    in_process = run_host_conformance(
        lambda: InProcessDriverHost(
            (claim,),
            NfcProvider(model="mock_nfc", explicit_mock=True, claims=REQUIRED_CLAIMS, driver=driver),
            generation=1,
        ),
        cases,
    )

    provider_module = tmp_path / "nfc_core_fixture.py"
    provider_module.write_text(
        "from totem.hardware.builtin.nfc.provider import NfcProvider\n"
        "from totem_driver_api import ResourceClaim\n"
        "class Driver:\n"
        "    def __init__(self): self.data = b'Mock NFC Card Data'\n"
        "    def init(self): pass\n"
        "    def read(self): return self.data\n"
        "    def write(self, data): self.data = data\n"
        "    def poll(self): return True\n"
        "def create_provider():\n"
        "    return NfcProvider(model='mock_nfc', explicit_mock=True, "
        "claims=(ResourceClaim('nfc', 'reader'),), driver=Driver())\n",
        encoding="utf-8",
    )
    process_record = SimpleNamespace(
        entry_point_value="nfc_core_fixture:create_provider",
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
    assert driver.reads == 1
    assert driver.writes == 1
    assert driver.polls == 1


def test_legacy_nfc_modules_are_exact_provider_reexports() -> None:
    from totem.devices.nfc.drivers.acr122 import Driver as LegacyAcr122
    from totem.devices.nfc.drivers.mock_nfc import Driver as LegacyMock
    from totem.devices.nfc.drivers.pn532 import Driver as LegacyPn532
    from totem.hardware.builtin.nfc.drivers.acr122 import Driver as CanonicalAcr122
    from totem.hardware.builtin.nfc.drivers.mock_nfc import Driver as CanonicalMock
    from totem.hardware.builtin.nfc.drivers.pn532 import Driver as CanonicalPn532

    assert LegacyAcr122 is CanonicalAcr122
    assert LegacyMock is CanonicalMock
    assert LegacyPn532 is CanonicalPn532


def test_legacy_nfc_sources_have_no_registry_or_runtime_ownership() -> None:
    expected = {
        "acr122.py": "totem.hardware.builtin.nfc.drivers.acr122",
        "mock_nfc.py": "totem.hardware.builtin.nfc.drivers.mock_nfc",
        "pn532.py": "totem.hardware.builtin.nfc.drivers.pn532",
    }
    legacy_root = ROOT / "src" / "totem" / "devices" / "nfc" / "drivers"

    for filename, canonical_module in expected.items():
        module = ast.parse((legacy_root / filename).read_text(encoding="utf-8"))
        imports = [node for node in module.body if isinstance(node, ast.ImportFrom)]
        assert len(imports) == 1
        assert imports[0].module == canonical_module
        assert [name.name for name in imports[0].names] == ["Driver"]
        assert not any(
            isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) for node in module.body
        )
