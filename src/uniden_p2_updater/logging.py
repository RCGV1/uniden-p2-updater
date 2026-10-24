# SPDX-License-Identifier: GPL-3.0-only
"""Exclusive JSONL logs containing exact bytes and explicit simulation labels."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from .files import reserve_output


class CommunicationLogger:
    def __init__(self, path, *, simulated=False):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.simulated = simulated
        reserve_output(self.path)
        self._closed = False

    def event(self, event, data=b"", **metadata):
        record = {
            "utc": datetime.now(timezone.utc).isoformat(),
            "monotonic_ns": time.monotonic_ns(),
            "simulated": self.simulated,
            "event": event,
            "hex": data.hex(),
            "ascii_escaped": data.decode("ascii", errors="backslashreplace"),
            **metadata,
        }
        if self._closed:
            raise ValueError("Communication log is closed")
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")

    def close(self):
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
