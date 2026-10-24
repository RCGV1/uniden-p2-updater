# SPDX-License-Identifier: GPL-3.0-only
"""Publication safety controls using invented files and scanner replies only."""

import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from uniden_p2_updater.backup import ConfigurationExport
from uniden_p2_updater.files import atomic_json, distinct_paths, reserve_output
from uniden_p2_updater.logging import CommunicationLogger
from uniden_p2_updater.transport import Wire
from uniden_p2_updater.updater import Journal, verified_backup


class SyntheticExportTransport:
    """Invented empty-scanner response fixture; opens no serial device."""

    def __init__(self, *, fail_exit=False):
        self.fail_exit = fail_exit
        self.responses = bytearray()
        self.commands = []
        self.close_count = 0

    def write(self, raw):
        self.commands.append(raw[:-1])
        packet = raw[:-1]
        if packet == b"EPG" and self.fail_exit:
            return len(raw)
        replies = {
            b"MDL": b"MDL,BCD996P2",
            b"VER": b"VER,Version 1.06.00",
            b"PRG": b"PRG,OK",
            b"EPG": b"EPG,OK",
            b"SCT": b"SCT,0",
            b"SIH": b"SIH,-1",
            b"SIT": b"SIT,-1",
            b"GLF": b"GLF,-1",
            b"GIE": b"GIE,-1",
        }
        response = replies.get(packet, packet.split(b",")[0] + b",0")
        if packet.startswith((b"LIH,", b"LIT,")):
            response = packet.split(b",")[0] + b",-1"
        self.responses.extend(response + b"\r")
        return len(raw)

    def read(self, size=1):
        result = bytes(self.responses[:size])
        del self.responses[:size]
        if not result:
            time.sleep(0.001)
        return result

    @property
    def in_waiting(self):
        return len(self.responses)

    def close(self):
        self.close_count += 1


class FastWire(Wire):
    def receive(self, timeout=3):
        return super().receive(min(0.03, timeout))


