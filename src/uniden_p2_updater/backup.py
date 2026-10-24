# SPDX-License-Identifier: GPL-3.0-only
"""Export documented configuration getters; PRG/EPG briefly pause scanning.

This archive is configuration data, not firmware or license storage. It retains
raw replies for reconstruction. No configuration setter or delete is implemented.
Restore to hardware is not implemented or claimed to have been tested.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from .logging import CommunicationLogger
from .transport import Wire, WireError
from .files import reserve_output, atomic_json, distinct_paths

GLOBAL_GETTERS = frozenset(
    {
        "MDL",
        "VER",
        "VOL",
        "SQL",
        "P25",
        "BKL",
        "COM",
        "KBP",
        "OMS",
        "PRI",
        "AGV",
        "SCT",
        "SIH",
        "SIT",
        "QSL",
        "SCO",
        "CLC",
        "WXS",
        "CNT",
        "DUD",
        "SCN",
        "DBC",
        "GDO",
        "BSP",
        "RMB",
        "MEM",
        "SHK",
        "CSG",
        "GLF",
        "GIE",
    }
)
INDEX_GETTERS = frozenset(
    {
        "SIN",
        "TRN",
        "SIF",
        "MCP",
        "ABP",
        "TFQ",
        "QGL",
        "GIN",
        "CIN",
        "TIN",
        "LIN",
        "GLI",
        "SLI",
    }
)


def permitted_getter(command):
    if command in GLOBAL_GETTERS:
        return True
    pieces = command.split(",")
    if len(pieces) == 2 and pieces[0] in {"LIH", "LIT"}:
        return pieces[1] in {"POI", "DROAD", "DXING"}
    if len(pieces) != 2 or not re.fullmatch(r"\d+", pieces[1]):
        return False
    name, value = pieces[0], int(pieces[1])
    if name in INDEX_GETTERS:
        return 0 <= value <= 45000
    return (
        (name in {"BBS", "TON", "CSP", "CBP"} and 0 <= value <= 9)
        or (name == "SGP" and 1 <= value <= 5)
        or (name == "SSP" and value in {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 15})
    )


class ConfigurationExport:
    def __init__(self, wire, output):
        self.wire, self.output = wire, Path(output)
        reserve_output(self.output)
        self.records = []
        self.data = {
            "schema": 1,
            "utc": datetime.now(timezone.utc).isoformat(),
            "model": "BCD996P2",
            "port": wire.port,
            "complete": False,
            "program_mode_exited": False,
            "records": self.records,
            "warnings": [],
            "coverage": "Documented readable settings and system/site/group/channel/location chains; not raw memory or license storage",
            "restore_implemented": False,
        }

    def checkpoint(self):
        atomic_json(self.output, self.data)

    def get(self, command, *, optional=False):
        if not permitted_getter(command):
            raise ValueError(f"Not a documented getter: {command}")
        raw = self.wire.command(command.encode("ascii"))
        fields = raw.decode("ascii", errors="backslashreplace").split(",")
        if len(fields) == 2 and fields[1] in {"ERR", "NG", "FER", "ORER"}:
            raise WireError(f"Scanner rejected {command!r}: {raw!r}")
        if fields[0] != command.split(",")[0] or len(fields) < 2:
            raise WireError(f"Unexpected configuration reply for {command}: {raw!r}")
        self.records.append({"request": command, "raw_hex": (raw + b"\r").hex(), "fields": fields})
        return fields

    def optional(self, command):
        try:
            return self.get(command)
        except WireError as exc:
            # Only a complete explicit rejection permits continuing. Timeout or
            # an unrelated reply leaves synchronization unknown and stops export.
            if not str(exc).startswith("Scanner rejected"):
                raise
            self.data["warnings"].append({"command": command, "error": str(exc)})
            return None

    def chain(self, command, head, forward_field):
        seen = set()
        index = int(head)
        while index != -1:
            if index in seen or not 0 <= index <= 45000 or len(seen) >= 45000:
                raise WireError(f"Invalid/cyclic {command} index chain at {index}")
            seen.add(index)
            fields = self.get(f"{command},{index}")
            yield index, fields
            index = int(fields[forward_field])

    def list_values(self, command, limit=45000):
        seen = set()
        for _ in range(limit):
            fields = self.get(command)
            if fields[1] == "-1":
                return
            if tuple(fields) in seen:
                raise WireError(f"Repeating cursor response for {command}")
            seen.add(tuple(fields))
        raise WireError(f"Unterminated cursor for {command}")

    def groups(self, head):
        for index, group in self.chain("GIN", head, 6):
            item_command, forward = ("CIN", 12) if group[1] == "C" else ("TIN", 8)
            if group[1] not in {"C", "T"}:
                raise WireError(f"Unknown group type: {group[1]}")
            for _ in self.chain(item_command, group[8], forward):
                pass

    def run(self):
        entered = False
        self.checkpoint()
        try:
            if self.get("MDL") != ["MDL", "BCD996P2"]:
                raise WireError("Wrong scanner model")
            self.data["firmware"] = self.get("VER")[1].removeprefix("Version ")
            for name in ["VOL", "SQL", "P25"]:
                self.optional(name)
            self.wire.command(b"PRG", b"PRG,OK")
            entered = True
            for name in [
                "BKL",
                "COM",
                "KBP",
                "OMS",
                "PRI",
                "AGV",
                "QSL",
                "SCO",
                "CLC",
                "WXS",
                "CNT",
                "DUD",
                "SCN",
                "DBC",
                "GDO",
                "BSP",
                "RMB",
                "MEM",
                "SHK",
                "CSG",
            ]:
                self.optional(name)
            for name in ["BBS", "TON", "CSP", "CBP"]:
                for index in range(10):
                    self.optional(f"{name},{index}")
            for index in range(1, 6):
                self.optional(f"SGP,{index}")
            for index in [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 15]:
                self.optional(f"SSP,{index}")
            for name in ["GLF", "GIE"]:
                self.list_values(name)
            count = int(self.get("SCT")[1])
            head = self.get("SIH")[1]
            self.get("SIT")
            systems = 0
            for index, system in self.chain("SIN", head, 13):
                systems += 1
                print(f"Exporting system {systems}/{count}: {system[2]}", flush=True)
                if len(system) < 28:
                    raise WireError("Truncated SIN reply cannot establish a complete export")
                if system[27] not in {"0", "1"}:
                    raise WireError("Invalid system protection flag")
                if system[27] == "1":
                    raise WireError("Protected system cannot be completely exported")
                self.optional(f"QGL,{index}")
                if system[1] == "CNV":
                    self.groups(system[14])
                else:
                    trunk = self.get(f"TRN,{index}")
                    for site_index, site in self.chain("SIF", system[14], 12):
                        self.optional(f"ABP,{site_index}")
                        if site[23] == "CUSTOM":
                            self.get(f"MCP,{site_index}")
                        for _ in self.chain("TFQ", site[14], 5):
                            pass
                    self.groups(trunk[21])
                    for name in ["GLI", "SLI"]:
                        self.list_values(f"{name},{index}")
                self.checkpoint()
            if systems != count:
                raise WireError(f"System count mismatch: {systems}/{count}")
            for location_type in ["POI", "DROAD", "DXING"]:
                self.get(f"LIT,{location_type}")
                for _ in self.chain("LIN", self.get(f"LIH,{location_type}")[1], 7):
                    pass
            self.data["counts"] = dict(Counter(r["request"].split(",")[0] for r in self.records))
            self.data["system_count"] = systems
            self.data["complete"] = True
        except BaseException as exc:
            self.data["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            if entered:
                try:
                    self.wire.command(b"EPG", b"EPG,OK")
                    self.data["program_mode_exited"] = True
                except Exception as exc:
                    self.data["exit_error"] = str(exc)
                    self.data["complete"] = False
            self.checkpoint()
        return self.data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        distinct_paths(args.output, args.log)
        for path in (args.output, args.log):
            if path.exists() or path.is_symlink():
                raise ValueError("Use new output and log paths")
    except ValueError as exc:
        parser.error(str(exc))
    try:
        with CommunicationLogger(args.log) as logger:
            with Wire(args.port, logger) as wire:
                result = ConfigurationExport(wire, args.output).run()
        print(json.dumps({k: v for k, v in result.items() if k != "records"}, indent=2))
        print("Archive SHA-256:", hashlib.sha256(args.output.read_bytes()).hexdigest())
        return 0 if result["complete"] else 1
    except Exception as exc:
        print(f"Export stopped: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
