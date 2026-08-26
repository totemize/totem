"""Data-only compatibility evidence for the hardware resolver."""

from __future__ import annotations

from totem.hardware.discovery.facts import HardwareComponent, HardwareFacts
from totem.hardware.catalog.metadata import CatalogRecord, CatalogSnapshot
from totem.hardware.discovery.profiles import DeviceProfile
from totem.hardware.discovery.resolver import ResolutionStatus, Resolver
from totem.hardware.runtime.config import BindingConfig, RuntimeConfig
from totem_driver_api import DriverManifest


def _record(
    provider_id: str,
    *,
    predicates: tuple[dict[str, str], ...] = (),
    prerequisites: tuple[str, ...] = (),
    resources: tuple[dict[str, object], ...] = (),
) -> CatalogRecord:
    manifest = DriverManifest.from_json(
        {
            "manifest_major": 1,
            "api_major": 1,
            "provider_id": provider_id,
            "provider_version": "1.0.0",
            "capabilities": ["display.frame-sink@1"],
            "predicates": list(predicates),
            "prerequisites": list(prerequisites),
            "config_schema": {"host_mode": {"type": "string"}},
            "defaults": {"host_mode": "process"},
            "resources": list(resources),
            "privileges": [],
            "grouping": "provider",
            "factory": "fixture.provider:create_provider",
        }
    )
    return CatalogRecord(
        distribution_name=provider_id,
        distribution_version="1.0.0",
        entry_point_name=provider_id,
        entry_point_value="fixture.provider:create_provider",
        manifest=manifest,
    )


def _catalog(*records: CatalogRecord) -> CatalogSnapshot:
    return CatalogSnapshot(records=tuple(records), diagnostics=())


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


def test_facts_cover_platform_bus_device_tree_and_service_evidence_independent_of_order() -> None:
    components = [
        HardwareComponent("net", "wlan0", {"phy": "phy0", "adapter": "brcmfmac"}),
        HardwareComponent("device-tree", "soc", {"modalias": "of:NspiT<NULL>Cspidev"}),
        HardwareComponent("usb", "04E6:5591", {"vid": "04E6", "pid": "5591", "address": "1-1"}),
        HardwareComponent("platform", "runtime", {"architecture": "armv7l", "os": "linux", "kernel": "6.12"}),
    ]
    first = HardwareFacts.from_components(components)
    second = HardwareFacts.from_components(list(reversed(components)))

    assert first == second
    assert first.value_for("net.wlan0.phy") == "phy0"
    assert first.value_for("net.wlan0.adapter") == "brcmfmac"
    assert first.value_for("device-tree.soc.modalias") == "of:nspit<null>cspidev"
    assert first.value_for("usb.04e6:5591.vid") == "04e6"
    assert first.value_for("platform.runtime.kernel") == "6.12"


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


def test_exact_match_outranks_weak_profile_evidence_and_explains_every_candidate() -> None:
    catalog = _catalog(
        _record(
            "exact.display",
            predicates=(
                {"fact": "platform.raspberry pi zero 2 w.architecture", "equals": "armv7l"},
            ),
            prerequisites=("systemd",),
            resources=(
                {"kind": "spi", "identifier": "spi0.0", "exclusive": True},
            ),
        ),
        _record(
            "weak.display",
            predicates=(
                {"fact": "usb.04e6:5591.interface", "equals": "nfc0"},
            ),
            prerequisites=("systemd",),
            resources=(
                {"kind": "spi", "identifier": "spi0.0", "exclusive": True},
            ),
        ),
        _record(
            "rejected.display",
            predicates=(
                {"fact": "platform.raspberry pi zero 2 w.architecture", "equals": "armv7l"},
            ),
            prerequisites=("bluez",),
            resources=(
                {"kind": "spi", "identifier": "spi0.0", "exclusive": True},
            ),
        ),
    )
    facts = HardwareFacts.from_mapping(
        {
            "platform.raspberry pi zero 2 w.architecture": "armv7l",
            "resource.spi": "spi0.0",
            "service.systemd": "present",
        }
    )
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

    result = Resolver().resolve(
        catalog, facts=facts, capability_id="display.frame-sink@1", profile=profile
    )

    assert result.status is ResolutionStatus.RESOLVED
    assert result.require_binding().provider_record.provider_id == "exact.display"
    assert [item.provider_id for item in result.plan.candidates] == [
        "exact.display",
        "rejected.display",
        "weak.display",
    ]
    exact, rejected, weak = result.plan.candidates
    assert exact.accepted is True
    assert exact.score > weak.score
    assert weak.supporting == (
        "profile:usb.04e6:5591.interface=nfc0",
        "resource.spi=spi0.0",
        "service.systemd=present",
    )
    assert rejected.accepted is False
    assert rejected.missing == ("service.bluez=present",)
    assert result.plan.to_json() == Resolver().resolve(
        catalog, facts=facts, capability_id="display.frame-sink@1", profile=profile
    ).plan.to_json()


