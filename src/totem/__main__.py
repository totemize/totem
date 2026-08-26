"""Command-line entry point for the Totem hardware API."""

import argparse
import logging
from pathlib import Path
from typing import Callable, Mapping, Optional

import uvicorn

from totem.api.app import create_app
from totem.compat.hardware_env import LegacyRuntimeConfig, legacy_runtime_config
from totem.hardware.runtime.broker import ResourceBroker
from totem.hardware.runtime.config import RuntimeConfig, load_runtime_config
from totem.hardware.runtime.runtime import HardwareRuntime
from totem.logging import setup_logger


LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


RuntimeFactory = Callable[[RuntimeConfig, LegacyRuntimeConfig], object]


def _empty_runtime(config: RuntimeConfig, _legacy: LegacyRuntimeConfig) -> HardwareRuntime:
    """Create the sole startup owner until resolved bindings are composed.

    The runtime itself remains the one owner even when a deployment has no
    resolved bindings.  The host factory is intentionally unreachable for an
    empty plan, keeping CLI composition local and side-effect free.
    """

    def unreachable_host_factory(_leases: tuple[object, ...], _generation: int) -> object:
        raise RuntimeError("an empty runtime must not create a driver host")

    return HardwareRuntime(
        (),
        broker=ResourceBroker(),
        host_factory=unreachable_host_factory,
        config=config,
    )


def compose_application(
    *,
    config_path: Optional[Path] = None,
    config: Optional[RuntimeConfig] = None,
    environ: Optional[Mapping[str, str]] = None,
    runtime_factory: Optional[RuntimeFactory] = None,
):
    """Compose the compatibility API over exactly one typed runtime owner."""

    if config is None:
        config = load_runtime_config(config_path) if config_path is not None else RuntimeConfig()
    legacy = legacy_runtime_config(environ)
    runtime = (runtime_factory or _empty_runtime)(config, legacy)
    return create_app(
        runtime=runtime,
        legacy_config=legacy,
        runtime_config=config,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Totem hardware API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--log-level", choices=tuple(LOG_LEVELS), default="info"
    )
    parser.add_argument("--reload", action="store_true")
    parser.add_argument(
        "--log-file",
        help="Optional log destination; stdout is used when omitted",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional typed runtime TOML configuration",
    )
    args = parser.parse_args()

    logger = setup_logger(
        level=LOG_LEVELS[args.log_level], log_file=args.log_file
    )
    logger.info("Starting Totem hardware API on %s:%s", args.host, args.port)
    application = compose_application(config_path=args.config)
    uvicorn.run(
        application,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
