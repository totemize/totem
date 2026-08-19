# E-Ink displays

Totem supports these registered display drivers:

| Driver | Panel | Host |
|---|---|---|
| `waveshare_2in13` | Waveshare 2.13-inch | Raspberry Pi 4 and earlier |
| `waveshare_2in13_pi5` | Waveshare 2.13-inch | Raspberry Pi 5 |
| `waveshare_2in13_pi5_sw_cs` | Waveshare 2.13-inch, software chip select | Raspberry Pi 5 |
| `waveshare_3in7` | Waveshare 3.7-inch | Generic Raspberry Pi |
| `waveshare_3in7_pi5` | Waveshare 3.7-inch | Raspberry Pi 5 |
| `mock_eink` | In-memory test transport | Development and CI |

Set `EINK_DISPLAY_TYPE` to `2in13` or `3in7` when using auto-detection. For
hardware smoke tests, set `TOTEM_EINK_DRIVER` to an exact registered name.

The default pin assignments are inherited from the Waveshare reference
drivers. They can be overridden with `EINK_RST_PIN`, `EINK_DC_PIN`,
`EINK_CS_PIN`, and `EINK_BUSY_PIN`. Pi 5 drivers use `gpiod` and `spidev`.

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
