"""Fixture-only resource ownership tests for the canonical runtime broker."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import cast

import pytest

from totem.hardware.catalog.metadata import CatalogRecord
from totem.hardware.runtime.bindings import BindingRecord
from totem.hardware.runtime.broker import (
    ResourceBroker,
    ResourceConflict,
    ResourceKey,
    ResourceReleaseError,
)
from totem_driver_api import ResourceClaim


def _binding(
    name: str,
    *claims: ResourceClaim,
) -> BindingRecord:
    return BindingRecord(
        capability_id="fixture.capability@1",
        binding_id=name,
        provider_record=cast(CatalogRecord, object()),
        claims=claims,
        config=(),
    )


def test_normalizes_resource_families_without_changing_case_sensitive_paths() -> None:
    assert ResourceKey.from_claim(ResourceClaim(" GPIO ", " GPIO17 ")).value == "gpio:17"
    assert ResourceKey.from_claim(ResourceClaim("spi", " /dev/SPIdev0.0 ")).value == "spi:/dev/spidev0.0"
    assert ResourceKey.from_claim(ResourceClaim("i2c", " 1 ")).value == "i2c:1"
    assert ResourceKey.from_claim(ResourceClaim("block", " /dev/SDA ")).value == "block:/dev/sda"
    assert ResourceKey.from_claim(ResourceClaim("path", " /var/lib/../run/Totem ")).value == "path:/var/run/Totem"
    assert ResourceKey.from_claim(ResourceClaim("phy", " PHY0 ")).value == "phy:phy0"
    assert ResourceKey.from_claim(ResourceClaim("interface", " WLAN0 ")).value == "interface:wlan0"
    assert ResourceKey.from_claim(ResourceClaim("adapter", " HCI0 ")).value == "adapter:hci0"
    assert ResourceKey.from_claim(ResourceClaim("dbus", " org.example.Totem ")).value == "dbus:org.example.Totem"
    assert ResourceKey.from_claim(ResourceClaim("socket", " /run/../run/totem.sock ")).value == "socket:/run/totem.sock"
    assert ResourceKey.from_claim(ResourceClaim("credential", " card-reader-key ")).value == "credential:<redacted>"
    assert ResourceKey.from_claim(ResourceClaim("compatibility", " WiFi-STA ")).value == "compatibility:wifi-sta"


def test_acquire_many_commits_every_claim_or_none_with_owner_diagnostics() -> None:
    broker = ResourceBroker()
    first = _binding("display", ResourceClaim("spi", "/dev/spidev0.0"))
    second = _binding(
        "network",
        ResourceClaim("interface", "wlan0"),
        ResourceClaim("dbus", "org.example.NetworkManager"),
    )
    broker.acquire(first)

    with pytest.raises(ResourceConflict) as raised:
        broker.acquire_many(
            (
                second,
                _binding("contender", ResourceClaim("spi", "/dev/spidev0.0")),
            )
        )

    conflict = raised.value
    assert conflict.resource.value == "spi:/dev/spidev0.0"
    assert conflict.owner.binding_id == "display"
    assert conflict.requesting_binding_id == "contender"
    assert broker.snapshot() == (
        {
            "binding_id": "display",
            "generation": 1,
            "resources": ("spi:/dev/spidev0.0",),
        },
    )


def test_concurrent_conflicts_have_one_complete_owner_and_one_loser() -> None:
    broker = ResourceBroker()
    bindings = (
        _binding("alpha", ResourceClaim("gpio", "17"), ResourceClaim("i2c", "1")),
        _binding("beta", ResourceClaim("gpio", "GPIO17"), ResourceClaim("spi", "/dev/spidev0.0")),
    )

    def acquire(binding: BindingRecord) -> str:
        try:
            broker.acquire(binding)
        except ResourceConflict as conflict:
            return "conflict:{}:{}".format(conflict.resource.value, conflict.owner.binding_id)
        return "acquired:{}".format(binding.binding_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(acquire, bindings))

    assert outcomes[0].startswith("acquired:")
    assert outcomes[1].startswith("conflict:gpio:17:")
    snapshot = broker.snapshot()
    assert len(snapshot) == 1
    assert len(snapshot[0]["resources"]) == 2


def test_nonexclusive_claims_share_and_exclusive_claims_do_not_coexist() -> None:
    broker = ResourceBroker()
    first = broker.acquire(_binding("observer-a", ResourceClaim("interface", "wlan0", exclusive=False)))
    second = broker.acquire(_binding("observer-b", ResourceClaim("interface", "WLAN0", exclusive=False)))

    assert {first.binding_id, second.binding_id} == {"observer-a", "observer-b"}
    with pytest.raises(ResourceConflict) as raised:
        broker.acquire(_binding("exclusive", ResourceClaim("interface", "wlan0")))
    assert raised.value.resource.value == "interface:wlan0"
    assert raised.value.owner.binding_id == "observer-a"


def test_release_requires_the_exact_binding_generation_and_owner_token() -> None:
    broker = ResourceBroker()
    first = broker.acquire(_binding("display", ResourceClaim("spi", "/dev/spidev0.0")))

    with pytest.raises(ResourceReleaseError):
        broker.release(first.binding_id, first.generation, "wrong-token")
    with pytest.raises(ResourceReleaseError):
        broker.release("other-binding", first.generation, first.owner_token)

    broker.release(first.binding_id, first.generation, first.owner_token)
    replacement = broker.acquire(_binding("display", ResourceClaim("spi", "/dev/spidev0.0")))

    assert replacement.generation == first.generation + 1
    with pytest.raises(ResourceReleaseError):
        broker.release(replacement.binding_id, first.generation, first.owner_token)
    with pytest.raises(ResourceReleaseError):
        broker.release(replacement.binding_id, replacement.generation, "wrong-token")
    assert broker.snapshot()[0]["binding_id"] == "display"


def test_snapshots_redact_credential_identifiers_and_never_expose_owner_tokens() -> None:
    broker = ResourceBroker()
    lease = broker.acquire(
        _binding(
            "nfc",
            ResourceClaim("credential", "super-secret-reader-password"),
            ResourceClaim("compatibility", "radio-sta", group="shared-radio"),
        )
    )

    assert lease.compatibility_groups == ("shared-radio",)
    assert broker.snapshot() == (
        {
            "binding_id": "nfc",
            "generation": 1,
            "resources": ("compatibility:radio-sta", "credential:<redacted>"),
        },
    )
    assert "super-secret-reader-password" not in repr(broker.snapshot())
    assert lease.owner_token not in repr(broker.snapshot())


def test_rejects_duplicate_normalized_claims_before_creating_a_lease() -> None:
    broker = ResourceBroker()
    with pytest.raises(ValueError, match="duplicate normalized resource"):
        broker.acquire(
            _binding(
                "duplicate",
                ResourceClaim("gpio", "17"),
                ResourceClaim("GPIO", "GPIO17"),
            )
        )
    assert broker.snapshot() == ()