def test_equal_automatic_matches_fail_closed_and_shuffled_inputs_are_identical() -> None:
    alpha = _record(
        "alpha.display",
        predicates=({"fact": "platform.os", "equals": "linux"},),
        resources=({"kind": "spi", "identifier": "spi0.0", "exclusive": True},),
    )
    beta = _record(
        "beta.display",
        predicates=({"fact": "platform.os", "equals": "linux"},),
        resources=({"kind": "spi", "identifier": "spi0.0", "exclusive": True},),
    )
    facts = HardwareFacts.from_mapping({"resource.spi": "spi0.0", "platform.os": "linux"})

    forward = Resolver().resolve(_catalog(alpha, beta), facts=facts, capability_id="display.frame-sink@1")
    reverse = Resolver().resolve(_catalog(beta, alpha), facts=facts, capability_id="display.frame-sink@1")

    assert forward.status is ResolutionStatus.AMBIGUOUS
    assert reverse.status is ResolutionStatus.AMBIGUOUS
    assert forward.plan.to_json() == reverse.plan.to_json()
    assert forward.evidence == ("alpha.display", "beta.display")


def test_explicit_binding_wins_only_after_config_prerequisite_and_resource_validation() -> None:
    automatic = _record(
        "automatic.display",
        predicates=({"fact": "platform.os", "equals": "linux"},),
        resources=({"kind": "spi", "identifier": "spi0.0", "exclusive": True},),
    )
    explicit = _record(
        "explicit.display",
        predicates=({"fact": "platform.os", "equals": "not-linux"},),
        prerequisites=("systemd",),
        resources=({"kind": "spi", "identifier": "spi0.0", "exclusive": True},),
    )
    config = RuntimeConfig(
        bindings=(BindingConfig("display.main", "explicit.display", {"host_mode": "process"}),)
    )
    facts = HardwareFacts.from_mapping(
        {"platform.os": "linux", "resource.spi": "spi0.0", "service.systemd": "present"}
    )

    selected = Resolver().resolve(
        _catalog(automatic, explicit),
        facts=facts,
        capability_id="display.frame-sink@1",
        config=config,
        binding_id="display.main",
    )

    assert selected.status is ResolutionStatus.RESOLVED
    assert selected.require_binding().provider_record.provider_id == "explicit.display"
    assert selected.plan.explicit_binding_id == "display.main"

    missing_resource = Resolver().resolve(
        _catalog(automatic, explicit),
        facts=HardwareFacts.from_mapping({"platform.os": "linux", "service.systemd": "present"}),
        capability_id="display.frame-sink@1",
        config=config,
        binding_id="display.main",
    )

    assert missing_resource.status is ResolutionStatus.UNAVAILABLE
    assert missing_resource.plan.candidates[0].missing == ("resource.spi=spi0.0",)


def test_override_rejects_invalid_config_and_unsupported_platform_without_provider_import() -> None:
    explicit = _record(
        "explicit.display",
        predicates=({"fact": "platform.os", "equals": "linux"},),
        resources=({"kind": "spi", "identifier": "spi0.0", "exclusive": True},),
    )
    invalid_config = RuntimeConfig(
        bindings=(BindingConfig("display.main", "explicit.display", {"unknown": "value"}),)
    )

    result = Resolver().resolve(
        _catalog(explicit),
        facts=HardwareFacts.from_mapping({"platform.os": "darwin", "resource.spi": "spi0.0"}),
        capability_id="display.frame-sink@1",
        config=invalid_config,
        binding_id="display.main",
    )

    assert result.status is ResolutionStatus.UNAVAILABLE
    assert result.plan.candidates[0].missing == ()
    assert result.plan.candidates[0].rejected == ("config:unknown_config_field",)
