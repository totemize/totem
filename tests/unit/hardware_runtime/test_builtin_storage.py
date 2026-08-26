"""Built-in storage provider tests using temporary local roots only."""

from __future__ import annotations

import ast
import base64
import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Dict

import pytest

from totem_driver_api import ResourceClaim
from totem_driver_api.capabilities.storage import (
    STORAGE_MAX_PAYLOAD_BYTES,
    StoragePath,
    StorageReadResult,
    StorageWriteRequest,
)
from totem_driver_api.conformance import ConformanceCase, run_host_conformance
from totem.hardware.catalog.metadata import CatalogScanner
from totem.hardware.discovery.facts import HardwareFacts
from totem.hardware.discovery.resolver import ResolutionStatus, Resolver
from totem.hardware.hosts.in_process import InProcessDriverHost
from totem.hardware.hosts.process import ProcessDriverHost
from totem.hardware.runtime.bindings import BindingRecord
from totem.hardware.runtime.broker import ResourceBroker, ResourceConflict


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


ROOT = Path(__file__).parents[3]
MANIFEST_PATH = ROOT / "src" / "totem" / "hardware" / "builtin" / "storage" / "totem-driver-manifest.json"
ENTRY_POINT = "totem.hardware.builtin.storage.provider:create_provider"
REQUIRED_CLAIMS = (
    ResourceClaim("path", "storage-root"),
    ResourceClaim("mount", "storage-mount"),
    ResourceClaim("block", "storage-block"),
)


class _EntryPoint:
    group = "totem.hardware.drivers"
    name = "builtin-storage"
    value = ENTRY_POINT


class _Distribution:
    metadata = {"Name": "totem", "Version": "0.2.0"}
    entry_points = (_EntryPoint(),)

    def __init__(self) -> None:
        self.files = (Path("totem/hardware/builtin/storage/totem-driver-manifest.json"),)

    def locate_file(self, path: Path) -> Path:
        assert str(path) == "totem/hardware/builtin/storage/totem-driver-manifest.json"
        return MANIFEST_PATH


def _catalog():
    return CatalogScanner(distributions=lambda: (_Distribution(),)).snapshot()


def _facts() -> HardwareFacts:
    return HardwareFacts.from_mapping(
        {
            "storage.family": "builtin",
            "resource.path": "storage-root",
            "resource.mount": "storage-mount",
            "resource.block": "storage-block",
        }
    )


def _binding(binding_id: str | None = None) -> BindingRecord:
    return Resolver().resolve(
        _catalog(), facts=_facts(), capability_id="storage.files@1", binding_id=binding_id
    ).require_binding()


def _request(request_id: str, binding_id: str, message_type: str, **values: object) -> Dict[str, object]:
    return {"type": message_type, "id": request_id, "binding_id": binding_id, **values}


def test_storage_contract_uses_bounded_normalized_json_safe_values() -> None:
    path = StoragePath("nested/./blob.bin")
    request = StorageWriteRequest(path, b"data")

    assert path.value == "nested/blob.bin"
    assert request.to_json_value() == {
        "path": "nested/blob.bin",
        "data_b64": base64.b64encode(b"data").decode("ascii"),
    }
    assert StorageReadResult(b"data").to_json_value()["data_b64"] == "ZGF0YQ=="
    with pytest.raises(ValueError, match="relative"):
        StoragePath("../escape")
    with pytest.raises(ValueError, match="maximum"):
        StorageWriteRequest(StoragePath("data.bin"), b"x" * (STORAGE_MAX_PAYLOAD_BYTES + 1))


def test_catalog_reads_storage_manifest_without_importing_provider_or_filesystem_driver() -> None:
    for module_name in (
        "totem.hardware.builtin.storage.provider",
    ):
        importlib.sys.modules.pop(module_name, None)

    catalog = _catalog()

    assert catalog.diagnostics == ()
    assert catalog.records[0].manifest.capabilities[0].identifier == "storage.files@1"
    assert catalog.records[0].manifest.factory == ENTRY_POINT
    assert not any(
        name in importlib.sys.modules
        for name in (
            "totem.hardware.builtin.storage.provider",
        )
    )


def test_storage_facts_resolve_all_root_mount_and_block_claims_before_provider_import() -> None:
    selected = Resolver().resolve(_catalog(), facts=_facts(), capability_id="storage.files@1")
    missing = Resolver().resolve(
        _catalog(),
        facts=HardwareFacts.from_mapping({"storage.family": "builtin"}),
        capability_id="storage.files@1",
    )

    assert selected.status is ResolutionStatus.RESOLVED
    assert frozenset(selected.require_binding().claims) == frozenset(REQUIRED_CLAIMS)
    assert missing.status is ResolutionStatus.UNAVAILABLE
    assert "totem.hardware.builtin.storage.provider" not in importlib.sys.modules


