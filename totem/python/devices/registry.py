"""Validated registries for resolving device drivers by stable names."""

import importlib
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple, Type

from devices.contracts import DeviceDriver


class DriverRegistryError(RuntimeError):
    """Base exception for driver resolution failures."""


class UnknownDriverError(DriverRegistryError):
    pass


class MockDriverNotAllowedError(DriverRegistryError):
    pass


class DriverLoadError(DriverRegistryError):
    pass


class HardwareNotFoundError(DriverRegistryError):
    pass


@dataclass(frozen=True)
class DriverSpec:
    name: str
    module: str
    class_name: str = "Driver"
    is_mock: bool = False


class DriverRegistry:
    """Resolve allow-listed driver names and validate their interfaces."""

    def __init__(self, interface: Type[DeviceDriver], specs: Iterable[DriverSpec]):
        self.interface = interface
        self._specs: Dict[str, DriverSpec] = {}
        for spec in specs:
            normalized = self.normalize(spec.name)
            if normalized in self._specs:
                raise ValueError("Duplicate driver registration: {}".format(spec.name))
            self._specs[normalized] = spec

    @staticmethod
    def normalize(name: str) -> str:
        return name.strip().lower().replace("-", "_")

    @property
    def names(self) -> Tuple[str, ...]:
        return tuple(sorted(self._specs))

    def load(self, name: str, *, allow_mock: bool = False) -> DeviceDriver:
        normalized = self.normalize(name)
        spec = self._specs.get(normalized)
        if spec is None:
            raise UnknownDriverError(
                "Unknown driver {!r}; expected one of: {}".format(
                    name, ", ".join(self.names)
                )
            )
        if spec.is_mock and not allow_mock:
            raise MockDriverNotAllowedError(
                "Mock driver {!r} requires allow_mock=True".format(spec.name)
            )

        try:
            module = importlib.import_module(spec.module)
            driver_class = getattr(module, spec.class_name)
        except (ImportError, AttributeError) as exc:
            raise DriverLoadError(
                "Unable to import driver {!r}: {}".format(spec.name, exc)
            ) from exc

        if not isinstance(driver_class, type) or not issubclass(
            driver_class, self.interface
        ):
            raise DriverLoadError(
                "Driver {!r} does not implement {}".format(
                    spec.name, self.interface.__name__
                )
            )

        return driver_class()
