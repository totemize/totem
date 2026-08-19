"""Command-line entry point for the Totem hardware API."""

import argparse
import logging

import uvicorn

from totem.logging import setup_logger


LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


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
    args = parser.parse_args()

    logger = setup_logger(
        level=LOG_LEVELS[args.log_level], log_file=args.log_file
    )
    logger.info("Starting Totem hardware API on %s:%s", args.host, args.port)
    uvicorn.run(
        "totem.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
