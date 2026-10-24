# SPDX-License-Identifier: GPL-3.0-only
"""Bounded CR-framed I/O shared by configuration export and firmware update.

This module has no standalone command interface. Callers impose their own policy.
Every transmitted packet and every complete/partial reply is logged verbatim.
"""

import time
import serial


class WireError(Exception):
    pass


class Wire:
    def __init__(self, port, logger, *, transport=None, flow=False):
        self.port, self.logger = port, logger
        self.transport = transport
        if self.transport is None:
            options = dict(
                port=None,
                baudrate=115200,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=0.05,
                write_timeout=5,
                xonxoff=flow,
                rtscts=False,
                dsrdtr=False,
            )
            if __import__("os").name != "nt":
                options["exclusive"] = True
            self.transport = serial.Serial(**options)
            try:
                self.transport.dtr = False
                self.transport.rts = False
                self.transport.port = port
                self.transport.open()
            except BaseException:
                self.transport.close()
                raise
        try:
            self.logger.event("wire_open", port=port, baudrate=115200, xonxoff=flow)
        except BaseException:
            self.transport.close()
            raise

    def send(self, packet):
        if not isinstance(packet, bytes) or b"\r" in packet or b"\n" in packet:
            raise ValueError("Supply one packet without terminators")
        raw = packet + b"\r"
        self.logger.event("tx_attempt", raw, port=self.port)
        written = self.transport.write(raw)
        self.logger.event("tx", raw[:written], port=self.port, requested_bytes=len(raw))
        if written != len(raw):
            raise WireError(f"Short write: {written}/{len(raw)}")

    def receive(self, timeout=3):
        deadline = time.monotonic() + timeout
        raw = bytearray()
        while time.monotonic() < deadline:
            byte = self.transport.read(1)
            if byte:
                raw.extend(byte)
                if len(raw) > 131072:
                    self.logger.event("rx_oversized", bytes(raw), port=self.port)
                    raise WireError("Packet exceeds bounded size")
                if byte == b"\r":
                    self.logger.event("rx", bytes(raw), port=self.port)
                    return bytes(raw[:-1])
        self.logger.event("rx_timeout", bytes(raw), port=self.port)
        raise WireError(f"Response timeout after {timeout}s; partial bytes={len(raw)}")

    def command(self, packet, expected=None, timeout=3):
        self.send(packet)
        response = self.receive(timeout)
        if expected is not None and response != expected:
            raise WireError(f"Unexpected reply to {packet!r}: {response!r}; expected {expected!r}")
        if expected is not None:
            return response
        if response.upper() in {b"ERR", b"NG", b"ERROR", b"UNKNOWN COMMAND", b"NAK"}:
            raise WireError(f"Scanner rejected {packet!r}: {response!r}")
        return response

    def pending(self):
        count = self.transport.in_waiting
        if not count:
            return b""
        raw = self.transport.read(count)
        self.logger.event("rx_pending", raw, port=self.port)
        return raw

    def close(self):
        self.transport.close()
        self.logger.event("wire_close", port=self.port)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
