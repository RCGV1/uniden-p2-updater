# SPDX-License-Identifier: GPL-3.0-only
"""Immutable exact-image catalog. Hashes identify files, not hardware validation."""

from dataclasses import dataclass
from types import MappingProxyType

MODEL = "BCD996P2"
LATEST_VERSION = "1.11.07"
IMAGE_SIZE = 1130496
FOOTER_SIZE = 65536


@dataclass(frozen=True)
class FirmwarePin:
    version: str
    sha256: str
    checksum: int
    physical_transfer_validated: bool = False

    def metadata(self):
        return {
            "model": MODEL,
            "version": self.version,
            "filename": f"{MODEL}_V{self.version.replace('.', '_')}.bin",
            "sha256": self.sha256,
            "file_bytes": IMAGE_SIZE,
            "expected_device_checksum": f"{self.checksum:04X}",
            "physical_transfer_validated": self.physical_transfer_validated,
            "untested_live_opt_in_required": not self.physical_transfer_validated,
            "hardware_prefixes": ["378Z"],
        }


FIRMWARE_PINS = (
    FirmwarePin(
        "1.10.02", "2d345f67d476d3e492f37cfb29551082eb36e7d3a8c8cb8d7e1ae8fbb9bd080c", 0x27AB
    ),
    FirmwarePin(
        "1.11.03", "b12f239ad90acdcd81cffa35959486f1d53ee83a8af9fdc49862e3db827336ae", 0x73F9
    ),
    FirmwarePin(
        "1.11.04", "39c30f318cacec575be964625d5fcb92727b0b6c414fd94f39b6e5eae2f49257", 0x7F73
    ),
    FirmwarePin(
        "1.11.06", "14bf6d1d0755974b1343020ceae81685fd8a23913eb128aae05fcbf13ac2bf0c", 0x38DB
    ),
    FirmwarePin(
        "1.11.07", "4b63481f3c53025e561fe412f6b5f977dd376545ab9fc32d5d5a4b47195534d9", 0x2D82, True
    ),
)
PINS_BY_HASH = MappingProxyType({pin.sha256: pin for pin in FIRMWARE_PINS})
PINS_BY_VERSION = MappingProxyType({pin.version: pin for pin in FIRMWARE_PINS})


def firmware_catalog():
    return {
        "model": MODEL,
        "recommended_version": LATEST_VERSION,
        "images": [pin.metadata() for pin in FIRMWARE_PINS],
        "other_models_supported": False,
    }
