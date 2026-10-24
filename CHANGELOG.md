# Changelog

## 0.2.0

- Fixed output reservation to reject dangling symlinks on Windows.

- Added an immutable exact-hash catalog for five official BCD996P2 firmware images and offline `--list-firmware` output.
- Preserved 1.11.07 as the recommended and only physically validated target; other cataloged live targets require `--allow-untested-target` and remain upgrade-only.
- Added catalog, version-gate and no-I/O listing coverage, plus early-prototype and contribution guidance.

## 0.1.0

- Native CLI for pinned official BCD996P2 1.11.07 firmware and 378Z hardware.
- Firmware inspection, explicit synthetic dry-run, front-USB preflight and readable-settings export.
- Exact model, window, erase-reply, packet and checksum checks with durable journals.
- Input/output alias protection, exclusive logs/exports and unique atomic checkpoints.
- Synthetic transfer/failure tests, package audit and cross-platform CI configuration.
