"""Test-suite safety gates for operations that touch real hardware."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-hardware",
        action="store_true",
        default=False,
        help="run tests marked hardware against connected devices",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-hardware"):
        return

    skip_hardware = pytest.mark.skip(
        reason="requires --run-hardware and connected Totem hardware"
    )
    for item in items:
        if "hardware" in item.keywords:
            item.add_marker(skip_hardware)
