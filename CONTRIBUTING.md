# Contributing

Changes must preserve the distinction between the host-facing ElkWiFi contract
and the private Pi1MHz transport. Do not expose Pi implementation details by
renumbering stock OSWORD functions or changing established command syntax.

## Development workflow

1. Start from clean, pinned ElkWiFi and Pi1MHz checkouts.
2. Make source changes in this repository, not only in a generated upstream checkout.
3. Keep patch application repeatable and update each already-applied test when required.
4. Build the 16 KiB ROM and both Pi kernel families for protocol or ABI changes.
5. Run the automated tests and the applicable hardware checklist sections.
6. Update command, architecture, status, and hash documentation in the same change.

Required local checks:

```sh
./build.sh
python3 -m unittest discover -s tests -v
unzip -t build/pi1mhz-all-hardware-test.zip
```

## Change requirements

- Never allow an unsupported operation to fall through to the original `&FC30` UART.
- Never downgrade TLS, HTTPS, or SSH requests to plaintext.
- Keep FIQ work bounded. Network and filesystem work belongs in the cooperative poll path.
- Bound all host-visible buffers and every missing-device poll.
- Preserve existing `Pi1MHz.cfg` values unless the change explicitly migrates them.
- Treat Tube pointers as parasite addresses until MOS transfer semantics have copied the data.
- Add a regression test for each corrected failure mode.
- Record hardware model, hashes, and exact command output for hardware-only failures.

## Commit scope

Keep commits narrow enough to review against the transport and host contracts.
Generated ROM and bundle changes must be committed with the source changes that
produced them. Do not commit local upstream checkouts, Python caches, production
credentials, SD-card working files, or unrelated Pi1MHz changes.

