# Validation and support limits

## Physical evidence

The reconstructed sequence completed one update on a 378Z BCD996P2 through front USB on Apple Silicon macOS, from 1.06.00 to official 1.11.07. The target negotiated 16,384-byte windows; 65 packets totaling 1,064,960 bytes each received ACK. The scanner reported `PROGRAM END`, then `CHECKSUM= 2D82H`, and subsequently returned the expected model/version repeatedly.

The transmitted bytes matched the original official input with its final 65,536 bytes excluded. Before/after readable-settings exports contained 11 systems, 27 groups and 234 channels; all comparable replies matched except firmware version. These are aggregate observations, not proof that every raw memory/calibration region was preserved.

The distributed standalone code has additional guards and packaging changes validated offline. No further hardware flash was performed. The exact revised release, Linux/Windows hardware, 378A hardware, other units/cables, rear serial transport and interrupted physical recovery are unverified. Firmware mode exposes more than the public normal remote-command interface; the utility implements only the pinned update sequence.

## Offline release checks

The 40 synthetic tests pass from the source tree and from the installed wheel on Apple Silicon macOS using Python 3.11 and 3.14. Console-entry inspection and synthetic transfer smoke checks pass. Wheel and source-distribution contents pass the allowlist/private-content audit. Remote GitHub CI has not run; Linux/Windows hardware remains unverified.

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
