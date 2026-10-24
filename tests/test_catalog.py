# SPDX-License-Identifier: GPL-3.0-only
"""Exact firmware catalog, CLI listing, and version-gate coverage."""

import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from uniden_p2_updater.catalog import (
    FIRMWARE_PINS,
    PINS_BY_HASH,
    PINS_BY_VERSION,
    firmware_catalog,
)
from uniden_p2_updater.cli import main
from uniden_p2_updater.logging import CommunicationLogger
from uniden_p2_updater.transport import WireError
from uniden_p2_updater.updater import Journal, Updater, require_tested_target
from uniden_p2_updater.simulation import SimulatedBootloader, SyntheticImage


class CatalogTests(unittest.TestCase):
    def test_live_target_policy_requires_explicit_opt_in_for_unverified_images(self):
        for pin in FIRMWARE_PINS:
            with self.subTest(version=pin.version):
                if pin.physical_transfer_validated:
                    require_tested_target(pin)
                else:
                    with self.assertRaisesRegex(ValueError, "--allow-untested-target"):
                        require_tested_target(pin)
                require_tested_target(pin, allow_untested_target=True)

    def test_catalog_is_exact_and_immutable(self):
        self.assertEqual(len(FIRMWARE_PINS), 5)
        self.assertEqual(len({pin.version for pin in FIRMWARE_PINS}), 5)
        self.assertEqual(len({pin.sha256 for pin in FIRMWARE_PINS}), 5)
        self.assertEqual(set(PINS_BY_VERSION), {pin.version for pin in FIRMWARE_PINS})
        self.assertEqual(set(PINS_BY_HASH), {pin.sha256 for pin in FIRMWARE_PINS})
        self.assertEqual(sum(pin.physical_transfer_validated for pin in FIRMWARE_PINS), 1)
        self.assertEqual(
            next(pin.version for pin in FIRMWARE_PINS if pin.physical_transfer_validated),
            "1.11.07",
        )
        with self.assertRaises(TypeError):
            PINS_BY_HASH["invented"] = FIRMWARE_PINS[0]
        with self.assertRaises(TypeError):
            PINS_BY_VERSION["invented"] = FIRMWARE_PINS[0]

        catalog = firmware_catalog()
        self.assertEqual(catalog["recommended_version"], "1.11.07")
        self.assertFalse(catalog["other_models_supported"])
        self.assertEqual(len(catalog["images"]), 5)
        self.assertEqual(
            {item["version"] for item in catalog["images"]},
            {pin.version for pin in FIRMWARE_PINS},
        )

    def test_list_firmware_prints_catalog_without_usb_or_file_io(self):
        stdout = io.StringIO()
        with (
            patch("uniden_p2_updater.cli.usb_factory", side_effect=AssertionError("USB used")),
            patch("serial.Serial", side_effect=AssertionError("Serial opened")),
            patch(
                "serial.tools.list_ports.comports",
                side_effect=AssertionError("USB enumerated"),
            ),
            patch(
                "uniden_p2_updater.updater.Firmware.load", side_effect=AssertionError("file read")
            ),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(main(["--list-firmware"]), 0)
        self.assertEqual(json.loads(stdout.getvalue()), firmware_catalog())

    def test_untested_target_opt_in_is_rejected_outside_flash_before_io(self):
        for mode in ("--inspect", "--preflight", "--dry-run"):
            with self.subTest(mode=mode), contextlib.redirect_stderr(io.StringIO()):
                with patch(
                    "uniden_p2_updater.cli.usb_factory",
                    side_effect=AssertionError("USB used"),
                ):
                    self.assertEqual(main([mode, "--allow-untested-target"]), 1)

    def test_simulated_full_transfer_uses_selected_older_target_version(self):
        image = replace(SyntheticImage.create(), version="1.11.04")
        target = SimulatedBootloader(image, size=16384)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            logger = CommunicationLogger(root / "wire.jsonl", simulated=True)

            def factory(phase):
                from uniden_p2_updater.transport import Wire

                return Wire("SIMULATED", logger, transport=target, flow=phase == "bootloader")

            journal = Journal(root / "journal.json", simulated=True)
            updater = Updater(
                image,
                factory,
                journal,
                sleep=lambda _: None,
                progress=lambda _: None,
                simulated=True,
            )
            result = updater.run()
        self.assertEqual(result["stage"], "complete")
        self.assertEqual(result["verified_versions"], ["1.11.04"] * 3)
        self.assertEqual(bytes(target.received), image.payload)
        self.assertEqual(target.erase_count, 1)

    def test_equal_or_newer_installed_version_stops_before_erase(self):
        for installed in ("1.11.04", "1.11.06"):
            with self.subTest(installed=installed), tempfile.TemporaryDirectory() as folder:
                image = replace(SyntheticImage.create(), version="1.11.04")

                class InstalledVersionBootloader(SimulatedBootloader):
                    def write(self, raw):
                        result = super().write(raw)
                        if raw == b"VER\r":
                            self.pending.clear()
                            self.pending.extend(f"VER,Version {installed}\r".encode("ascii"))
                        return result

                target = InstalledVersionBootloader(image, size=16384)
                root = Path(folder)
                logger = CommunicationLogger(root / "wire.jsonl", simulated=True)

                def factory(phase):
                    from uniden_p2_updater.transport import Wire

                    return Wire("SIMULATED", logger, transport=target, flow=phase == "bootloader")

                journal = Journal(root / "journal.json", simulated=True)
                updater = Updater(
                    image,
                    factory,
                    journal,
                    sleep=lambda _: None,
                    progress=lambda _: None,
                    simulated=True,
                )
                with self.assertRaisesRegex(WireError, "already at or above target"):
                    updater.run()
                self.assertEqual(target.erase_count, 0)
                self.assertEqual(journal.data["stage"], "stopped_before_erase")


if __name__ == "__main__":
    unittest.main()
