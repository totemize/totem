#!/usr/bin/env python3
"""Paired comparison of header codecs with identical logical fixtures."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List


SPIKES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SPIKES / "_support"))

from nip5d_framed import (  # noqa: E402
    JsonCodec,
    MessagePackCodec,
    benchmark,
    run_conformance,
)


def median_path(samples: List[Dict[str, Any]], *path: str) -> float:
    values = []
    for sample in samples:
        value: Any = sample
        for part in path:
            value = value[part]
        values.append(float(value))
    return round(statistics.median(values), 6)


def aggregate(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    first_sizes = samples[0]["wire_sizes_bytes"]
    if any(sample["wire_sizes_bytes"] != first_sizes for sample in samples[1:]):
        raise AssertionError("wire sizes changed across identical trials")
    return {
        "wire_sizes_bytes": first_sizes,
        "decode_microseconds_per_frame": {
            "control": median_path(samples, "decode_microseconds_per_frame", "control"),
            "display_with_raw_attachment": median_path(
                samples, "decode_microseconds_per_frame", "display_with_raw_attachment"
            ),
        },
        "encode_and_decode_microseconds_per_frame": {
            "control": median_path(
                samples, "encode_and_decode_microseconds_per_frame", "control"
            ),
            "display_with_raw_attachment": median_path(
                samples,
                "encode_and_decode_microseconds_per_frame",
                "display_with_raw_attachment",
            ),
        },
    }


def ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=2_000)
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name("comparison.json")
    )
    args = parser.parse_args()
    if args.trials < 2:
        raise ValueError("at least two trials are required for a comparison")

    codecs = {
        "json": JsonCodec(),
        "messagepack": MessagePackCodec(),
        "messagepack_pure_python": MessagePackCodec(pure_python=True),
    }
    checks = {name: run_conformance(codec) for name, codec in codecs.items()}
    if any(value != checks["json"] for value in checks.values()):
        raise AssertionError("codec conformance coverage diverged")

    samples: Dict[str, List[Dict[str, Any]]] = {name: [] for name in codecs}
    for trial in range(args.trials):
        names = list(codecs)
        offset = trial % len(names)
        order = names[offset:] + names[:offset]
        for name in order:
            samples[name].append(benchmark(codecs[name], args.iterations))

    json_result = aggregate(samples["json"])
    msgpack_result = aggregate(samples["messagepack"])
    fallback_result = aggregate(samples["messagepack_pure_python"])
    comparison = {
        "schema": "totem.nip5d-codec-comparison@1",
        "trials": args.trials,
        "iterations_per_inner_sample": args.iterations,
        "conformance_checks_per_codec": len(checks["json"]),
        "codec_versions": {
            "json": codecs["json"].library_version,
            "messagepack": codecs["messagepack"].library_version,
            "messagepack_pure_python": codecs["messagepack_pure_python"].library_version,
        },
        "json": json_result,
        "messagepack": msgpack_result,
        "messagepack_pure_python": fallback_result,
        "ratios_messagepack_over_json": {
            "control_wire_size": ratio(
                msgpack_result["wire_sizes_bytes"]["control"],
                json_result["wire_sizes_bytes"]["control"],
            ),
            "display_wire_size": ratio(
                msgpack_result["wire_sizes_bytes"]["display_total"],
                json_result["wire_sizes_bytes"]["display_total"],
            ),
            "control_decode_time": ratio(
                msgpack_result["decode_microseconds_per_frame"]["control"],
                json_result["decode_microseconds_per_frame"]["control"],
            ),
            "display_decode_time": ratio(
                msgpack_result["decode_microseconds_per_frame"][
                    "display_with_raw_attachment"
                ],
                json_result["decode_microseconds_per_frame"][
                    "display_with_raw_attachment"
                ],
            ),
            "control_encode_decode_time": ratio(
                msgpack_result["encode_and_decode_microseconds_per_frame"]["control"],
                json_result["encode_and_decode_microseconds_per_frame"]["control"],
            ),
            "display_encode_decode_time": ratio(
                msgpack_result["encode_and_decode_microseconds_per_frame"][
                    "display_with_raw_attachment"
                ],
                json_result["encode_and_decode_microseconds_per_frame"][
                    "display_with_raw_attachment"
                ],
            ),
        },
        "ratios_messagepack_pure_python_over_json": {
            "control_decode_time": ratio(
                fallback_result["decode_microseconds_per_frame"]["control"],
                json_result["decode_microseconds_per_frame"]["control"],
            ),
            "display_decode_time": ratio(
                fallback_result["decode_microseconds_per_frame"][
                    "display_with_raw_attachment"
                ],
                json_result["decode_microseconds_per_frame"][
                    "display_with_raw_attachment"
                ],
            ),
            "control_encode_decode_time": ratio(
                fallback_result["encode_and_decode_microseconds_per_frame"]["control"],
                json_result["encode_and_decode_microseconds_per_frame"]["control"],
            ),
            "display_encode_decode_time": ratio(
                fallback_result["encode_and_decode_microseconds_per_frame"][
                    "display_with_raw_attachment"
                ],
                json_result["encode_and_decode_microseconds_per_frame"][
                    "display_with_raw_attachment"
                ],
            ),
        },
        "pi_gate": (
            "Repeat on armv6/armv7/aarch64 devices, including install/build path and "
            "pure-Python fallback if a compatible wheel is unavailable."
        ),
    }
    args.output.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(comparison, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
