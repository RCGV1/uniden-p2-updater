# Sources and attribution

This is an original Python implementation of observed interoperability behavior, not a vendor release. Protocol research inspected BC_VUP3 3.03/3.06 behavior and the BCD996P2 model configuration. The implementation pins one original official firmware input, rather than distributing it. Proprietary executable code, decompiled listings, resources, installers, firmware and download authentication are excluded.

Primary vendor sources:

- [BCD996P2 downloads](https://www.uniden.info/download/index.cfm?s=bcd996p2)
- [Firmware history and hardware-family notes](https://info.uniden.com/twiki/bin/view/UnidenMan4/BCD996P2FirmwareUpdate)
- [Official remote commands](https://info.uniden.com/twiki/pub/publish/_publish/BCD996P2_Remote_Commands.pdf), used for the readable-settings export. The firmware loader is a distinct interface reconstructed from the updater.

Earlier public work includes [Bearflash](https://github.com/gabtremblay/bearflash), a Python flasher for an older scanner generation, [Bearmock](https://github.com/gabtremblay/Bearmock), an updater-capture tool, and cross-platform SD staging projects [Scanner Manager](https://github.com/disturbedkh/scanner-manager) and [sds100](https://github.com/swannman/sds100). Their different models/transports are acknowledged without claiming their implementations were imported. This project imports pyserial and Python's standard library only.

The work is not described as clean-room because vendor behavior was examined through decompilation. No first-ever claim, patentability claim, vendor endorsement or general legal-clearance claim is made. The demonstrated contribution is the specific BCD996P2 transfer implementation and bounded macOS hardware evidence.

The original project source is GPL-3.0-only. pyserial is a separately distributed BSD-3-Clause dependency; its notice is retained in `THIRD_PARTY_NOTICES.md`. GitHub CI actions are external development tooling, not runtime dependencies.
