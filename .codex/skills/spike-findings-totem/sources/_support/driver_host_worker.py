#!/usr/bin/env python3
import argparse

from dual_host_fixture import run_worker


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fd", type=int, required=True)
    args = parser.parse_args()
    return run_worker(args.fd)


if __name__ == "__main__":
    raise SystemExit(main())