class FileSafetyTests(unittest.TestCase):
    def test_distinct_paths_rejects_canonical_alias_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            protected = root / "backup.json"
            protected.write_bytes(b"protected backup")
            with self.assertRaises(ValueError):
                distinct_paths(protected, root / "subdir" / ".." / "backup.json")
            self.assertEqual(protected.read_bytes(), b"protected backup")
            self.assertFalse((root / "subdir").exists())
            distinct_paths(protected, root / "journal.json", None, root / "wire.jsonl")

    def test_distinct_paths_rejects_symlink_alias(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            protected = root / "firmware.bin"
            protected.write_bytes(b"invented input")
            alias = root / "log-link"
            try:
                alias.symlink_to(protected)
            except (OSError, NotImplementedError) as error:
                self.skipTest(str(error))
            with self.assertRaises(ValueError):
                distinct_paths(protected, alias)
            self.assertEqual(protected.read_bytes(), b"invented input")

    def test_distinct_paths_rejects_hardlink_alias(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            protected = root / "backup.json"
            protected.write_bytes(b"protected backup")
            alias = root / "journal.json"
            try:
                os.link(protected, alias)
            except (OSError, NotImplementedError) as error:
                self.skipTest(str(error))
            with self.assertRaises(ValueError):
                distinct_paths(protected, alias)
            self.assertEqual(protected.read_bytes(), b"protected backup")

    def test_reservation_rejects_existing_file_and_dangling_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "output.json"
            path.write_bytes(b"existing history")
            with self.assertRaises(FileExistsError):
                reserve_output(path)
            self.assertEqual(path.read_bytes(), b"existing history")
            alias = root / "dangling.json"
            try:
                alias.symlink_to(root / "missing.json")
            except (OSError, NotImplementedError) as error:
                self.skipTest(str(error))
            with self.assertRaises(FileExistsError):
                reserve_output(alias)
            self.assertFalse((root / "missing.json").exists())

    def test_journal_and_logger_never_overwrite_existing_history(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history"
            path.write_bytes(b"existing history")
            with self.assertRaises(FileExistsError):
                Journal(path)
            with self.assertRaises(FileExistsError):
                CommunicationLogger(path)
            self.assertEqual(path.read_bytes(), b"existing history")

    def test_unique_checkpoint_preserves_old_fixed_temporary_filename(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            journal_path = root / "run.json"
            backup_path = root / "run.json.tmp"
            backup_path.write_bytes(b"protected backup")
            distinct_paths(journal_path, backup_path)
            journal = Journal(journal_path, simulated=True)
            journal.set("ready")
            journal.set("stopped_before_erase")
            self.assertEqual(backup_path.read_bytes(), b"protected backup")
            self.assertEqual(json.loads(journal_path.read_text())["stage"], "stopped_before_erase")
            self.assertEqual({path.name for path in root.iterdir()}, {"run.json", "run.json.tmp"})

    def test_failed_atomic_serialization_preserves_previous_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "journal.json"
            atomic_json(path, {"stage": "ready"})
            original = path.read_bytes()
            with self.assertRaises(TypeError):
                atomic_json(path, {"not_json": {1, 2}})
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual([item.name for item in root.iterdir()], ["journal.json"])


class BackupSafetyTests(unittest.TestCase):
    def export(self, root, *, fail_exit=False):
        transport = SyntheticExportTransport(fail_exit=fail_exit)
        path = root / "backup.json"
        with CommunicationLogger(root / "wire.jsonl", simulated=True) as logger:
            with FastWire("SIMULATED", logger, transport=transport) as wire:
                result = ConfigurationExport(wire, path).run()
        return path, transport, result

    def test_valid_invented_export_is_accepted_without_hardware(self):
        with tempfile.TemporaryDirectory() as folder:
            path, transport, result = self.export(Path(folder))
            metadata = verified_backup(path)
            self.assertTrue(result["complete"])
            self.assertEqual(metadata["firmware"], "1.06.00")
            self.assertEqual(transport.close_count, 1)

    def test_exit_timeout_persists_incomplete_flags_rejects_backup_and_closes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path, transport, result = self.export(root, fail_exit=True)
            persisted = json.loads(path.read_text())
            for archive in (result, persisted):
                self.assertIs(archive["complete"], False)
                self.assertIs(archive["program_mode_exited"], False)
                self.assertIn("timeout", archive["exit_error"].lower())
            with self.assertRaises(ValueError):
                verified_backup(path)
            self.assertEqual(transport.commands[-1], b"EPG")
            self.assertEqual(transport.close_count, 1)
            events = [json.loads(line) for line in (root / "wire.jsonl").read_text().splitlines()]
            self.assertEqual(events[-1]["event"], "wire_close")
            self.assertTrue(all(event["simulated"] for event in events))

    def test_backup_completion_flags_require_actual_booleans(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path, _, _ = self.export(root)
            baseline = json.loads(path.read_text())
            for name in ("complete", "program_mode_exited"):
                for value in ("false", "true", 1, 0, None, False):
                    with self.subTest(field=name, value=value):
                        bad = copy.deepcopy(baseline)
                        bad[name] = value
                        path.write_text(json.dumps(bad))
                        with self.assertRaises(ValueError):
                            verified_backup(path)

    def test_backup_requires_record_objects_model_and_matching_version_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path, _, _ = self.export(root)
            baseline = json.loads(path.read_text())
            mutations = []
            bad = copy.deepcopy(baseline)
            bad["records"] = [1]
            mutations.append(bad)
            bad = copy.deepcopy(baseline)
            bad["records"] = []
            mutations.append(bad)
            bad = copy.deepcopy(baseline)
            bad["model"] = "BCD325P2"
            mutations.append(bad)
            for command in ("MDL", "VER"):
                bad = copy.deepcopy(baseline)
                bad["records"] = [
                    record for record in bad["records"] if record["request"] != command
                ]
                mutations.append(bad)
            bad = copy.deepcopy(baseline)
            bad["firmware"] = "1.07.00"
            mutations.append(bad)
            bad = copy.deepcopy(baseline)
            bad["firmware"] = "not a version"
            mutations.append(bad)
            bad = copy.deepcopy(baseline)
            for record in bad["records"]:
                if record["request"] == "MDL":
                    record["fields"] = ["MDL", "BCD325P2"]
            mutations.append(bad)
            for index, bad in enumerate(mutations):
                with self.subTest(mutation=index):
                    path.write_text(json.dumps(bad))
                    with self.assertRaises(ValueError):
                        verified_backup(path)


if __name__ == "__main__":
    unittest.main()
