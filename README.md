# uniden-p2-updater

An unofficial native Python command-line updater for the **Uniden BCD996P2**, using its front USB connection without a Windows runtime. The supported hardware label prefix is **378Z** and the only accepted firmware is the pinned official **1.11.07** file.

The update sequence was physically validated on one 378Z scanner using Apple Silicon macOS: 1.06.00 → 1.11.07, 65 acknowledged packets, matching device checksum and repeated post-update version checks. This standalone release adds file-protection and protocol checks tested offline. The revised release has not been flashed again. Linux/Windows hardware operation, other units, rear RS-232 and interrupted physical recovery remain unverified. See [validation](docs/validation.md).

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

Acquire the original firmware through [Uniden's product downloads](https://www.uniden.info/download/index.cfm?s=bcd996p2), then inspect it locally:

```sh
uniden-p2-update --inspect --firmware /path/to/BCD996P2_V1_11_07.bin
```

| Required original | Value |
|---|---|
| Model / firmware | BCD996P2 / 1.11.07 |
| File bytes | 1,130,496 |
| SHA-256 | `4b63481f3c53025e561fe412f6b5f977dd376545ab9fc32d5d5a4b47195534d9` |

The vendor page may provide a Windows installer rather than a raw image. This tool requires the original `.bin` obtained through the vendor update workflow; an installer is not a valid firmware input.

There is no override for a different image or hash. `--inspect` opens no serial interface. Supplying `--firmware` to dry-run uses the validated original as simulated transfer input; the default uses invented bytes.

## Identify and export settings

Use an explicitly identified front USB serial port. For example, replace `/dev/cu.usbmodemXXXX` with the scanner's current macOS device path; Windows uses a name such as `COM3`.

```sh
uniden-p2-update --preflight --firmware /path/to/BCD996P2_V1_11_07.bin --port /dev/cu.usbmodemXXXX --log logs/preflight.jsonl
uniden-p2-backup --port /dev/cu.usbmodemXXXX --output logs/settings.json --log logs/settings-wire.jsonl
```

Preflight sends model/version queries only. The exporter uses documented getters and PRG/EPG mode transitions, briefly pausing scanning. It writes a readable-settings archive, **not a full memory image**, and no automated restore is implemented. Protected, malformed or incomplete exports cannot satisfy the flashing prerequisite. An archive is not cryptographically authenticated or uniquely bound to a physical scanner. Before normal flashing, its recorded firmware version must match the connected scanner.

## Explicit firmware update

Verify the **378Z** prefix on the scanner's physical serial label, keep stable scanner power and USB connected, and use the completed export:

```sh
uniden-p2-update --flash --firmware /path/to/BCD996P2_V1_11_07.bin --port /dev/cu.usbmodemXXXX --serial-prefix 378Z --backup logs/settings.json --log logs/flash-wire.jsonl --journal logs/flash-update.json
```

This command erases/programs application firmware. It rejects another model, an unknown USB location, a nonmatching backup version, an already-current/newer installed version, and input/output path aliases. Logs, journals and exports require fresh filenames. USB reconnection follows the original nonempty physical location and a serial number when the interface provides one. A location anchor cannot identify a swapped same-model device without a unique serial number.

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

BCD325P2, 378A hardware, arbitrary firmware, raw firmware extraction and activation are unsupported. The implementation follows BC_VUP3 protocol behavior observed during interoperability analysis. [Sources and attribution](docs/provenance.md) distinguish this P2 implementation from earlier Python flashers and SD-card update tools; no historical-first or clean-room claim is made.

**GPL-3.0-only.** See [LICENSE](LICENSE), [COPYRIGHT](COPYRIGHT) and [dependency notices](THIRD_PARTY_NOTICES.md). This project is not affiliated with or endorsed by Uniden.
