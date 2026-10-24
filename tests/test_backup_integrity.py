# SPDX-License-Identifier: GPL-3.0-only
import copy
import json
from pathlib import Path
import tempfile
import unittest
from test_safety import SyntheticExportTransport, FastWire
from uniden_p2_updater.backup import ConfigurationExport
from uniden_p2_updater.logging import CommunicationLogger
from uniden_p2_updater.updater import verified_backup
from uniden_p2_updater.transport import WireError


class BackupIntegrityTests(unittest.TestCase):
    def test_inconsistent_record_bytes_counts_and_schema_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "backup.json"
            with CommunicationLogger(root / "wire.jsonl", simulated=True) as logger:
                with FastWire("SIMULATED", logger, transport=SyntheticExportTransport()) as wire:
                    baseline = ConfigurationExport(wire, path).run()
            verified_backup(path)
            for kind in ("raw", "count", "schema", "tail", "missing-count"):
                value = copy.deepcopy(baseline)
                if kind == "raw":
                    value["records"][0]["raw_hex"] = "00"
                if kind == "count":
                    value["system_count"] = 1
                if kind == "schema":
                    value["schema"] = True
                if kind == "tail":
                    record = next(r for r in value["records"] if r["request"] == "SIT")
                    record["fields"] = ["SIT", "1"]
                    record["raw_hex"] = b"SIT,1\r".hex()
                if kind == "missing-count":
                    value["records"] = [r for r in value["records"] if r["request"] != "SCT"]
                path.write_text(json.dumps(value))
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    verified_backup(path)

    def test_truncated_or_protected_system_never_marks_export_complete(self):
        class Systems(SyntheticExportTransport):
            def __init__(self, fields):
                super().__init__()
                self.fields = fields

            def write(self, raw):
                packet = raw[:-1]
                response = {b"SCT": b"SCT,1", b"SIH": b"SIH,0", b"SIN,0": self.fields}.get(packet)
                if response is None:
                    return super().write(raw)
                self.commands.append(packet)
                self.responses.extend(response + b"\r")
                return len(raw)

        for fields in (b"SIN,CNV,name", ("SIN,CNV,name," + ",".join(["0"] * 24) + ",1").encode()):
            with self.subTest(fields=fields), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                target = Systems(fields)
                with CommunicationLogger(root / "wire.jsonl", simulated=True) as logger:
                    with FastWire("SIMULATED", logger, transport=target) as wire:
                        export = ConfigurationExport(wire, root / "backup.json")
                        with self.assertRaises(WireError):
                            export.run()
                self.assertFalse(export.data["complete"])
                self.assertEqual(target.commands[-1], b"EPG")
