"""Parsers for Linux radio capability and rfkill reports."""

import json
import re
from typing import Dict, List, Optional, Tuple

from totem.devices.network.models import (
    ConcurrentInterfaceCombination,
    InterfaceLimit,
    RadioBlockState,
)


_COMBINATION_LIMIT = re.compile(r"#\{\s*([^}]+)\s*\}\s*<=\s*(\d+)")


def parse_iw_phy(
    text: str,
) -> Tuple[List[str], Dict[str, List[int]], List[ConcurrentInterfaceCombination]]:
    modes: List[str] = []
    bands: Dict[str, List[int]] = {}
    combinations: List[ConcurrentInterfaceCombination] = []
    section: Optional[str] = None
    band: Optional[str] = None
    combination_buffer = ""

    def finish_combination() -> None:
        nonlocal combination_buffer
        if not combination_buffer:
            return
        limits = [
            InterfaceLimit(
                modes=[mode.strip() for mode in match.group(1).split(",")],
                maximum=int(match.group(2)),
            )
            for match in _COMBINATION_LIMIT.finditer(combination_buffer)
        ]
        total = re.search(r"total\s*<=\s*(\d+)", combination_buffer)
        channels = re.search(r"#channels\s*<=\s*(\d+)", combination_buffer)
        if limits and total and channels:
            combinations.append(
                ConcurrentInterfaceCombination(
                    limits=limits,
                    maximum_interfaces=int(total.group(1)),
                    maximum_channels=int(channels.group(1)),
                )
            )
        combination_buffer = ""

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped == "Supported interface modes:":
            finish_combination()
            section = "modes"
            continue
        if stripped == "valid interface combinations:":
            finish_combination()
            section = "combinations"
            continue
        band_match = re.match(r"Band\s+(\d+):", stripped)
        if band_match:
            finish_combination()
            section = "band"
            band = "band{}".format(band_match.group(1))
            bands.setdefault(band, [])
            continue
        if section == "modes":
            mode_match = re.match(r"\*\s+(.+)$", stripped)
            if mode_match:
                modes.append(mode_match.group(1))
                continue
            if stripped and not raw_line.startswith("\t\t"):
                section = None
        elif section == "band" and band:
            frequency = re.match(r"\*\s+(\d+)(?:\.\d+)?\s+MHz\s+\[(\d+)\]", stripped)
            if frequency and "disabled" not in stripped:
                bands[band].append(int(frequency.group(2)))
        elif section == "combinations":
            if stripped.startswith("*"):
                finish_combination()
                combination_buffer = stripped[1:].strip()
            elif combination_buffer and ("#{" in stripped or "total" in stripped):
                combination_buffer += " " + stripped
            elif combination_buffer:
                finish_combination()
                section = None
    finish_combination()
    return modes, bands, combinations


def parse_rfkill_json(text: str, radio_type: str) -> RadioBlockState:
    try:
        entries = json.loads(text).get("rfkilldevices", [])
    except (ValueError, AttributeError) as exc:
        raise ValueError("Invalid rfkill JSON") from exc
    matching = [entry for entry in entries if entry.get("type") == radio_type]
    if not matching:
        return RadioBlockState(soft_blocked=False, hard_blocked=False)
    return RadioBlockState(
        soft_blocked=any(
            str(entry.get("soft", "")).lower() == "blocked" for entry in matching
        ),
        hard_blocked=any(
            str(entry.get("hard", "")).lower() == "blocked" for entry in matching
        ),
    )


def frequency_to_channel(frequency_mhz: Optional[int]) -> Optional[int]:
    if frequency_mhz is None:
        return None
    if frequency_mhz == 2484:
        return 14
    if 2412 <= frequency_mhz <= 2472:
        return (frequency_mhz - 2407) // 5
    if 5000 <= frequency_mhz <= 5895:
        return (frequency_mhz - 5000) // 5
    if 5955 <= frequency_mhz <= 7115:
        return (frequency_mhz - 5950) // 5
    return None


def modes_fit_combination(
    active_modes: List[str],
    candidate_mode: str,
    combination: ConcurrentInterfaceCombination,
) -> bool:
    requested = active_modes + [candidate_mode]
    if len(requested) > combination.maximum_interfaces:
        return False
    for mode in set(requested):
        matching_limits = [limit for limit in combination.limits if mode in limit.modes]
        if not matching_limits:
            return False
        if requested.count(mode) > max(limit.maximum for limit in matching_limits):
            return False
    for limit in combination.limits:
        if sum(requested.count(mode) for mode in limit.modes) > limit.maximum:
            return False
    return True
