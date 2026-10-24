# SPDX-License-Identifier: GPL-3.0-only
import tempfile
from pathlib import Path
import unittest
from uniden_p2_updater.backup import permitted_getter, ConfigurationExport
from uniden_p2_updater.transport import WireError


class FakeWire:
    port = "SIMULATED"

    def __init__(self, fail=None):
        self.requests = []
        self.fail = fail

    def command(self, packet, expected=None):
        self.requests.append(packet)
        if packet == self.fail:
            raise WireError("Response timeout")
        if packet.startswith((b"LIH,", b"LIT,")):
            return packet.split(b",")[0] + b",-1"
        responses = {
            b"MDL": b"MDL,BCD996P2",
            b"VER": b"VER,Version 1.06.00",
            b"PRG": b"PRG,OK",
            b"EPG": b"EPG,OK",
            b"GLF": b"GLF,-1",
            b"GIE": b"GIE,-1",
            b"SCT": b"SCT,0",
            b"SIH": b"SIH,-1",
            b"SIT": b"SIT,-1",
            b"LIH": b"LIH,-1",
            b"LIT": b"LIT,-1",
        }
        return responses.get(packet, packet.split(b",")[0] + b",0")


class BackupTests(unittest.TestCase):
    def test_policy_denies_setters_and_destructive_commands(self):
        for command in [
            "CLR",
            "MMM,2468",
            "FWM,Uniden",
            "VOL,3",
            "SIN,1,newname",
            "CIN,2,00000000",
            "COM,115200,115200",
            "SIN,-1",
            "SIN,45001",
            "SIN,1\rCLR",
            "LIH",
            "LIT",
            "LIH,INVALID",
        ]:
            self.assertFalse(permitted_getter(command), command)
        for command in [
            "SIN,0",
            "CIN,45000",
            "COM",
            "GLF",
            "SSP,15",
            "SGP,5",
            "LIH,POI",
            "LIT,DROAD",
            "LIH,DXING",
        ]:
            self.assertTrue(permitted_getter(command), command)

    def test_empty_scanner_export_and_mode_exit(self):
        wire = FakeWire()
        with tempfile.TemporaryDirectory() as folder:
            result = ConfigurationExport(wire, Path(folder) / "backup.json").run()
            self.assertTrue(result["complete"])
            self.assertTrue(result["program_mode_exited"])
            self.assertFalse(result["restore_implemented"])
            self.assertEqual(wire.requests[-1], b"EPG")
            self.assertEqual(result["system_count"], 0)
            for kind in [b"POI", b"DROAD", b"DXING"]:
                self.assertIn(b"LIH," + kind, wire.requests)

    def test_command_prefixed_error_is_not_configuration_data(self):
        wire = FakeWire()
        wire.command = lambda *args: b"DBC,ERR"
        with tempfile.TemporaryDirectory() as folder:
            export = ConfigurationExport(wire, Path(folder) / "backup.json")
            self.assertIsNone(export.optional("DBC"))
            self.assertEqual(export.records, [])
            self.assertEqual(len(export.data["warnings"]), 1)

    def test_exit_program_mode_even_after_read_failure(self):
        wire = FakeWire(fail=b"SCT")
        with tempfile.TemporaryDirectory() as folder:
            export = ConfigurationExport(wire, Path(folder) / "backup.json")
            with self.assertRaises(WireError):
                export.run()
            self.assertEqual(wire.requests[-1], b"EPG")
            self.assertFalse(export.data["complete"])

    def test_cycle_is_not_reported_as_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            export = ConfigurationExport(FakeWire(), Path(folder) / "backup.json")
            export.get = lambda command: ["TEST", "1"]
            with self.assertRaises(WireError):
                list(export.chain("SIN", 1, 1))


if __name__ == "__main__":
    unittest.main()
