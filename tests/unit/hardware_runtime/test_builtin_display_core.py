"""Display provider core tests using only in-memory transports."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from totem_driver_api import ResourceClaim
from totem_driver_api import DriverManifest
from totem_driver_api.capabilities.display import FrameSinkRequest
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
MANIFEST_PATH = ROOT / "src" / "totem" / "hardware" / "builtin" / "display" / "totem-driver-manifest.json"
ENTRY_POINT = "totem.hardware.builtin.display.provider:create_provider"
REQUIRED_CLAIMS = (
    ResourceClaim("gpio", "bcm:17,18,24,25"),
    ResourceClaim("spi", "spi0.0"),
)


class _EntryPoint:
    group = "totem.hardware.drivers"
    name = "builtin-display"
    value = ENTRY_POINT


class _Distribution:
    metadata = {"Name": "totem", "Version": "0.2.0"}
    entry_points = (_EntryPoint(),)

    def __init__(self) -> None:
        self.files = (Path("totem/hardware/builtin/display/totem-driver-manifest.json"),)

    def locate_file(self, path: Path) -> Path:
        assert str(path) == "totem/hardware/builtin/display/totem-driver-manifest.json"
        return MANIFEST_PATH


class _RecordingTransport:
    def __init__(self) -> None:
        self.requests: List[FrameSinkRequest] = []

    def write_frame(self, request: FrameSinkRequest) -> None:
        self.requests.append(request)


def _catalog():
    return CatalogScanner(distributions=lambda: (_Distribution(),)).snapshot()


def _profile() -> DeviceProfile:
    return DeviceProfile.from_mapping(
        "bench.display.v4",
        {
            "components": [
                {
                    "kind": "display",
                    "identifier": "panel",
                    "evidence": {"variant": "waveshare-2in13-v4"},
                }
            ]
        },
    )


def _facts() -> HardwareFacts:
    return HardwareFacts.from_mapping(
        {
            "resource.gpio": "bcm:17,18,24,25",
            "resource.spi": "spi0.0",
        }
    )


def _binding() -> BindingRecord:
    return Resolver().resolve(
        _catalog(), facts=_facts(), profile=_profile(), capability_id="display.frame-sink@1"
    ).require_binding()


def _request(request_id: str, binding_id: str = "display") -> Dict[str, object]:
    return {
        "type": "display.frame.write",
        "id": request_id,
        "binding_id": binding_id,
        "frame": {"attachment_id": "frame", "width": 250, "height": 122, "pixel_format": "mono1"},
    }


def test_catalog_reads_packaged_manifest_without_importing_provider_or_hardware_modules() -> None:
    for module_name in (
        "totem.hardware.builtin.display.provider",
        "spidev",
        "RPi.GPIO",
        "gpiod",
        "PIL",
    ):
        importlib.sys.modules.pop(module_name, None)

    catalog = _catalog()

    assert catalog.diagnostics == ()
    assert catalog.records[0].manifest.capabilities[0].identifier == "display.frame-sink@1"
    assert catalog.records[0].manifest.factory == ENTRY_POINT
    assert "totem.hardware.builtin.display.provider" not in importlib.sys.modules
    assert not any(name in importlib.sys.modules for name in ("spidev", "RPi.GPIO", "gpiod", "PIL"))


def test_profile_and_complete_claim_facts_select_the_generic_provider_without_io() -> None:
    unresolved = Resolver().resolve(
        _catalog(), facts=_facts(), capability_id="display.frame-sink@1"
    )
    selected = Resolver().resolve(
        _catalog(), facts=_facts(), profile=_profile(), capability_id="display.frame-sink@1"
    )

    assert unresolved.status is ResolutionStatus.UNAVAILABLE
    assert selected.status is ResolutionStatus.RESOLVED
    assert selected.require_binding().claims == REQUIRED_CLAIMS
    assert "totem.hardware.builtin.display.provider" not in importlib.sys.modules


def test_ambiguous_panel_records_do_not_import_or_open_a_transport() -> None:
    first = _catalog().records[0]
    alternate_manifest = DriverManifest.from_json(
        {
            **first.manifest.to_json_value(),
            "provider_id": "alternate.display",
        }
    )
    alternate = type(first)(
        distribution_name="alternate-display",
        distribution_version="1.0.0",
        entry_point_name="alternate-display",
        entry_point_value="alternate.display.provider:create_provider",
        manifest=alternate_manifest,
    )
    ambiguous = Resolver().resolve(
        type(_catalog())(records=(first, alternate), diagnostics=()),
        facts=_facts(),
        profile=_profile(),
        capability_id="display.frame-sink@1",
    )

    assert ambiguous.status is ResolutionStatus.AMBIGUOUS
    assert "totem.hardware.builtin.display.provider" not in importlib.sys.modules


def test_provider_rejects_missing_claims_or_unsupported_frames_before_transport_io() -> None:
    from totem.hardware.builtin.display.provider import DisplayProvider, DisplaySelectionError

    transport = _RecordingTransport()
    provider = DisplayProvider(
        variant="waveshare-2in13-v4",
        claims=(ResourceClaim("spi", "spi0.0"),),
        transport=transport,
    )

    with pytest.raises(DisplaySelectionError, match="claims"):
        provider.write_frame(FrameSinkRequest("frame", 250, 122, "mono1"))
    with pytest.raises(DisplaySelectionError, match="variant"):
        DisplayProvider(
            variant="not-a-panel", claims=REQUIRED_CLAIMS, transport=transport
        ).write_frame(FrameSinkRequest("frame", 250, 122, "mono1"))
    with pytest.raises(ValueError, match="dimensions"):
        DisplayProvider(
            variant="waveshare-2in13-v4", claims=REQUIRED_CLAIMS, transport=transport
        ).write_frame(FrameSinkRequest("frame", 251, 122, "mono1"))

    assert transport.requests == []


def test_core_provider_has_matching_in_process_and_process_conformance_with_mock_transport(
    tmp_path: Path,
) -> None:
    from totem.hardware.builtin.display.provider import DisplayProvider

    binding = _binding()
    claim = ResourceBroker().claim(binding)
    transport = _RecordingTransport()
    provider = DisplayProvider(
        variant="waveshare-2in13-v4", claims=REQUIRED_CLAIMS, transport=transport
    )
    cases = (
        ConformanceCase("frame", _request("frame", claim.binding_id), {"frame": b"mock-frame"}),
        ConformanceCase("unknown", {"type": "display.unknown", "id": "unknown", "binding_id": claim.binding_id}),
    )

    in_process = run_host_conformance(
        lambda: InProcessDriverHost((claim,), provider, generation=1), cases
    )

    provider_module = tmp_path / "display_core_fixture.py"
    provider_module.write_text(
        "from totem.hardware.builtin.display.provider import DisplayProvider\n"
        "from totem_driver_api import ResourceClaim\n"
        "class Transport:\n"
        "    def write_frame(self, request):\n"
        "        return None\n"
        "def create_provider():\n"
        "    return DisplayProvider(variant='waveshare-2in13-v4', "
        "claims=(ResourceClaim('gpio', 'bcm:17,18,24,25'), ResourceClaim('spi', 'spi0.0')), "
        "transport=Transport())\n",
        encoding="utf-8",
    )
    process_record = SimpleNamespace(
        entry_point_value="display_core_fixture:create_provider",
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
    assert [request.attachment_id for request in transport.requests] == ["frame"]


def test_common_base_uses_injected_transports_and_keeps_frame_contract() -> None:
    from totem.hardware.builtin.display.drivers._waveshare_2in13_base import Waveshare2in13Base

    class Spi:
        def __init__(self) -> None:
            self.writes: List[List[int]] = []

        def open(self, bus: int, device: int) -> None:
            assert (bus, device) == (0, 0)

        def writebytes(self, values: List[int]) -> None:
            self.writes.append(values)

        def close(self) -> None:
            return None

    class Gpio:
        BCM, OUT, IN, HIGH, LOW, PUD_DOWN = 0, 2, 3, 1, 0, 21

        def __init__(self) -> None:
            self.outputs: List[tuple[int, int]] = []

        def setwarnings(self, enabled: bool) -> None:
            return None

        def setmode(self, mode: int) -> None:
            return None

        def setup(self, pin: int, mode: int, **kwargs: object) -> None:
            return None

        def output(self, pin: int, value: int) -> None:
            self.outputs.append((pin, value))

        def input(self, pin: int) -> int:
            return self.LOW

        def cleanup(self, pin: int = 0) -> None:
            return None

    class Panel(Waveshare2in13Base):
        def init(self) -> bool:
            self._initialize_transport()
            self.initialized = True
            return True

        def _update(self) -> None:
            return None

        def _image_buffer(self, image: object) -> bytearray:
            return bytearray([0xFF]) * self.FRAME_BYTES

    spi, gpio = Spi(), Gpio()
    panel = Panel(spi=spi, gpio=gpio, sleep=lambda _seconds: None)
    panel.display_bytes(bytes([0xFF]) * panel.FRAME_BYTES)

    assert panel.width == 250 and panel.height == 122
    assert panel.FRAME_BYTES == 4_000
    assert spi.writes[0] == [panel.SET_RAM_X_ADDRESS_START_END_POSITION]
    assert gpio.outputs[0] == (panel.power_pin, gpio.HIGH)
