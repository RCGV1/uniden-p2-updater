# SPDX-License-Identifier: GPL-3.0-only
"""Transport failures use explicit in-memory fixtures, never a serial port."""

import unittest
from uniden_p2_updater.transport import Wire, WireError


class Target:
    def __init__(self, response=b"", short=False):
        self.response = bytearray(response)
        self.short = short
        self.closed = False
        self.writes = []

    def read(self, n):
        result = bytes(self.response[:n])
        del self.response[:n]
        return result

    def write(self, value):
        self.writes.append(value)
        return len(value) - (1 if self.short else 0)

    def close(self):
        self.closed = True


class Log:
    def event(self, *args, **kwargs):
        pass


class TransportTests(unittest.TestCase):
    def test_framing_and_short_write(self):
        target = Target(b"OK\r")
        with Wire("SIMULATED", Log(), transport=target) as wire:
            self.assertEqual(wire.command(b"TEST", b"OK"), b"OK")
            for packet in (b"BAD\rNEXT", b"BAD\n", "text"):
                with self.assertRaises(ValueError):
                    wire.send(packet)
        self.assertEqual(target.writes, [b"TEST\r"])
        self.assertTrue(target.closed)
        target = Target(short=True)
        with Wire("SIMULATED", Log(), transport=target) as wire:
            with self.assertRaises(WireError):
                wire.send(b"TEST")
        self.assertEqual(len(target.writes), 1)

    def test_partial_reply_is_not_accepted(self):
        with Wire("SIMULATED", Log(), transport=Target(b"ACK")) as wire:
            with self.assertRaises(WireError):
                wire.receive(timeout=0.001)

    def test_opened_transport_closed_if_open_event_logging_fails(self):
        class BadLog:
            def event(self, *a, **kw):
                raise OSError("invented log failure")

        target = Target()
        with self.assertRaises(OSError):
            Wire("SIMULATED", BadLog(), transport=target)
        self.assertTrue(target.closed)
