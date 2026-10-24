# uniden-p2-updater

An unofficial native Python command-line updater for the **Uniden BCD996P2**, using its front USB connection without a Windows runtime. It accepts five exact official BCD996P2 images: **1.10.02, 1.11.03, 1.11.04, 1.11.06, and 1.11.07**. The supported hardware label prefix is **378Z**.

> **Early prototype: help wanted.** Only firmware 1.11.07 has been physically transferred with this implementation, on one 378Z scanner using Apple Silicon macOS. The standalone v0.2 release has not itself been flashed. The other four images are exact-hash catalog entries, but live use requires an explicit `--allow-untested-target` opt-in. We are looking for **testers and contributors** to expand firmware support, document the flashing protocol, improve offline tests, and establish cross-platform support. Read [CONTRIBUTING.md](CONTRIBUTING.md) before sharing evidence or attempting hardware validation.

The 1.11.07 update completed with 65 acknowledged packets, a matching device checksum and repeated post-update version checks. Linux/Windows hardware operation, other units, rear RS-232 and interrupted physical recovery remain unverified. See [validation](docs/validation.md).

## Install

Python 3.10+ and pyserial are required. From this source directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

On Windows, activate with `.venv\Scripts\Activate.ps1`. This project needs no elevated installer and includes no firmware download client, Windows runtime or vendor firmware.

## Start offline

```sh
uniden-p2-update --help
uniden-p2-update --dry-run --log logs/synthetic-wire.jsonl --journal logs/synthetic-update.json
```

Dry-run uses deterministic **invented bytes and simulated responses**, clearly labeled in every log and journal. It opens no serial device and does not enumerate USB. It requires no firmware file. Synthetic input is unavailable to the normal flashing path.

List the exact accepted firmware pins offline, then acquire an original image through [Uniden's product downloads](https://www.uniden.info/download/index.cfm?s=bcd996p2) and inspect it locally:

```sh
uniden-p2-update --list-firmware
uniden-p2-update --inspect --firmware /path/to/BCD996P2_V1_11_07.bin
```

The catalog pins exact whole-file hashes, versions and device checksums. Version 1.11.07 is the recommended target and the only physically validated target. The other four versions are available for offline inspection and, with an explicit live-flash opt-in, for upgrade-only updates on supported 378Z hardware.

The vendor page may provide a Windows installer rather than a raw image. This tool requires the original `.bin` obtained through the vendor update workflow; an installer is not a valid firmware input.

There is no override for an image outside the catalog or a mismatched hash. `--inspect` and `--list-firmware` open no serial interface. Supplying `--firmware` to dry-run uses the selected catalog image as simulated transfer input; the default uses invented bytes.

## Identify and export settings

Use an explicitly identified front USB serial port. For example, replace `/dev/cu.usbmodemXXXX` with the scanner's current macOS device path; Windows uses a name such as `COM3`.

```sh
uniden-p2-update --preflight --firmware /path/to/BCD996P2_V1_11_07.bin --port /dev/cu.usbmodemXXXX --log logs/preflight.jsonl
uniden-p2-backup --port /dev/cu.usbmodemXXXX --output logs/settings.json --log logs/settings-wire.jsonl
```

Preflight sends model/version queries only. The exporter uses documented getters and PRG/EPG mode transitions, briefly pausing scanning. It writes a readable-settings archive, **not a full memory image**, and no automated restore is implemented. Protected, malformed or incomplete exports cannot satisfy the flashing prerequisite. An archive is not cryptographically authenticated or uniquely bound to a physical scanner. Before normal flashing, its recorded firmware version must match the connected scanner.

## Explicit firmware update

Verify the **378Z** prefix on the scanner's physical serial label, keep stable scanner power and USB connected, and use the completed export. The example uses the only physically validated target:

```sh
uniden-p2-update --flash --firmware /path/to/BCD996P2_V1_11_07.bin --port /dev/cu.usbmodemXXXX --serial-prefix 378Z --backup logs/settings.json --log logs/flash-wire.jsonl --journal logs/flash-update.json
```

This command erases/programs application firmware. It rejects another model, an unknown USB location, a nonmatching backup version, an already-current/newer installed version, and input/output path aliases. Logs, journals and exports require fresh filenames. USB reconnection follows the original nonempty physical location and a serial number when the interface provides one. A location anchor cannot identify a swapped same-model device without a unique serial number.

For a cataloged target other than 1.11.07, add `--allow-untested-target` to `--flash`. This opt-in acknowledges that the image is pinned and identified but its transfer has not been physically validated by this project. Normal-mode updates still refuse downgrades and require the scanner to report an older version. Recovery checks the archive’s pre-update version because the installed version is unavailable in the loader.

During transfer, the client requires the exact negotiated-window reply, erase acknowledgement, every packet ACK, terminal marker, expected device checksum and three post-update version replies. Boot-region-writing mode is disabled. It sends no licensing commands.

A timeout, NAK, short write, interrupt or checksum failure stops without resending an ambiguous firmware packet or automatically rebooting. If erase was requested, keep power/USB connected and inspect the journal. [Failure and explicit recovery behavior](docs/protocol.md#failure-and-recovery) explains the separate `--recover` option; physical interrupted-update recovery is unverified.

Full wire logs contain the transmitted firmware bytes; settings logs contain configuration data. They are local diagnostic files excluded from this source release. Review them before sharing.

## Development and distributions

```sh
python -m pip install . build ruff
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
python tools/audit_release.py
python -m build
python tools/audit_release.py --artifacts dist
```

All unit tests use invented data and explicit transports. No vendor image, USB connection or proprietary utility is needed. Optional read-only checks with a user-supplied official image are documented in [validation](docs/validation.md). The CI configuration tests simulated behavior and packaging across operating systems; that does not establish hardware support.

## Scope and provenance

BCD325P2, 378A hardware, arbitrary firmware, raw firmware extraction and activation are unsupported. The implementation follows BC_VUP3 protocol behavior observed during interoperability analysis. [Sources and attribution](docs/provenance.md) distinguish this P2 implementation from earlier Python flashers and SD-card update tools; no historical-first or clean-room claim is made. Contributions and tester guidance are in [CONTRIBUTING.md](CONTRIBUTING.md).

**GPL-3.0-only.** See [LICENSE](LICENSE), [COPYRIGHT](COPYRIGHT) and [dependency notices](THIRD_PARTY_NOTICES.md). This project is not affiliated with or endorsed by Uniden.
