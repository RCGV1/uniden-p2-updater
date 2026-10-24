# Validation and support limits

## Prototype and physical evidence

This project is an early prototype seeking documentation reviewers, offline-test contributors, and people able to help establish additional platform support. The exact v0.2 standalone release has not been flashed. The only physical transfer evidence is from the preceding implementation on one BCD996P2 with a 378Z serial prefix, using front USB on Apple Silicon macOS.

The reconstructed sequence completed one update on a 378Z BCD996P2 through front USB on Apple Silicon macOS, from 1.06.00 to official 1.11.07. The target negotiated 16,384-byte windows; 65 packets totaling 1,064,960 bytes each received ACK. The scanner reported `PROGRAM END`, then `CHECKSUM= 2D82H`, and subsequently returned the expected model/version repeatedly.

The transmitted bytes matched the original official input with its final 65,536 bytes excluded. Before/after readable-settings exports contained 11 systems, 27 groups and 234 channels; all comparable replies matched except firmware version. These are aggregate observations, not proof that every raw memory/calibration region was preserved.

The catalog accepts exact official BCD996P2 images for versions 1.10.02, 1.11.03, 1.11.04, 1.11.06, and 1.11.07. Only 1.11.07 has physical transfer evidence, and that evidence predates the standalone v0.2 release. The other four targets require the explicit `--allow-untested-target` flag for live flashing. That flag does not add hardware evidence; it records the operator's choice to use a cataloged but unvalidated target. Normal-mode updates require an older reported installed version. Recovery requires an older archive version but cannot verify the currently installed version in the loader. All live updates require BCD996P2 identity and a 378Z hardware label prefix.

No further hardware flash was performed. The exact revised release, Linux/Windows hardware, 378A hardware, other units/cables, rear serial transport and interrupted physical recovery are unverified. Firmware mode exposes more than the public normal remote-command interface; the utility implements only the pinned update sequence.

## Offline release checks

The test suite uses synthetic data and explicit transports; it checks catalog membership and immutability, offline catalog listing, the untested-target opt-in boundary, target-version handling, protocol faults, settings export and file safety. Local test counts can change as the prototype develops. Console-entry inspection and synthetic transfer smoke checks pass. Wheel and source-distribution contents pass the allowlist/private-content audit. GitHub CI runs offline tests and packaging on macOS, Linux and Windows; its results do not establish hardware support. Linux/Windows hardware remains unverified.

## Independent test inputs

`SyntheticImage` produces a repeating sequence of byte values, labeled as invented. It is never written to a vendor-format fixture file or accepted by production image validation. Synthetic checksum `1234` exists only to exercise message handling. Test doubles deliberately supply responses and faults; their output is not a scanner measurement.

Tests check full payload/order, exact command sequence, wrong identity, bad window, erase-reply mismatch, NAK, lost ACK, checksum mismatch, interrupts, backup-version mismatch, frame injection, partial replies, path aliases, checkpoint rollback, incomplete export and USB-anchor behavior. The full simulated payload keeps the real transfer dimensions while using no vendor bytes.

The settings validator checks schema, strict completion flags, response bytes/fields, model/version evidence, system count and system-chain consistency. It does not authenticate a user-editable archive, prove scanner identity, or provide restoration. Neither the exporter nor test fixtures claim raw memory access.

## Optional original-image checks

With a separately acquired original image, offline inspection checks its exact length/SHA-256 and footer identity/version. It performs no device discovery:

```sh
uniden-p2-update --inspect --firmware /path/to/BCD996P2_V1_11_07.bin
```

The unit suite deliberately has no external firmware prerequisite. It verifies rejection of invented/modified inputs without patching production hash constants. Complete positive validation of the real pinned input was performed locally; that input is excluded from distributions.

Contributors should prioritize offline tests and documentation review. See [CONTRIBUTING.md](../CONTRIBUTING.md) for evidence handling and hardware-validation boundaries.
