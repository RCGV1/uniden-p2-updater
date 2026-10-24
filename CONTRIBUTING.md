# Contributing

This is an early prototype. We are looking for testers and contributors to expand firmware support and improve the flashing documentation. Help is welcome with documentation review, offline tests, packaging, and establishing support on additional operating systems. Start with the [validation limits](docs/validation.md) and [protocol notes](docs/protocol.md).

## Useful contributions

- Improve clarity and accuracy of the flashing and recovery documentation.
- Add offline tests using invented firmware bytes and simulated transports.
- Review catalog and version-gate behavior without including firmware files.
- Report operating-system and Python-version results for tests and packaging.
- For hardware evidence, provide a concise, redacted summary of the model, firmware versions, operating system, connection path, and observed outcomes. Coordinate before any live update; do not experiment with unsupported models, hardware revisions, arbitrary images, or downgrade targets.

Only BCD996P2 devices with a 378Z serial prefix are in the current live-flash scope. The update from 1.06.00 to 1.11.07 has been demonstrated on one such scanner, but the standalone v0.2 release has not been flashed. Other pinned firmware targets require the explicit `--allow-untested-target` option and have no project hardware validation yet. Linux/Windows hardware, other units, rear serial transport, and interrupted-update recovery remain unverified. Normal updates verify an older installed version; recovery relies on the archive’s older pre-update version. Do not treat simulator results as hardware evidence.

## What not to submit

Do not add vendor firmware binaries, vendor updater binaries, full wire logs, configuration exports, serial numbers, activation keys, registration material, or other private device data to issues, pull requests, or public chat. Full wire logs can contain the transmitted firmware image; settings exports and logs can expose configuration. Share only the minimum redacted information needed to describe a finding.

Do not use vendor firmware or activation material as test fixtures. Tests should use invented bytes and simulated devices. The project does not seek activation keys, entitlement data, or methods for bypassing license checks.

## Development checks

From the project directory:

```sh
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
python tools/audit_release.py
```

Please describe the user-visible behavior changed and list the checks you ran. Keep pull requests focused and omit private research notes or abandoned approaches.
