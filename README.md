# Totem

Totem is a composable, Nostr-native hardware platform with mesh capabilities.

This repository contains the Python software used to manage Totem devices and
their hardware drivers. Mesh networking is provided by FIPS, while the local
software focuses on hardware control and on-device services.

The Python project lives in [`totem/python`](totem/python/README.md). It includes
device support for e-ink displays, NFC readers, NVMe storage, and Wi-Fi
controllers, together with mock drivers, tests, examples, and Raspberry Pi
setup utilities.

## Setup

```bash
cd totem/python
poetry install
```

See [`totem/python/README.md`](totem/python/README.md) for usage, testing, and
hardware setup details.
