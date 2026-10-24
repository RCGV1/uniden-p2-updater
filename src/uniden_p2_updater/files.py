# SPDX-License-Identifier: GPL-3.0-only
"""Exclusive output creation and atomic checkpoints."""

import json
import os
from pathlib import Path
import tempfile


def distinct_paths(*paths):
    """Reject canonical, symlink and hard-link aliases before opening outputs."""
    selected = [Path(p) for p in paths if p is not None]
    for index, path in enumerate(selected):
        for other in selected[:index]:
            if path.resolve() == other.resolve() or (
                path.exists() and other.exists() and path.samefile(other)
            ):
                raise ValueError(f"Input/output paths must be distinct: {path} and {other}")


def reserve_output(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Windows may follow dangling symlinks even with O_EXCL. Reject existing
    # directory entries explicitly, including links with missing targets.
    try:
        path.lstat()
    except FileNotFoundError:
        pass
    else:
        raise FileExistsError(f"Output already exists: {path}")
    # O_EXCL prevents replacing a file created after the entry check.
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)


def atomic_json(path, data):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
