import os
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).parents[2] / (
    "deploy/ansible/roles/network/files/" "totem-wifi-fallback"
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("scenario", "expected_activation"),
    [("connected", None), ("peer", "totem-peer"), ("isolated", "totem-ap")],
)
def test_wifi_fallback_prefers_active_then_peer_then_ap(
    tmp_path, scenario, expected_activation
):
    calls = tmp_path / "calls"
    fake_nmcli = tmp_path / "nmcli"
    fake_nmcli.write_text(
        """#!/usr/bin/env python3
import os
from pathlib import Path
import sys

args = sys.argv[1:]
log = Path(os.environ["CALL_LOG"])
with log.open("a") as stream:
    stream.write(" ".join(args) + "\\n")

if args == ["--get-values", "GENERAL.CONNECTION", "device", "show", "wlan0"]:
    print("infra" if os.environ["SCENARIO"] == "connected" else "--")
elif args == ["radio", "wifi", "on"]:
    pass
elif args == [
    "--terse", "--fields", "SSID", "device", "wifi", "list",
    "ifname", "wlan0", "--rescan", "yes",
]:
    if os.environ["SCENARIO"] == "peer":
        print("!Totem")
elif len(args) >= 5 and args[2:4] == ["connection", "up"]:
    pass
else:
    raise SystemExit("unexpected nmcli call: " + repr(args))
"""
    )
    fake_nmcli.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "CALL_LOG": str(calls),
            "SCENARIO": scenario,
            "TOTEM_NMCLI": str(fake_nmcli),
            "TOTEM_SLEEP": "/bin/true",
            "TOTEM_WIFI_GRACE_SECONDS": "0",
            "TOTEM_WIFI_JITTER_SECONDS": "0",
        }
    )

    subprocess.run(  # noqa: E501
        [SCRIPT], check=True, env=env, text=True, capture_output=True
    )
    activations = [
        line.split()[4]
        for line in calls.read_text().splitlines()
        if " connection up " in " " + line + " "
    ]
    expected = [] if expected_activation is None else [expected_activation]
    assert activations == expected
