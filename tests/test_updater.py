# SPDX-License-Identifier: GPL-3.0-only
"""Synthetic transfer and fault controls; no vendor image or hardware required."""

import json
from pathlib import Path
import tempfile
import unittest
from uniden_p2_updater.logging import CommunicationLogger
from uniden_p2_updater.transport import Wire, WireError
from uniden_p2_updater.updater import (
    Firmware,
    Updater,
    Journal,
    handshake_size,
    verify_checksum,
    verified_backup,
)
from uniden_p2_updater.simulation import SimulatedBootloader, SyntheticImage


class FastWire(Wire):
    def receive(self, timeout=3):
        return super().receive(min(0.03, timeout))


class UpdaterTests(unittest.TestCase):
    def run_target(self, folder, *, fault=None, size=1024, recover=False):
        image = SyntheticImage.create()
        target = SimulatedBootloader(image, size=size, fault=fault)
        if recover:
            target.mode = "bootloader"
        logger = CommunicationLogger(Path(folder) / "wire.jsonl", simulated=True)

        def factory(phase):
            return FastWire("SIMULATED", logger, transport=target, flow=True)

        journal = Journal(Path(folder) / "journal.json", simulated=True)
        updater = Updater(
            image,
            factory,
            journal,
            sleep=lambda _: None,
            progress=lambda _: None,
            simulated=True,
        )
        return image, target, updater, journal

    def test_full_synthetic_payload_ack_checksum_reboot_and_postcheck(self):
        with tempfile.TemporaryDirectory() as folder:
            image, target, updater, journal = self.run_target(folder)
            result = updater.run()
            self.assertEqual(result["stage"], "complete")
            self.assertEqual(bytes(target.received), image.data[:-65536])
            self.assertEqual(len(target.received), 1064960)
            self.assertEqual(target.erase_count, 1)
            self.assertEqual(result["verified_versions"], ["1.11.07"] * 3)
            self.assertNotIn(b"*BIN Y", target.commands)
            self.assertFalse(any(p.startswith(b"*RMV") for p in target.commands))
            self.assertEqual(
                [p for p in target.commands if p.startswith(b"*")][:8],
                [
                    b"*MDL",
                    b"*SPD 5",
                    b"*SCB 1",
                    b"*WWS N",
                    b"*ULE",
                    b"*BIN N",
                    b"*PRG",
                    b"*OFF",
                ],
            )

    def test_wrong_model_never_erases(self):
        with tempfile.TemporaryDirectory() as folder:
            _, target, updater, journal = self.run_target(folder, fault="wrong_model")
            with self.assertRaises(WireError):
                updater.run()
            self.assertEqual(target.erase_count, 0)
            self.assertEqual(journal.data["stage"], "stopped_before_erase")

    def test_bad_ack_never_retries_packet_or_reboots(self):
        with tempfile.TemporaryDirectory() as folder:
            _, target, updater, journal = self.run_target(folder, fault="nak")
            with self.assertRaises(WireError):
                updater.run()
            self.assertEqual(len(target.received), 1024)
            self.assertNotIn(b"*OFF", target.commands)
            self.assertEqual(journal.data["stage"], "recovery_required")

    def test_lost_ack_is_not_assumed_successful(self):
        with tempfile.TemporaryDirectory() as folder:
            _, target, updater, journal = self.run_target(folder, fault="missing_ack")
            with self.assertRaises(WireError):
                updater.run()
            self.assertEqual(updater.bytes_acknowledged, 0)
            self.assertEqual(len(target.received), 1024)
            self.assertNotIn(b"*OFF", target.commands)

    def test_checksum_mismatch_keeps_target_in_bootloader(self):
        with tempfile.TemporaryDirectory() as folder:
            _, target, updater, journal = self.run_target(folder, fault="checksum")
            with self.assertRaises(WireError):
                updater.run()
            self.assertNotIn(b"*OFF", target.commands)
            self.assertFalse(updater.checksum_verified)
            self.assertEqual(journal.data["stage"], "recovery_required")

    def test_invalid_handshake_stops_before_erasing(self):
        with tempfile.TemporaryDirectory() as folder:
            _, target, updater, _ = self.run_target(folder, size=1000)
            with self.assertRaises(WireError):
                updater.run()
            self.assertEqual(target.erase_count, 0)

    def test_recovery_skips_normal_mode_service_transition(self):
        with tempfile.TemporaryDirectory() as folder:
            _, target, updater, journal = self.run_target(folder, recover=True)
            updater.run(recover=True)
            self.assertNotIn(b"FWM,Uniden", target.commands)
            self.assertEqual(journal.data["stage"], "complete")

    def test_handshake_and_checksum_parser_bounds(self):
        for response in [
            b"WWS 0",
            b"WWS -1",
            b"WWS 1000",
            b"WWS 65536",
            b"ERR",
            b"WWS 1024 extra",
            b"ACK 1024",
            b"BOGUS 1024",
        ]:
            with self.assertRaises(WireError):
                handshake_size(response, 1064960)
        self.assertEqual(handshake_size(b"WWS 1024", 1064960), 1024)
        verify_checksum(b"SUM = 2D82H", 0x2D82)
        for response in [
            b"SUM = 2D83H",
            b"SUM 2D82",
            b"SUM = 00002D82",
            b"SUM = xyz",
            b"SUM=2D82=2D82",
            b"BOGUS=2D82H",
            b"SUM=2D82HH",
        ]:
            with self.assertRaises(WireError):
                verify_checksum(response, 0x2D82)

    def test_pinned_image_and_completed_backup_are_mandatory(self):
        with tempfile.TemporaryDirectory() as folder:
            modified = Path(folder) / "bad.bin"
            data = bytearray(SyntheticImage.create().data)
            data[0] ^= 1
            modified.write_bytes(data)
            with self.assertRaises(ValueError):
                Firmware.load(modified)
            backup = Path(folder) / "backup.json"
            backup.write_text(
                json.dumps(
                    {
                        "model": "BCD996P2",
                        "complete": False,
                        "program_mode_exited": True,
                        "records": [1],
                    }
                )
            )
            with self.assertRaises(ValueError):
                verified_backup(backup)


if __name__ == "__main__":
    unittest.main()
