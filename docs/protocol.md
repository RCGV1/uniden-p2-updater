# Supported transfer behavior

The client identifies normal-mode model/version, refuses a current/newer version, checks the recorded backup version, and follows the model-specific normal-to-loader transition. It reconnects at the original physical USB anchor with no hardware RTS/CTS or modem flow control. Boot transport enables XON/XOFF, uses baud selector 5, and negotiates the window with `WWS`.

The expected `WWS` prefix and a bounded power-of-two/aligned size are mandatory before erase. The live-tested erase acknowledgement is exactly `OK`. After requesting erase the journal records that intent conservatively, including when a command might only have been partially transmitted. Binary mode uses the boot-writing-disabled option. Each window is transmitted as uppercase hexadecimal plus CR and needs exactly one ACK. No automatic packet retry is implemented.

For the pinned file, only the first 1,064,960 bytes are sent. The final 65,536 bytes supply host-side metadata and are excluded. The final 16-bit expected checksum is read from the original distribution footer; matching that value does not establish cryptographic authenticity. Whole-file SHA-256 pinning is an independent local input restriction. The updater transports the original encoded payload and implements no package decoder.

After `PROGRAM END` and a matching device checksum, the client requests reboot and verifies normal-mode identity/version three times. A missing immediate reboot acknowledgement can be resolved only by those normal-mode checks. A failure after checksum verification is recorded separately from a failed transfer.

## Failure and recovery

Before erase, a failure stops the sequence and closes the host transport. After an erase request, the journal marks `recovery_required` unless the final checksum was verified, in which case it records that the postcheck is incomplete. The client sends no automatic second erase, ambiguous packet retransmission or reboot after a transfer failure.

`--recover` is an explicit modifier for `--flash`. It skips the normal-mode service transition, requires the same pinned file, supported physical prefix and a completed archive, verifies the loader identity, and starts a fresh erase/transfer. It is a restart, not packet-level resume. The archive version cannot be compared with normal firmware while starting directly in the loader. Physical interrupted-update recovery is unverified; only the synthetic path is tested.

If a transfer stops after erase intent, keep scanner power and USB connected and preserve the journal. Decide recovery deliberately from the device state and official instructions. The utility does not guess or automatically invoke it.

## Files and diagnostics

Every command/response is logged as exact bytes with UTC timestamps and a simulation flag. Journals use exclusive initial creation, unique temporary files, flush/fsync and atomic replacement. Logs and exports are local diagnostic data; logs may reconstruct the vendor payload, and exports may expose configuration. They are not included in source or package distributions.
