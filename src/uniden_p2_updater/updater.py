# SPDX-License-Identifier: GPL-3.0-only
"""BCD996P2 firmware updater derived from official BC_VUP3 3.06 behavior.

Native Python/pyserial; no Windows runtime. Only the pinned official 1.11.07
image is accepted. No license operations, boot-region writes, or arbitrary
firmware inputs are supported. --inspect is offline; --preflight is read-only;
--dry-run uses a synthetic bootloader; --flash explicitly writes firmware.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from .transport import WireError
from .files import atomic_json, reserve_output

MODEL = "BCD996P2"
VERSION = "1.11.07"
IMAGE_SHA256 = "4b63481f3c53025e561fe412f6b5f977dd376545ab9fc32d5d5a4b47195534d9"
IMAGE_SIZE = 1130496
FOOTER_SIZE = 65536


@dataclass(frozen=True)
class Firmware:
    data: bytes
    sha256: str
    version: str
    checksum: int

    @property
    def payload(self):
        return self.data[:-FOOTER_SIZE]

    @classmethod
    def load(cls, path):
        if Path(path).stat().st_size != IMAGE_SIZE:
            raise ValueError("Image is not the pinned official BCD996P2 1.11.07 download")
        data = Path(path).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != IMAGE_SIZE or digest != IMAGE_SHA256:
            raise ValueError("Image is not the pinned official BCD996P2 1.11.07 download")

        def footer(offset):
            result = bytearray()
            for byte in data[-offset:]:
                byte ^= 0x55
                if not 32 <= byte <= 126:
                    break
                result.append(byte)
            return result.decode("ascii").strip()

        if footer(40) != MODEL or footer(22) != "Version " + VERSION:
            raise ValueError("Firmware footer model/version mismatch")
        return cls(data, digest, VERSION, int.from_bytes(data[-4:-2], "little"))

    def metadata(self):
        return {
            "model": MODEL,
            "version": self.version,
            "sha256": self.sha256,
            "file_bytes": len(self.data),
            "transmitted_payload_bytes": len(self.payload),
            "excluded_footer_bytes": FOOTER_SIZE,
            "expected_device_checksum": f"{self.checksum:04X}",
            "boot_region_writing": False,
            "license_operations": False,
        }


def handshake_size(response, payload_size):
    parts = response.split(b" ")
    if len(parts) != 2 or parts[0] != b"WWS" or not parts[1].isdigit():
        raise WireError(f"Unrecognized handshake-size reply: {response!r}")
    size = int(parts[1])
    if not 16 <= size <= 32768 or size & (size - 1) or payload_size % size:
        raise WireError(f"Unsafe/non-aligned handshake size: {size}")
    return size


def verify_checksum(response, expected):
    # Official CheckSum: split '=', trim whitespace and trailing H, hex ushort.
    parts = response.upper().split(b"=")
    if len(parts) != 2:
        raise WireError(f"Malformed device checksum: {response!r}")
    if parts[0].strip() not in {b"CHECKSUM", b"SUM"}:
        raise WireError(f"Malformed device checksum label: {response!r}")
    value = parts[1].strip()
    if value.endswith(b"H"):
        value = value[:-1]
    if not re.fullmatch(rb"[0-9A-F]{1,4}", value) or int(value, 16) != expected:
        raise WireError(f"Device checksum mismatch: {response!r}; expected {expected:04X}")


class Journal:
    def __init__(self, path, **metadata):
        self.path = Path(path)
        reserve_output(self.path)
        self.data = {
            "utc_started": datetime.now(timezone.utc).isoformat(),
            "events": [],
            **metadata,
        }
        self.set("created")

    def set(self, stage, **details):
        event = {
            "utc": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            **details,
        }
        self.data.update(event)
        self.data["events"].append(event)
        atomic_json(self.path, self.data)


class Updater:
    def __init__(
        self,
        image,
        factory,
        journal,
        *,
        sleep=time.sleep,
        progress=print,
        simulated=False,
        backup_version=None,
    ):
        if not simulated and (
            not isinstance(image, Firmware)
            or len(image.data) != IMAGE_SIZE
            or hashlib.sha256(image.data).hexdigest() != IMAGE_SHA256
            or image.sha256 != IMAGE_SHA256
            or image.version != VERSION
            or image.checksum != int.from_bytes(image.data[-4:-2], "little")
        ):
            raise ValueError("Live updates require the pinned official firmware")
        self.backup_version = backup_version
        self.image, self.factory, self.journal = image, factory, journal
        self.sleep, self.progress = sleep, progress
        self.erase_requested = False
        self.bytes_acknowledged = 0
        self.checksum_verified = False

    def identify(self, wire):
        wire.command(b"MDL", b"MDL,BCD996P2")
        response = wire.command(b"VER")
        match = re.fullmatch(rb"VER,Version (\d+\.\d+\.\d+)", response)
        if not match:
            raise WireError(f"Malformed firmware version: {response!r}")
        return match[1].decode("ascii")

    def run(self, *, recover=False):
        wire = None
        try:
            if not recover:
                wire = self.factory("normal")
                version = self.identify(wire)
                self.journal.set("normal_identity_verified", installed_version=version)
                if self.backup_version is not None and version != self.backup_version:
                    raise WireError(
                        "Backup firmware version differs from the connected scanner; export again"
                    )
                if tuple(map(int, version.split("."))) >= tuple(map(int, VERSION.split("."))):
                    raise WireError(
                        "Scanner is already at or above target version; no write performed"
                    )
                wire.command(b"EPG", b"EPG,OK")
                wire.command(b"PRG", b"PRG,OK")
                # Exact official mode transition. No general service-mode API.
                wire.command(b"MMM,2468", b"MMM,OK")
                wire.command(b"FWM,Uniden", b"FWM,OK")
                self.journal.set("bootloader_entry_requested")
                wire.close()
                wire = None
                self.progress("Waiting for scanner firmware-update mode...")
                self.sleep(10)  # official BCD996P2 TimeoutReboot
            wire = self.factory("bootloader")
            wire.pending()  # startup traffic is recorded; no transfer data exists yet
            wire.command(b"", b"UNKNOWN COMMAND")
            wire.pending()
            wire.command(b"*MDL", b"BCD996P2")
            self.journal.set("bootloader_identity_verified")
            wire.command(b"*SPD 5")  # official baud selector 5, not a baud literal
            self.sleep(0.5)
            wire.transport.baudrate = 115200
            self.sleep(0.5)
            wire.command(b"*SCB 1", b"SCB 1")
            size = handshake_size(wire.command(b"*WWS N"), len(self.image.payload))
            self.journal.set("ready_to_erase", handshake_bytes=size, **self.image.metadata())
            if wire.pending():
                raise WireError("Unexpected pending bytes before erase")
            self.progress(
                f"Writing official {MODEL} {VERSION}; keep scanner power and USB connected."
            )
            # Set before sending: a partial write could already trigger erase.
            self.erase_requested = True
            self.journal.set("erase_requested")
            response = wire.command(b"*ULE", b"OK", timeout=10)
            self.journal.set(
                "erase_reply_received",
                erase_reply=response.decode("ascii", errors="backslashreplace"),
            )
            wire.command(b"*BIN N", b"OK")  # do not write the boot region
            wire.command(b"*PRG", b"OK")
            self.journal.set("transferring", bytes_acknowledged=0)
            last_percent = -1
            for offset in range(0, len(self.image.payload), size):
                if wire.pending():
                    raise WireError("Unexpected traffic before firmware packet")
                chunk = self.image.payload[offset : offset + size]
                if len(chunk) != size:
                    raise WireError("Partial final packet is not supported")
                wire.send(chunk.hex().upper().encode("ascii"))
                response = wire.receive(timeout=3)
                if response != b"ACK":
                    raise WireError(f"Firmware packet not acknowledged at {offset}: {response!r}")
                self.bytes_acknowledged = offset + size
                percent = self.bytes_acknowledged * 100 // len(self.image.payload)
                if percent // 5 != last_percent // 5:
                    last_percent = percent
                    self.journal.set(
                        "transferring",
                        bytes_acknowledged=self.bytes_acknowledged,
                        percent=percent,
                    )
                    self.progress(
                        f"Firmware transfer: {percent}% ({self.bytes_acknowledged:,} bytes acknowledged)"
                    )
            response = wire.receive(timeout=5)
            if response != b"PROGRAM END":
                raise WireError(f"Expected PROGRAM END, got {response!r}")
            verify_checksum(wire.receive(timeout=2), self.image.checksum)
            self.checksum_verified = True
            self.journal.set(
                "device_checksum_verified",
                bytes_acknowledged=self.bytes_acknowledged,
                checksum=f"{self.image.checksum:04X}",
            )
            try:
                wire.command(b"*OFF")
            except (WireError, OSError) as exc:
                # Some USB implementations disconnect immediately on reboot.
                # Only a successful normal-mode version query can resolve this.
                self.journal.set("reboot_ack_missing", error=str(exc))
            wire.close()
            wire = None
            self.journal.set("waiting_for_normal_mode")
            self.sleep(10)
            wire = self.factory("normal_after_update")
            versions = [self.identify(wire) for _ in range(3)]
            if versions != [VERSION] * 3:
                raise WireError(f"Post-update firmware version mismatch: {versions!r}")
            self.journal.set(
                "complete",
                verified_versions=versions,
                bytes_acknowledged=self.bytes_acknowledged,
            )
            self.progress(
                f"Verified {MODEL} firmware {VERSION} in three consecutive post-update queries."
            )
            return self.journal.data
        except BaseException as exc:
            stage = "recovery_required" if self.erase_requested else "stopped_before_erase"
            if self.checksum_verified:
                stage = "firmware_checksum_verified_postcheck_incomplete"
            self.journal.set(
                stage,
                error=f"{type(exc).__name__}: {exc}",
                bytes_acknowledged=self.bytes_acknowledged,
                erase_requested=self.erase_requested,
                device_checksum_verified=self.checksum_verified,
            )
            # Never reset, erase again, or resend ambiguous packets automatically.
            raise
        finally:
            if wire:
                wire.close()


def verified_backup(path):
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    records = data.get("records")
    if (
        type(data.get("schema")) is not int
        or data.get("schema") != 1
        or data.get("model") != MODEL
        or data.get("complete") is not True
        or data.get("program_mode_exited") is not True
        or not isinstance(records, list)
        or not records
        or any(not isinstance(r, dict) or not isinstance(r.get("request"), str) for r in records)
        or not any(r.get("request") == "MDL" and r.get("fields") == ["MDL", MODEL] for r in records)
        or not any(
            r.get("request") == "VER"
            and r.get("fields") == ["VER", "Version " + str(data.get("firmware"))]
            for r in records
        )
        or not re.fullmatch(r"\d+\.\d+\.\d+", str(data.get("firmware")))
    ):
        raise ValueError(
            "A completed BCD996P2 readable-settings export is required before flashing"
        )
    _check_backup_records(data)
    return {
        "path": str(Path(path).resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "firmware": data.get("firmware"),
        "warnings": data.get("warnings", []),
    }


def _check_backup_records(data):
    """Check archive consistency; this does not authenticate scanner identity."""
    from .backup import permitted_getter

    indexed = {}
    for record in data["records"]:
        request = record["request"]
        encoded = record.get("raw_hex", "")
        fields = record.get("fields")
        if (
            not permitted_getter(request)
            or not isinstance(encoded, str)
            or not re.fullmatch(r"(?:[0-9a-fA-F]{2})+", encoded)
            or not isinstance(fields, list)
            or not all(isinstance(x, str) for x in fields)
        ):
            raise ValueError("Malformed readable-settings record")
        raw = bytes.fromhex(encoded)
        if (
            not raw.endswith(b"\r")
            or b"\r" in raw[:-1]
            or b"\n" in raw
            or raw[:-1].decode("ascii", errors="backslashreplace").split(",") != fields
            or fields[0] != request.split(",")[0]
        ):
            raise ValueError("Settings record bytes and parsed fields disagree")
        if request.startswith("SIN,"):
            index = int(request.split(",")[1])
            if index in indexed or len(fields) < 28 or fields[27] != "0":
                raise ValueError("Duplicate, protected or truncated system record")
            indexed[index] = fields

    def scalar(command):
        records = [r["fields"] for r in data["records"] if r["request"] == command]
        if len(records) != 1 or len(records[0]) != 2:
            raise ValueError(f"Missing or ambiguous {command} evidence")
        try:
            return int(records[0][1])
        except ValueError as exc:
            raise ValueError(f"Invalid {command} evidence") from exc

    count = scalar("SCT")
    head = scalar("SIH")
    tail = scalar("SIT")
    if (
        type(data.get("system_count")) is not int
        or not 0 <= count <= 500
        or count != data["system_count"]
        or len(indexed) != count
    ):
        raise ValueError("Settings system count disagrees with records")
    visited = set()
    last = -1
    while head != -1:
        if head in visited or head not in indexed:
            raise ValueError("Invalid settings system chain")
        visited.add(head)
        last = head
        try:
            head = int(indexed[head][13])
        except ValueError as exc:
            raise ValueError("Invalid settings forward index") from exc
    if len(visited) != count or tail != last:
        raise ValueError("Incomplete settings system chain")
