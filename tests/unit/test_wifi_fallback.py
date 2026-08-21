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


@pytest.mark.unit
def test_empty_ap_restarts_selection_but_an_associated_station_resets_idle(
    tmp_path,
):
    calls = tmp_path / "calls"
    marker = tmp_path / "idle"
    uptime = tmp_path / "uptime"

    fake_nmcli = tmp_path / "nmcli"
    fake_nmcli.write_text(
        """#!/usr/bin/env python3
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with Path(os.environ["CALL_LOG"]).open("a") as stream:
    stream.write("nmcli " + " ".join(args) + "\\n")
if args == ["--get-values", "GENERAL.CONNECTION", "device", "show", "wlan0"]:
    print("totem-ap")
elif args == ["connection", "down", "totem-ap"]:
    pass
else:
    raise SystemExit("unexpected nmcli call: " + repr(args))
"""
    )
    fake_nmcli.chmod(0o755)

    fake_iw = tmp_path / "iw"
    fake_iw.write_text(
        """#!/usr/bin/env python3
import os
if os.environ["IW_SCENARIO"] == "station":
    print("Station 00:11:22:33:44:55")
elif os.environ["IW_SCENARIO"] == "error":
    raise SystemExit(1)
"""
    )
    fake_iw.chmod(0o755)

    fake_systemctl = tmp_path / "systemctl"
    fake_systemctl.write_text(
        """#!/usr/bin/env python3
import os
from pathlib import Path
import sys
with Path(os.environ["CALL_LOG"]).open("a") as stream:
    stream.write("systemctl " + " ".join(sys.argv[1:]) + "\\n")
"""
    )
    fake_systemctl.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "CALL_LOG": str(calls),
            "IW_SCENARIO": "empty",
            "TOTEM_IW": str(fake_iw),
            "TOTEM_NMCLI": str(fake_nmcli),
            "TOTEM_SYSTEMCTL": str(fake_systemctl),
            "TOTEM_UPTIME_FILE": str(uptime),
            "TOTEM_WIFI_AP_IDLE_MARKER": str(marker),
            "TOTEM_WIFI_AP_IDLE_SECONDS": "600",
        }
    )

    def check(now, scenario="empty"):
        uptime.write_text(f"{now}.00 0.00\n")
        env["IW_SCENARIO"] = scenario
        subprocess.run(
            [SCRIPT, "--check-ap-idle"],
            check=True,
            env=env,
            text=True,
            capture_output=True,
        )

    check(100)
    assert marker.read_text() == "100\n"

    check(200, "station")
    assert not marker.exists()

    check(300)
    check(901)
    assert not marker.exists()
    assert calls.read_text().splitlines()[-2:] == [
        "nmcli connection down totem-ap",
        "systemctl --no-block start totem-wifi-fallback.service",
    ]

    marker.write_text("0\n")
    before = calls.read_text()
    check(1000, "error")
    assert not marker.exists()
    assert calls.read_text() == before + (
        "nmcli --get-values GENERAL.CONNECTION device show wlan0\n"
    )
