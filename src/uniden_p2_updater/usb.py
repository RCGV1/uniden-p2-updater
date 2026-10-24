# SPDX-License-Identifier: GPL-3.0-only
"""Reconnection anchored to the explicitly selected physical USB location."""

from dataclasses import dataclass
import time
from serial.tools import list_ports
from .transport import Wire, WireError


@dataclass(frozen=True)
class USBAnchor:
    location: str
    serial_number: str | None

    @classmethod
    def select(cls, port, devices):
        matches = [p for p in devices if p.device == port]
        if len(matches) != 1 or (matches[0].vid, matches[0].pid) != (0x1965, 0x001A):
            raise ValueError("Select the enumerated BCD996P2 front USB interface (1965:001A)")
        device = matches[0]
        if not device.location or not device.location.strip():
            raise ValueError("USB location is unavailable; no mode change or update can start")
        return cls(device.location, device.serial_number or None)

    def matches(self, device, phase):
        return (
            device.vid == 0x1965
            and device.location == self.location
            and (self.serial_number is None or device.serial_number == self.serial_number)
            and (phase == "bootloader" or device.pid == 0x001A)
        )


def usb_factory(
    port,
    logger,
    *,
    enumerate_ports=None,
    wire_type=Wire,
    clock=time.monotonic,
    sleep=time.sleep,
):
    enumerate_ports = enumerate_ports or list_ports.comports
    anchor = USBAnchor.select(port, enumerate_ports())

    def factory(phase):
        deadline = clock() + 20
        while True:
            candidates = [p for p in enumerate_ports() if anchor.matches(p, phase)]
            if len(candidates) > 1:
                raise WireError("Multiple interfaces match the original physical USB anchor")
            if len(candidates) == 1:
                try:
                    return wire_type(candidates[0].device, logger, flow=phase == "bootloader")
                except OSError:
                    if clock() >= deadline:
                        raise
            if clock() >= deadline:
                raise WireError("Scanner did not re-enumerate at the original USB anchor")
            sleep(0.25)

    return factory