def test_provider_rejects_path_escapes_before_driver_file_access(tmp_path: Path) -> None:
    from totem.hardware.builtin.storage.drivers.filesystem import Driver
    from totem.hardware.builtin.storage.files import StoragePathError
    from totem.hardware.builtin.storage.provider import StorageProvider

    provider = StorageProvider(
        model="filesystem", root=tmp_path, claims=REQUIRED_CLAIMS, driver=Driver(root=tmp_path)
    )
    (tmp_path / "escape").symlink_to(tmp_path.parent, target_is_directory=True)

    for requested in ("../escape", "/absolute", "escape/file.bin"):
        with pytest.raises(StoragePathError):
            provider.write(requested, b"nope")
    assert provider.driver_io_count == 0


def test_exclusive_root_claim_conflict_identifies_both_binding_owners() -> None:
    broker = ResourceBroker()
    owner = broker.claim(_binding("storage-owner"))

    with pytest.raises(ResourceConflict) as raised:
        broker.claim(_binding("storage-requester"))

    assert raised.value.existing_owner is owner
    assert raised.value.requesting_owner == "storage-requester"
    assert "storage-owner" in str(raised.value)
    assert "storage-requester" in str(raised.value)


def test_storage_provider_has_matching_dual_host_read_write_list_delete_conformance(tmp_path: Path) -> None:
    from totem.hardware.builtin.storage.drivers.filesystem import Driver
    from totem.hardware.builtin.storage.provider import StorageProvider

    binding = _binding()
    claim = ResourceBroker().claim(binding)
    payload = base64.b64encode(b"new data").decode("ascii")
    cases = (
        ConformanceCase("write", _request("write", claim.binding_id, "storage.files.write", path="new.bin", data_b64=payload)),
        ConformanceCase("read", _request("read", claim.binding_id, "storage.files.read", path="new.bin")),
        ConformanceCase("list", _request("list", claim.binding_id, "storage.files.list", path=".")),
        ConformanceCase("delete", _request("delete", claim.binding_id, "storage.files.delete", path="new.bin")),
        ConformanceCase("unknown", _request("unknown", claim.binding_id, "storage.unknown")),
    )
    in_process = run_host_conformance(
        lambda: InProcessDriverHost(
            (claim,),
            StorageProvider(model="filesystem", root=tmp_path, claims=REQUIRED_CLAIMS, driver=Driver(root=tmp_path)),
            generation=1,
        ),
        cases,
    )

    provider_module = tmp_path / "storage_core_fixture.py"
    provider_module.write_text(
        "import tempfile\n"
        "from totem.hardware.builtin.storage.drivers.filesystem import Driver\n"
        "from totem.hardware.builtin.storage.provider import StorageProvider\n"
        "from totem_driver_api import ResourceClaim\n"
        "def create_provider():\n"
        "    root = tempfile.mkdtemp(prefix='totem-storage-')\n"
        "    return StorageProvider(model='filesystem', root=root, claims=(ResourceClaim('path', 'storage-root'), ResourceClaim('mount', 'storage-mount'), ResourceClaim('block', 'storage-block')), driver=Driver(root=root))\n",
        encoding="utf-8",
    )
    process_record = SimpleNamespace(
        entry_point_value="storage_core_fixture:create_provider",
        provider_id=binding.provider_record.provider_id,
        distribution_version="0.2.0",
        manifest=binding.provider_record.manifest,
    )
    process_binding = BindingRecord(
        binding.capability_id, binding.binding_id, process_record, binding.claims, binding.config
    )
    process_claim = ResourceBroker().claim(process_binding)
    process = run_host_conformance(lambda: ProcessDriverHost.start(process_claim, site_packages=tmp_path), cases)

    assert in_process.items == process.items


def test_legacy_storage_modules_are_exact_provider_reexports() -> None:
    from totem.devices.storage.drivers.filesystem import Driver as LegacyFilesystem
    from totem.devices.storage.drivers.generic_nvme import Driver as LegacyNVMe
    from totem.devices.storage.files import ConfinedStorage as LegacyStorage
    from totem.hardware.builtin.storage.drivers.filesystem import Driver as CanonicalFilesystem
    from totem.hardware.builtin.storage.drivers.generic_nvme import Driver as CanonicalNVMe
    from totem.hardware.builtin.storage.files import ConfinedStorage as CanonicalStorage

    assert LegacyFilesystem is CanonicalFilesystem
    assert LegacyNVMe is CanonicalNVMe
    assert LegacyStorage is CanonicalStorage


def test_legacy_storage_sources_have_no_registry_or_runtime_ownership() -> None:
    expected = {
        "drivers/filesystem.py": "totem.hardware.builtin.storage.drivers.filesystem",
        "drivers/generic_nvme.py": "totem.hardware.builtin.storage.drivers.generic_nvme",
        "files.py": "totem.hardware.builtin.storage.files",
    }
    legacy_root = ROOT / "src" / "totem" / "devices" / "storage"

    for filename, canonical_module in expected.items():
        module = ast.parse((legacy_root / filename).read_text(encoding="utf-8"))
        imports = [node for node in module.body if isinstance(node, ast.ImportFrom)]
        assert len(imports) == 1
        assert imports[0].module == canonical_module
        assert not any(
            isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) for node in module.body
        )
