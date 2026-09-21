"""Production startup composition for the sole capability runtime owner."""

from __future__ import annotations

import site
from pathlib import Path
from typing import Callable, Mapping, Optional

from totem.hardware.catalog.metadata import CatalogScanner, CatalogSnapshot
from totem.hardware.discovery.facts import HardwareFacts
from totem.hardware.discovery.resolver import Resolver
from totem.hardware.hosts.process import ProcessDriverHost

from .broker import ResourceBroker
from .config import RuntimeConfig
from .runtime import HardwareRuntime


def compose_runtime(
    config: RuntimeConfig,
    *,
    catalog: Optional[CatalogSnapshot] = None,
    facts: Optional[HardwareFacts] = None,
    resolver: Optional[Resolver] = None,
    broker: Optional[ResourceBroker] = None,
    host_factory: Optional[Callable[[tuple[object, ...], int], object]] = None,
) -> HardwareRuntime:
    """Build one immutable catalog → facts → plan → broker → host runtime.

    ``hardware_facts`` is deliberately data-only startup configuration.  A
    deployment that needs an intentionally inert daemon must set
    ``no_hardware = true`` explicitly; an empty owner is never the default
    composition path.
    """

    global_settings = config.global_settings
    if global_settings.get("no_hardware") is True:
        selected_catalog = catalog or CatalogScanner().snapshot()
        return HardwareRuntime(
            (), broker=broker or ResourceBroker(), host_factory=host_factory or _process_host_factory,
            catalog=selected_catalog, config=config, resolver=resolver or Resolver(),
        )
    selected_catalog = catalog or CatalogScanner().snapshot()
    facts_value = facts or HardwareFacts.from_mapping(_configured_facts(global_settings))
    selected_resolver = resolver or Resolver()
    bindings = []
    for capability in sorted(
        {capability.identifier for record in selected_catalog.records for capability in record.manifest.capabilities}
    ):
        result = selected_resolver.resolve(selected_catalog, facts=facts_value, capability_id=capability, config=config)
        if result.binding is not None:
            bindings.append(result.binding)
    return HardwareRuntime(
        bindings,
        broker=broker or ResourceBroker(),
        host_factory=host_factory or _process_host_factory,
        catalog=selected_catalog,
        config=config,
        resolver=selected_resolver,
    )


def _configured_facts(settings: Mapping[str, object]) -> Mapping[str, object]:
    value = settings.get("hardware_facts", {})
    if not isinstance(value, Mapping):
        raise ValueError("global hardware_facts must be a mapping")
    return {str(key): item for key, item in value.items()}


def _process_host_factory(leases: tuple[object, ...], generation: int) -> ProcessDriverHost:
    site_packages = next((Path(path) for path in site.getsitepackages() if Path(path).exists()), Path(site.getusersitepackages()))
    return ProcessDriverHost.start_group(leases, site_packages=site_packages, generation=generation)
