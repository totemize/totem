"""Data-only compatibility evidence for the hardware resolver."""

from __future__ import annotations

from totem.hardware.discovery.facts import HardwareComponent, HardwareFacts
from totem.hardware.discovery.profiles import DeviceProfile


def test_facts_normalize_component_evidence_and_are_immutable() -> None:
    facts = HardwareFacts.from_components(
        [
            HardwareComponent(
                kind="usb",
                identifier="  04E6:5591  ",
                evidence={"interface": "nfc0", "bus": "USB"},
            ),
            HardwareComponent(
                kind="platform",
                identifier=" Raspberry Pi Zero 2 W ",
                evidence={"architecture": "ARMV7L", "os": "Linux"},
            ),
        ]
    )

    assert facts.components == (
        HardwareComponent(
            kind="platform",
            identifier="raspberry pi zero 2 w",
            evidence=(("architecture", "armv7l"), ("os", "linux")),
        ),
        HardwareComponent(
            kind="usb",
            identifier="04e6:5591",
            evidence=(("bus", "usb"), ("interface", "nfc0")),
        ),
    )
    assert facts.value_for("usb.04e6:5591.interface") == "nfc0"
    assert facts.value_for("platform.raspberry pi zero 2 w.architecture") == "armv7l"


def test_data_only_profile_merges_facts_without_product_selection() -> None:
    profile = DeviceProfile.from_mapping(
        "bench.nfc",
        {
            "components": [
                {
                    "kind": "usb",
                    "identifier": "04e6:5591",
                    "evidence": {"interface": "nfc0"},
                }
            ]
        },
    )

    assert profile.profile_id == "bench.nfc"
    assert profile.components[0].kind == "usb"
    assert profile.components[0].identifier == "04e6:5591"
