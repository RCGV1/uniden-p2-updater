# SPDX-License-Identifier: GPL-3.0-only
"""Audit allowlisted source and built artifacts without opening hardware."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    "README.md",
    "LICENSE",
    "COPYRIGHT",
    "THIRD_PARTY_NOTICES.md",
    "CHANGELOG.md",
    "pyproject.toml",
    "MANIFEST.in",
    ".gitignore",
}
GENERATED = {"build", "dist", "__pycache__", ".ruff_cache", ".venv", ".git", "logs"}
SENSITIVE = re.compile(
    rb"/Us[e]rs/|Documents[/]Codex|(?<![0-9])37[89][0-9]{11}(?![0-9])|"
    rb"Authorizatio[n]\s*:\s*(?:Basic|Bearer)"
)


def allowed_source(name):
    path = PurePosixPath(name)
    if name in ROOT_FILES or name == ".github/workflows/ci.yml":
        return True
    if len(path.parts) == 2 and path.parts[0] == "docs" and path.suffix == ".md":
        return True
    if len(path.parts) == 2 and path.parts[0] in {"tests", "tools"} and path.suffix == ".py":
        return True
    return (
        len(path.parts) == 3
        and path.parts[:2] == ("src", "uniden_p2_updater")
        and path.suffix == ".py"
    )


def check_text(name, data):
    if b"\0" in data or SENSITIVE.search(data):
        raise ValueError(f"Binary or private content in {name}")
    data.decode("utf-8")


def source_files(root=ROOT):
    selected = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in GENERATED or part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Symlinks are excluded: {relative}")
        if not path.is_file():
            continue
        name = relative.as_posix()
        if not allowed_source(name):
            raise ValueError(f"Unexpected source file: {name}")
        check_text(name, path.read_bytes())
        selected.append(path)
    for name in ROOT_FILES:
        if not (root / name).is_file():
            raise ValueError(f"Required source file missing: {name}")
    if 'license = "GPL-3.0-only"' not in (root / "pyproject.toml").read_text(encoding="utf-8"):
        raise ValueError("Expected GPLv3 metadata")
    return selected


def allowed_built(name, wheel=False):
    parts = PurePosixPath(name).parts
    if not parts or ".." in parts or name.startswith("/"):
        return False
    if wheel:
        return (len(parts) == 2 and parts[0] == "uniden_p2_updater" and name.endswith(".py")) or (
            parts[0].endswith(".dist-info") and len(parts) <= 3
        )
    if len(parts) < 2:
        return False
    relative = PurePosixPath(*parts[1:]).as_posix()
    return (
        allowed_source(relative)
        or relative == "PKG-INFO"
        or relative == "setup.cfg"
        or (
            len(parts) == 4
            and parts[1] == "src"
            and parts[2] == "uniden_p2_updater.egg-info"
            and parts[3]
            in {
                "PKG-INFO",
                "SOURCES.txt",
                "dependency_links.txt",
                "entry_points.txt",
                "requires.txt",
                "top_level.txt",
            }
        )
    )


def audit_artifacts(directory):
    results = []
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            raise ValueError(f"Unexpected artifact directory: {path.name}")
        entries = []
        if path.suffix == ".whl":
            with zipfile.ZipFile(path) as archive:
                entries = [(n, archive.read(n)) for n in archive.namelist() if not n.endswith("/")]
            wheel = True
        elif path.name.endswith(".tar.gz"):
            with tarfile.open(path, "r:gz") as archive:
                for member in archive.getmembers():
                    if member.isdir():
                        continue
                    if not member.isfile():
                        raise ValueError("Non-regular distribution member")
                    entries.append((member.name, archive.extractfile(member).read()))
            wheel = False
        else:
            raise ValueError(f"Unexpected distribution file: {path.name}")
        for name, data in entries:
            if not allowed_built(name, wheel=wheel):
                raise ValueError(f"Unexpected distribution member: {name}")
            check_text(name, data)
        if not any(n.endswith("/LICENSE") for n, _ in entries):
            raise ValueError("License absent from distribution")
        results.append(
            {
                "file": path.name,
                "members": len(entries),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    if not results:
        raise ValueError("No distributions found")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    paths = source_files()
    result = {
        "source_files": len(paths),
        "source_audit": "passed",
        "firmware_or_hardware_needed": False,
    }
    if args.artifacts:
        result["artifacts"] = audit_artifacts(args.artifacts)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
