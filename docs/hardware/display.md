# E-Ink displays

Totem supports these registered display drivers:

| Driver | Panel | Host |
|---|---|---|
| `waveshare_2in13_v1` | Original Waveshare 2.13-inch | Raspberry Pi 4 and earlier |
| `waveshare_2in13_v2` | Waveshare 2.13-inch V2 panel | Raspberry Pi 4 and earlier |
| `waveshare_2in13_v3` | Waveshare 2.13-inch V3 | Raspberry Pi 4 and earlier |
| `waveshare_2in13_v4` | Waveshare 2.13-inch V4 | Raspberry Pi 4 and earlier |
| `waveshare_2in13` | Compatibility alias for `waveshare_2in13_v2` | Raspberry Pi 4 and earlier |
| `waveshare_2in13_pi5` | Waveshare 2.13-inch | Raspberry Pi 5 |
| `waveshare_2in13_pi5_sw_cs` | Waveshare 2.13-inch, software chip select | Raspberry Pi 5 |
| `waveshare_3in7` | Waveshare 3.7-inch | Generic Raspberry Pi |
| `waveshare_3in7_pi5` | Waveshare 3.7-inch | Raspberry Pi 5 |
| `mock_eink` | In-memory test transport | Development and CI |

Set `EINK_DISPLAY_TYPE` to `2in13_v1`, `2in13_v2`, `2in13_v3`,
`2in13_v4`, or `3in7` when using
auto-detection (`2in13` remains a V2 alias). For
normal manager/service operation and hardware smoke tests, set
`TOTEM_EINK_DRIVER` to an exact registered name. An explicit constructor
argument takes precedence over the environment.

The versioned drivers use Waveshare's standard HAT assignments: reset GPIO17,
data/command GPIO25, busy GPIO24, power GPIO18, and SPI0 CE0. Pi 5 drivers use
`gpiod` and `spidev`.

The `Rev 2.1` silkscreen identifies the HAT/level-shifter board revision, not
the e-paper controller revision. Select V1/V2/V3/V4 from the label on the panel
or flex cable; do not infer it from `Rev 2.1`.

Render text through the manager with an explicit revision:

```bash
PYTHONPATH=src python examples/display_text.py \
  --driver waveshare_2in13_v4 \
  --text $'hello world\n<3 totem'
```

`metot` uses the checked-in [`deploy/devices/metot.env`](../../deploy/devices/metot.env)
profile. Install that file as `/etc/totem/totem.env`; the systemd unit reads it
on startup. SPI0 must also be enabled persistently in the Raspberry Pi boot
configuration (`dtparam=spi=on`).

Mock behavior must be explicit:

```python
from totem.managers.display_manager import DisplayManager

display = DisplayManager("mock_eink", allow_mock=True)
display.display_text("Totem")
```

Drivers that lose access to GPIO or SPI during initialization report mock
state. The facade rejects that state unless mock operation was explicitly
allowed, preventing a hardware deployment from silently succeeding in memory.

The display manager owns an operation lock. Applications should share one
manager instance rather than opening GPIO/SPI independently from multiple
processes.
