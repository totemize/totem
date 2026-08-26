"""Compatibility view over installed driver catalog records and runtime handles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol, Tuple, Union

from totem.hardware.catalog.metadata import CatalogRecord, CatalogScanner, CatalogSnapshot


class DriverRegistryError(RuntimeError):
    """Base exception for compatibility registry resolution failures."""


class UnknownDriverError(DriverRegistryError):
    """The catalog does not declare the requested historical name."""


class MockDriverNotAllowedError(DriverRegistryError):
    """A cataloged mock provider requires explicit compatibility opt-in."""


class DriverLoadError(DriverRegistryError):
    """A caller attempted to bypass canonical capability ownership."""


class HardwareNotFoundError(DriverRegistryError):
    """Historical family wrappers retain this actionable selection error."""


class BindingHandleClient(Protocol):
    """Minimal existing-runtime port; it owns neither selection nor resources."""

    def handle(self, capability_id: str, binding_id: str) -> object:
        """Return one already-ready opaque capability handle."""


@dataclass(frozen=True)
class DriverSpec:
    """Historical data name projected from provider metadata, never a class load."""

    name: str
    module: str = ""
    class_name: str = "Driver"
    is_mock: bool = False
    capability_id: str = ""
    binding_id: str = ""

    @classmethod
    def from_catalog_record(cls, record: CatalogRecord) -> Tuple["DriverSpec", ...]:
        """Project metadata into legacy-shaped records without importing it."""

        module, _separator, factory = record.entry_point_value.partition(":")
        capabilities = tuple(record.manifest.capabilities)
        multiple_capabilities = len(capabilities) > 1
        is_mock = (
            record.provider_id.startswith("mock.")
            or ".mock." in record.provider_id
            or record.provider_id.endswith(".mock")
        )
        return tuple(
            cls(
                name=(
                    "{}:{}".format(record.provider_id, capability.identifier)
                    if multiple_capabilities
                    else record.provider_id
                ),
                module=module,
                class_name=factory or "Driver",
                is_mock=is_mock,
                capability_id=capability.identifier,
                binding_id="{}:{}".format(record.provider_id, capability.identifier),
            )
            for capability in capabilities
        )


CatalogSource = Union[CatalogScanner, CatalogSnapshot]


class DriverRegistry:
    """Expose catalog records and existing runtime handles at legacy imports.

    ``interface`` and ``specs`` remain accepted only so importing a historical
    family wrapper does not fail before that wrapper is migrated. They are
    intentionally ignored: provider availability comes exclusively from the
    installed catalog and ``load`` can only request an already-ready runtime
    handle.
    """

    def __init__(
        self,
        interface: object = None,
        specs: Iterable[DriverSpec] = (),
        *,
        catalog: Optional[CatalogSource] = None,
        binding_client: Optional[BindingHandleClient] = None,
    ) -> None:
        del interface, specs
        self._catalog = catalog or CatalogScanner()
        self._binding_client = binding_client
        self._records: Optional[Tuple[DriverSpec, ...]] = None

    @staticmethod
    def normalize(name: str) -> str:
        return name.strip().lower().replace("-", "_")

    @property
    def names(self) -> Tuple[str, ...]:
        return tuple(sorted(spec.name for spec in self._specifications()))

    def lookup(self, name: str) -> DriverSpec:
        normalized = self.normalize(name)
        for spec in self._specifications():
            if self.normalize(spec.name) == normalized:
                return spec
        expected = ", ".join(self.names) or "(catalog is empty)"
        raise UnknownDriverError(
            "Unknown driver {!r}; expected one of: {}".format(name, expected)
        )

    def load(self, name: str, *, allow_mock: bool = False) -> object:
        """Return an existing opaque handle; never import or construct a provider."""

        spec = self.lookup(name)
        if spec.is_mock and not allow_mock:
            raise MockDriverNotAllowedError(
                "Mock driver {!r} requires allow_mock=True".format(spec.name)
            )
        if self._binding_client is None:
            raise DriverLoadError(
                "Legacy driver loading requires a canonical runtime handle"
            )
        return self._binding_client.handle(spec.capability_id, spec.binding_id)

    def _specifications(self) -> Tuple[DriverSpec, ...]:
        if self._records is None:
            snapshot = (
                self._catalog.snapshot()
                if isinstance(self._catalog, CatalogScanner)
                else self._catalog
            )
            records = tuple(
                spec
                for record in snapshot.records
                for spec in DriverSpec.from_catalog_record(record)
            )
            self._records = tuple(sorted(records, key=lambda spec: self.normalize(spec.name)))
        return self._records
