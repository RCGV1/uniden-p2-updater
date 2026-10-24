# SPDX-License-Identifier: GPL-3.0-only
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uniden_p2_updater.cli import main
from uniden_p2_updater.updater import Firmware


class CLITests(unittest.TestCase):
    def test_dry_run_needs_no_firmware_and_never_enumerates_or_opens_serial(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "wire.jsonl"
            journal = Path(folder) / "journal.json"
            with (
                patch("serial.Serial", side_effect=AssertionError("Hardware forbidden")),
                patch(
                    "serial.tools.list_ports.comports",
                    side_effect=AssertionError("Enumeration forbidden"),
                ),
                patch(
                    "uniden_p2_updater.cli.usb_factory",
                    side_effect=AssertionError("USB forbidden"),
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(
                    main(["--dry-run", "--log", str(log), "--journal", str(journal)]), 0
                )
            import json

            result = json.loads(journal.read_text())
            self.assertEqual(result["stage"], "complete")
            self.assertTrue(result["simulated"])
            self.assertTrue(result["firmware"]["simulated_input"])
            self.assertTrue(all(json.loads(x)["simulated"] for x in log.read_text().splitlines()))

    def test_alias_rejected_before_reading_firmware_or_touching_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            backup = root / "backup.json"
            backup.write_text("preserve")
            with (
                patch.object(
                    Firmware,
                    "load",
                    side_effect=AssertionError("Too late to check paths"),
                ),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                code = main(
                    [
                        "--flash",
                        "--firmware",
                        str(root / "firmware.bin"),
                        "--port",
                        "UNUSED",
                        "--serial-prefix",
                        "378Z",
                        "--backup",
                        str(backup),
                        "--journal",
                        str(backup),
                        "--log",
                        str(root / "new.jsonl"),
                    ]
                )
            self.assertEqual(code, 1)
            self.assertEqual(backup.read_text(), "preserve")
            self.assertFalse((root / "new.jsonl").exists())

    def test_invalid_inputs_and_recovery_never_open_hardware(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch(
                "uniden_p2_updater.cli.usb_factory",
                side_effect=AssertionError("No USB"),
            ),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            file = Path(folder) / "bad.bin"
            file.write_bytes(b"invented")
            for args in (
                ["--inspect", "--firmware", str(file)],
                ["--dry-run", "--recover"],
                ["--flash", "--port", "UNUSED", "--firmware", str(file)],
                ["--dry-run", "--port", "UNUSED"],
                ["--preflight"],
            ):
                with self.subTest(args=args):
                    self.assertEqual(main(args), 1)
