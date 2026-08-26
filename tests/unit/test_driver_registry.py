"""Compatibility imports for the catalog-backed driver registry."""

import pytest

from totem.devices.registry import (
    DriverLoadError,
    DriverRegistry,
    HardwareNotFoundError,
    MockDriverNotAllowedError,
    UnknownDriverError,
)
from totem.hardware.catalog.metadata import CatalogSnapshot


pytestmark = pytest.mark.unit


def test_legacy_registry_errors_remain_importable() -> None:
    registry = DriverRegistry(catalog=CatalogSnapshot(records=(), diagnostics=()))

    with pytest.raises(UnknownDriverError):
        registry.lookup("unsupported")
    with pytest.raises(UnknownDriverError):
        registry.load("unsupported")

    assert issubclass(HardwareNotFoundError, RuntimeError)
    assert issubclass(MockDriverNotAllowedError, RuntimeError)
    assert issubclass(DriverLoadError, RuntimeError)


def test_legacy_constructor_cannot_reactivate_static_driver_specs() -> None:
    registry = DriverRegistry(object, ())

    assert registry.names
    with pytest.raises((UnknownDriverError, DriverLoadError)):
        registry.load("made_up_driver")
