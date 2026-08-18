# Project governance

## Scope

1MHzWifi is maintained as an integration project spanning the ElkWiFi host
contract, the Pi1MHz bare-metal firmware, Acorn host tools and emulator
adapters. Changes must remain suitable for submission to the respective
upstream projects. Generated patches do not transfer ownership of upstream
code to this repository.

## Roles

Peter Clarke (`@peteclarke-del`) is the current maintainer and release owner.
The maintainer sets release scope, approves changes, controls repository
settings and decides whether evidence satisfies a hardware gate.

Contributors may propose, implement, test and review changes. Repeated or
substantial contribution does not by itself grant release or repository
administration authority. Additional maintainers may be appointed publicly in
this file and in `.github/CODEOWNERS`.

## Decision process

Decisions are made in this order of priority:

1. Preserve the documented public ElkWiFi command and OSWORD contract.
2. Protect Acorn memory, filing systems, the 1 MHz bus and fitted expansions.
3. Preserve secure fail-closed behaviour and credential handling boundaries.
4. Prefer reproducible hardware or hardware-accurate emulator evidence.
5. Keep patches reviewable and acceptable to their upstream maintainers.
6. Prefer the smallest maintainable change that fixes the demonstrated cause.

Normal changes are decided through pull-request review. Significant ABI,
security, licensing, hardware-support or release-policy changes require an
issue describing the proposal before implementation. The maintainer records
the final decision and its evidence in the issue or pull request.

## Compatibility and evidence

Automated tests are necessary but do not override physical hardware results.
A change which affects timing, JIM RAM, vectors, filing systems, WiCFS, Tube
coexistence or Pi model support remains a hardware-test candidate until the
applicable checks in `docs/hardware-validation.md` pass.

The Tube is a coexistence requirement, not a transport destination. 1MHzWifi
must not transfer host programs into a fitted parasite. Platform-specific
workarounds require runtime detection or a documented override and must not be
hard-coded to one owner's ROM layout.

## Releases

Only the maintainer creates a release. A release must identify its source
commit, ROM version, Pi1MHz revision, artifact hashes, completed validation
matrix and known limitations. Generated ROMs, kernels, host tools and patches
must match the reviewed source. A release may be labelled as a hardware-test
candidate when physical gates remain open, but it must not be described as
validated.

Repository settings which enforce this process are listed in
`docs/github-repository-settings.md`. They require periodic administrator
review because GitHub does not derive them from this document.

## Upstream and third-party material

Upstream changes remain separated into the ElkWiFi, Pi1MHz, Elkulator and
B-Em patch areas. Third-party ROMs, disc images, credentials and hardware media
are local test inputs and must not be committed or added to patch kits. See
`NOTICE`, `LICENSING.md` and `THIRD_PARTY_NOTICES.md` before importing source
or binaries.

## Conduct and security

Participation is governed by `CODE_OF_CONDUCT.md`. Security reports follow
`SECURITY.md`. A security or conduct report must not be moved into a public
issue without the reporter's agreement.
