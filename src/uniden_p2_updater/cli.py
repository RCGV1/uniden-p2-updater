# SPDX-License-Identifier: GPL-3.0-only
"""Command-line entry point; simulation and inspection never enumerate USB."""

import argparse
from pathlib import Path
import sys
import time
import json
from . import __version__
from .files import distinct_paths
from .logging import CommunicationLogger
from .transport import Wire
from .updater import Firmware, Journal, Updater, verified_backup, require_tested_target
from .simulation import SimulatedBootloader, SyntheticImage
from .usb import usb_factory
from .catalog import firmware_catalog


def parser():
    p = argparse.ArgumentParser(description="Unofficial native BCD996P2 pinned-image updater")
    p.add_argument("--version", action="version", version=__version__)
    mode = p.add_mutually_exclusive_group(required=True)
    for name in ("inspect", "preflight", "dry-run", "flash", "list-firmware"):
        mode.add_argument("--" + name, action="store_true")
    p.add_argument(
        "--firmware",
        type=Path,
        help="Exact cataloged official image; optional for synthetic dry-run",
    )
    p.add_argument(
        "--allow-untested-target",
        action="store_true",
        help="Explicit live opt-in for cataloged targets without a physical transfer test",
    )
    p.add_argument("--port", help="Explicit front USB serial device")
    p.add_argument(
        "--serial-prefix",
        choices=["378Z"],
        help="Physically verified supported label prefix",
    )
    p.add_argument("--backup", type=Path, help="Completed readable-settings export")
    p.add_argument(
        "--recover",
        action="store_true",
        help="Explicit restart from bootloader; physical recovery unverified",
    )
    p.add_argument("--log", type=Path, default=Path("logs/update_wire.jsonl"))
    p.add_argument("--journal", type=Path, default=Path("logs/update_journal.json"))
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    updater = None
    try:
        if args.list_firmware:
            if (
                args.firmware
                or args.port
                or args.backup
                or args.serial_prefix
                or args.recover
                or args.allow_untested_target
            ):
                raise ValueError("--list-firmware does not accept transfer arguments")
            print(json.dumps(firmware_catalog(), indent=2))
            return 0
        if args.allow_untested_target and not args.flash:
            raise ValueError("--allow-untested-target requires --flash")
        if args.recover and not args.flash:
            raise ValueError("--recover requires --flash")
        if args.dry_run and (args.port or args.backup or args.serial_prefix):
            raise ValueError("Synthetic dry-run does not accept hardware or backup arguments")
        if not args.dry_run and args.firmware is None:
            raise ValueError("--firmware is required outside synthetic dry-run")
        if (args.flash or args.preflight) and not args.port:
            raise ValueError("An explicit front USB --port is required")
        if args.flash and (not args.serial_prefix or args.backup is None):
            raise ValueError("--flash requires --serial-prefix 378Z and --backup")
        distinct_paths(args.firmware, args.backup, args.log, args.journal)
        if not args.inspect:
            for output in (args.log, args.journal) if not args.preflight else (args.log,):
                if output.exists() or output.is_symlink():
                    raise ValueError(f"Use a fresh output path: {output}")
        image = Firmware.load(args.firmware) if args.firmware else SyntheticImage.create()
        if args.inspect:
            print(json.dumps(image.metadata(), indent=2))
            return 0
        if args.flash:
            require_tested_target(image.pin, allow_untested_target=args.allow_untested_target)
        backup = verified_backup(args.backup) if args.flash else None
        with CommunicationLogger(args.log, simulated=args.dry_run) as logger:
            if args.dry_run:
                target = SimulatedBootloader(image, size=16384)

                def factory(phase):
                    return Wire("SIMULATED", logger, transport=target, flow=phase == "bootloader")
            else:
                factory = usb_factory(args.port, logger)
            if args.preflight:
                # No updater instance/transition/journal needed for identification.
                with factory("normal") as wire:
                    wire.command(b"MDL", b"MDL,BCD996P2")
                    import re

                    response = wire.command(b"VER")
                    if not re.fullmatch(rb"VER,Version \d+\.\d+\.\d+", response):
                        raise ValueError("Malformed firmware version reply")
                print(
                    json.dumps(
                        {
                            **image.metadata(),
                            "observed_version_reply": response.decode("ascii"),
                            "flash_started": False,
                        },
                        indent=2,
                    )
                )
                return 0
            journal = Journal(
                args.journal,
                simulated=args.dry_run,
                firmware=image.metadata(),
                serial_prefix=args.serial_prefix,
                backup=backup,
                source="BCD996P2 interoperability implementation",
            )
            updater = Updater(
                image,
                factory,
                journal,
                simulated=args.dry_run,
                allow_untested_target=args.allow_untested_target,
                backup_version=backup["firmware"] if backup else None,
                sleep=(lambda _: None) if args.dry_run else time.sleep,
                progress=lambda message: print(
                    ("SIMULATED: " if args.dry_run else "") + message, flush=True
                ),
            )
            updater.run(recover=args.recover)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print(f"Update stopped: {type(exc).__name__}: {exc}", file=sys.stderr)
        if updater is not None and updater.erase_requested:
            print(
                "Erase was requested. Keep scanner power/USB connected and inspect the journal; no automatic retry or reset was sent.",
                file=sys.stderr,
            )
        return 1
