# Device deployment profiles

The systemd unit reads `/etc/totem/totem.env`. Device-specific values live in
this repository under `deploy/devices/` so hardware configuration is reviewed
and deployed from source rather than edited ad hoc on a unit.

For `metot`:

```bash
sudo install -d -m 0755 /etc/totem
sudo install -m 0644 deploy/devices/metot.env /etc/totem/totem.env
sudo raspi-config nonint do_spi 0
sudo systemctl restart totem.service
```

`raspi-config` must leave the setting in
[`devices/metot.boot-config.txt`](devices/metot.boot-config.txt) present in the
active Raspberry Pi boot configuration. Verify `/dev/spidev0.0` after reboot.
