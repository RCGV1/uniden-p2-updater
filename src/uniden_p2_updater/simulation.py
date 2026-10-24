# SPDX-License-Identifier: GPL-3.0-only
"""Explicitly synthetic target and input; no serial interface or vendor bytes."""

from dataclasses import dataclass
import hashlib
import time
from .updater import MODEL, VERSION, FOOTER_SIZE


@dataclass(frozen=True)
class SyntheticImage:
    """Deterministic invented bytes for simulation only; never a firmware input."""

    data: bytes
    sha256: str
    version: str = VERSION
    checksum: int = 0x1234

    @classmethod
    def create(cls):
        data = bytes(range(256)) * (0x114000 // 256)
        return cls(data, hashlib.sha256(data).hexdigest())

    @property
    def payload(self):
        return self.data[:-FOOTER_SIZE]

    def metadata(self):
        return {
            "model": MODEL,
            "version": self.version,
            "sha256": self.sha256,
            "file_bytes": len(self.data),
            "transmitted_payload_bytes": len(self.payload),
            "expected_device_checksum": f"{self.checksum:04X}",
            "simulated_input": True,
            "boot_region_writing": False,
            "license_operations": False,
        }


class SimulatedBootloader:
    """Independent stateful synthetic target; opens no hardware."""

    def __init__(self, image, *, size=1024, fault=None):
        self.image, self.size, self.fault = image, size, fault
        self.mode = "normal"
        self.pending = bytearray()
        self.received = bytearray()
        self.commands = []
        self.baudrate = 115200
        self.closed = False
        self.erase_count = 0

    @property
    def in_waiting(self):
        return len(self.pending)

    def write(self, raw):
        assert raw.endswith(b"\r") and b"\r" not in raw[:-1]
        packet = raw[:-1]
        self.commands.append(packet)
        if self.mode == "writing":
            chunk = bytes.fromhex(packet.decode("ascii"))
            assert len(chunk) == self.size
            expected = self.image.payload[len(self.received) : len(self.received) + self.size]
            assert chunk == expected, "Packet differs from pinned image"
            self.received.extend(chunk)
            if self.fault == "missing_ack":
                return len(raw)
            self.pending.extend(b"NAK\r" if self.fault == "nak" else b"ACK\r")
            if len(self.received) == len(self.image.payload):
                self.pending.extend(b"PROGRAM END\r")
                value = self.image.checksum ^ (1 if self.fault == "checksum" else 0)
                self.pending.extend(f"SUM = {value:04X}H\r".encode())
                self.mode = "programmed"
            return len(raw)
        responses = {
            b"MDL": b"MDL,BCD996P2",
            b"VER": b"VER,Version 1.06.00",
            b"EPG": b"EPG,OK",
            b"PRG": b"PRG,OK",
            b"MMM,2468": b"MMM,OK",
            b"FWM,Uniden": b"FWM,OK",
            b"": b"UNKNOWN COMMAND",
            b"*MDL": b"BCD996P2",
            b"*SPD 5": b"SPD 5",
            b"*SCB 1": b"SCB 1",
            b"*WWS N": f"WWS {self.size}".encode(),
            b"*ULE": b"OK",
            b"*BIN N": b"OK",
            b"*PRG": b"OK",
            b"*OFF": b"OK",
        }
        if packet == b"*MDL" and self.fault == "wrong_model":
            response = b"BCD325P2"
        elif packet == b"VER" and self.mode == "updated":
            response = b"VER,Version 1.11.07"
        else:
            response = responses.get(packet, b"ERR")
        if packet == b"FWM,Uniden":
            self.mode = "bootloader"
        if packet == b"*ULE":
            self.erase_count += 1
        if packet == b"*PRG":
            self.mode = "writing"
        if packet == b"*OFF":
            self.mode = "updated" if len(self.received) == len(self.image.payload) else "normal"
        self.pending.extend(response + b"\r")
        return len(raw)

    def read(self, size=1):
        result = bytes(self.pending[:size])
        del self.pending[:size]
        if not result:
            time.sleep(0.001)
        return result

    def close(self):
        self.closed = True
