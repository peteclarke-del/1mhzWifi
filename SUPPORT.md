# Support

## Project status

1MHzWifi is under active hardware validation. The current artifacts are test
candidates, not a completed replacement for every ElkWiFi configuration.
Open release gates are listed in `TODO.md` and `docs/hardware-validation.md`.

## Asking for help

Use a GitHub issue for build problems, reproducible command failures, emulator
integration problems and hardware compatibility reports. Choose the closest
issue form and provide:

- the 1MHzWifi ROM version and SHA-256 hash;
- the Pi kernel filename, revision and hash;
- the Acorn model, MOS version, filing system and complete expansion layout;
- the Pi model and WiFi chipset where known;
- Tube state, ROM order, sideways RAM banks and OSHWM when relevant;
- the exact command sequence and complete output;
- whether the same files work with an earlier build;
- sanitised logs, traces or photographs.

For Elkulator, include the emulator commit, patch-kit version, runtime ROM
hashes and mailbox mode. For B-Em, include its commit and generated
configuration. A test using a different filing system, ROM order or Tube state
is useful evidence, but it is not an exact reproduction.

## Scope boundaries

The project can investigate faults in the 1MHzWifi ROM, maintained Pi1MHz
patches, NetTools and maintained emulator adapters. It cannot provide general
support for access points, unofficial ROMs, damaged hardware, unrelated
filing-system images or third-party games. Compatibility reports in those
areas are still welcome when they isolate a 1MHzWifi regression.

Do not attach WiFi passwords, private keys, registration credentials, writable
SD-card images or unsanitised packet captures. Report security problems using
the private process in `SECURITY.md`.
