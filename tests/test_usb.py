# SPDX-License-Identifier: GPL-3.0-only
from types import SimpleNamespace
import unittest
from uniden_p2_updater.usb import USBAnchor, usb_factory
from uniden_p2_updater.transport import WireError


def device(**changes):
    values = dict(
        device="SIMULATED",
        vid=0x1965,
        pid=0x001A,
        location="SYNTHETIC-USB",
        serial_number=None,
    )
    values.update(changes)
    return SimpleNamespace(**values)


class USBTests(unittest.TestCase):
    def test_missing_location_wrong_model_and_ambiguous_device_rejected(self):
        for devices in (
            [device(location=None)],
            [device(location="")],
            [device(vid=1)],
            [device(pid=1)],
            [],
            [device(), device()],
        ):
            with self.subTest(devices=devices), self.assertRaises(ValueError):
                USBAnchor.select("SIMULATED", devices)

    def test_anchor_rejects_other_location_or_changed_serial(self):
        anchor = USBAnchor.select("SIMULATED", [device(serial_number="SYNTHETIC-ID")])
        self.assertFalse(
            anchor.matches(device(location="DIFFERENT", serial_number="SYNTHETIC-ID"), "bootloader")
        )
        self.assertFalse(anchor.matches(device(serial_number="CHANGED"), "bootloader"))
        self.assertFalse(anchor.matches(device(pid=2, serial_number="SYNTHETIC-ID"), "normal"))
        self.assertTrue(anchor.matches(device(pid=2, serial_number="SYNTHETIC-ID"), "bootloader"))

    def test_factory_does_not_fall_back_to_other_location(self):
        snapshots = iter([[device()], [device(location="CHANGED")]])
        clock = iter([0, 21])
        factory = usb_factory(
            "SIMULATED",
            None,
            enumerate_ports=lambda: next(snapshots),
            wire_type=lambda *a, **kw: self.fail("Never open replacement"),
            clock=lambda: next(clock),
            sleep=lambda _: None,
        )
        with self.assertRaises(WireError):
            factory("bootloader")

    def test_factory_reopens_renamed_port_at_original_location_with_boot_flow(self):
        snapshots = iter([[device()], [device(device="RENAMED")]])
        calls = []
        factory = usb_factory(
            "SIMULATED",
            None,
            enumerate_ports=lambda: next(snapshots),
            wire_type=lambda *a, **kw: calls.append((a, kw)),
        )
        factory("bootloader")
        self.assertEqual(calls[0][0][0], "RENAMED")
        self.assertTrue(calls[0][1]["flow"])
