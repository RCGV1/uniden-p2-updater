# SPDX-License-Identifier: GPL-3.0-only
"""Ambiguous transfers stop; these invented responses are simulation only."""

import json
from pathlib import Path
import tempfile
import unittest
from uniden_p2_updater.logging import CommunicationLogger
from uniden_p2_updater.transport import Wire, WireError
from uniden_p2_updater.updater import Updater, Journal, Firmware
from uniden_p2_updater.simulation import SyntheticImage, SimulatedBootloader


class FaultTarget(SimulatedBootloader):
    def write(self, raw):
        if raw == b"*ULE\r" and self.fault == "erase_reply":
            self.commands.append(b"*ULE")
            self.erase_count += 1
            self.pending.extend(b"ERASE END\r")
            return len(raw)
        if self.fault == "interrupt" and self.mode == "writing":
            raise KeyboardInterrupt()
        if self.fault == "bad_window" and raw == b"*WWS N\r":
            self.commands.append(b"*WWS N")
            self.pending.extend(b"ACK 16384\r")
            return len(raw)
        return super().write(raw)


class FailureTests(unittest.TestCase):
    def test_erase_response_window_and_interrupt_stop_without_reset(self):
        for fault in ("erase_reply", "bad_window", "interrupt"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                image = SyntheticImage.create()
                target = FaultTarget(image, size=16384, fault=fault)
                with CommunicationLogger(Path(folder) / "wire.jsonl", simulated=True) as logger:
                    journal = Journal(Path(folder) / "journal.json", simulated=True)
                    update = Updater(
                        image,
                        lambda _: Wire("SIMULATED", logger, transport=target),
                        journal,
                        simulated=True,
                        sleep=lambda _: None,
                        progress=lambda _: None,
                    )
                    with self.assertRaises((WireError, KeyboardInterrupt)):
                        update.run()
                self.assertNotIn(b"*OFF", target.commands)
                if fault == "bad_window":
                    self.assertEqual(target.erase_count, 0)
                    self.assertEqual(journal.data["stage"], "stopped_before_erase")
                else:
                    self.assertEqual(journal.data["stage"], "recovery_required")
                if fault == "erase_reply":
                    self.assertNotIn(b"*BIN N", target.commands)
                    self.assertNotIn(b"*PRG", target.commands)
                self.assertEqual(
                    json.loads((Path(folder) / "journal.json").read_text())["stage"],
                    journal.data["stage"],
                )

    def test_synthetic_or_forged_input_cannot_create_live_updater(self):
        image = SyntheticImage.create()
        forged = Firmware(image.data, image.sha256, image.version, image.checksum)
        for candidate in (image, forged):
            with self.assertRaises(ValueError):
                Updater(candidate, lambda _: self.fail("No I/O permitted"), None)

    def test_backup_version_mismatch_stops_before_programming_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            target = SimulatedBootloader(SyntheticImage.create())
            with CommunicationLogger(Path(folder) / "wire.jsonl", simulated=True) as logger:
                update = Updater(
                    target.image,
                    lambda _: Wire("SIMULATED", logger, transport=target),
                    Journal(Path(folder) / "journal.json"),
                    simulated=True,
                    backup_version="1.05.00",
                    sleep=lambda _: None,
                    progress=lambda _: None,
                )
                with self.assertRaises(WireError):
                    update.run()
            self.assertNotIn(b"PRG", target.commands)
            self.assertEqual(target.erase_count, 0)
