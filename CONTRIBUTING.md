# Contributing

Participation is subject to the [code of conduct](CODE_OF_CONDUCT.md),
[project governance](GOVERNANCE.md), [security policy](SECURITY.md) and current
[licensing status](LICENSING.md).

Changes must preserve the distinction between the host-facing ElkWiFi contract
and the private Pi1MHz transport. Do not expose Pi implementation details by
renumbering stock OSWORD functions or changing established command syntax.

## Development workflow

1. Follow the clean-checkout process in
   [`docs/building.md`](docs/building.md).
2. Make source changes in this repository, not only in a generated upstream checkout.
3. Keep patch application repeatable and update each already-applied test when required.
4. Build the 16 KiB ROM and both Pi kernel families for protocol or ABI changes.
5. Run the automated tests and the applicable hardware checklist sections.
6. Update command, architecture, status, and hash documentation in the same change.

Required local checks:

```sh
make deps
make test
sha256sum --check --strict SHA256SUMS
```

## Change requirements

- Never allow an unsupported operation to fall through to the original `&FC30` UART.
- Never downgrade TLS, HTTPS, or SSH requests to plaintext.
- Keep FIQ work bounded. Network and filesystem work belongs in the cooperative poll path.
- Bound all host-visible buffers and every missing-device poll.
- Preserve existing `Pi1MHz.cfg` values unless the change explicitly migrates them.
- Keep Pi1MHz mailbox, network, JIM and WiCFS title traffic on the 1 MHz bus
  and I/O processor. 1MHzWifi must not claim a Tube channel, access Tube
  registers, disable a fitted Tube or transfer a title to the parasite. A game
  may use an available Tube after 1MHzWifi has launched it.
- Add a regression test for each corrected failure mode.
- Record hardware model, hashes, and exact command output for hardware-only failures.
- Keep third-party ROMs and test media under ignored local storage. Never add
  them to commits, generated upstream patches or release archives unless their
  redistribution has been reviewed and explicitly approved.
- Identify all copied or derived source and confirm the right to contribute it.

## Commit scope

Keep commits narrow enough to review against the transport and host contracts.
Generated ROM and bundle changes must be committed with the source changes that
produced them. Do not commit local upstream checkouts, Python caches, production
credentials, SD-card working files, or unrelated Pi1MHz changes.

## Pull requests

Open an issue first for public ABI changes, security-sensitive design changes,
new hardware targets or changes which alter upstream licensing obligations.
Complete the pull-request template and distinguish automated, emulator and
physical-hardware evidence. An emulator result must state the precise runtime,
ROM hashes and mailbox model. It must not be presented as physical validation.

The maintainer may request that a large change be split by upstream target or
failure mode. Generated patches and binaries must remain paired with the source
and tests that produced them.
