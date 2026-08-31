# GitHub repository settings baseline

These controls complement the files in `.github`. They must be configured by a
repository administrator and verified after ownership, visibility or plan
changes. A checked box records an observed setting, not an intention.

## Repository identity

- [ ] Default branch is `main`.
- [ ] Description identifies 1MHz-WiFi as an ElkWiFi-compatible Pi1MHz project.
- [ ] Repository topics cover Acorn Electron, BBC Micro, Pi1MHz, 6502 and
  Raspberry Pi.
- [ ] Issues are enabled and present the maintained issue forms.
- [ ] The support and security links resolve from the public repository.

## Main branch ruleset

- [ ] Direct force pushes and branch deletion are blocked.
- [ ] Pull requests must be up to date with `main` before merge.
- [ ] The `unified-tests` CI result is required.
- [ ] Conversations must be resolved before merge.
- [ ] CODEOWNERS review is requested for owned paths.
- [ ] Administrator bypass is limited to recovery and documented emergencies.

This is currently a solo-maintainer repository. Do not require an approval that
the sole maintainer cannot obtain. When a second maintainer is appointed,
require at least one approval for firmware, ROM, workflow, security, governance
and licensing changes.

## Merge and release policy

- [ ] Delete merged topic branches automatically.
- [ ] Do not permit merge commits which obscure the reviewed patch boundary.
- [ ] Protect release tags matching the project's chosen version convention.
- [ ] Release notes identify source commit, artifact hashes, upstream revisions,
  validation status and open hardware gates.
- [ ] A release marked validated has matching physical-hardware evidence.

## Actions

- [ ] Default workflow token permissions are read-only.
- [ ] Write permissions require an explicit workflow-level declaration.
- [ ] Actions are restricted to GitHub-maintained actions and specifically
  reviewed external actions.
- [ ] Fork pull requests cannot obtain repository secrets without approval.
- [ ] The CI workflow remains reproducible from a clean Ubuntu runner.

## Security

- [ ] Private vulnerability reporting is enabled.
- [ ] Dependabot alerts and security updates are enabled.
- [ ] Secret scanning and push protection are enabled when available.
- [ ] No production credentials, WiFi profiles, private keys or writable media
  images are stored in Actions artifacts or repository releases.
- [ ] Security advisories follow `SECURITY.md` and credit reporters when agreed.

## Periodic audit

Review this checklist before each tagged release and after any change to GitHub
ownership, visibility, installed applications or Actions policy. Compare
`.github/CODEOWNERS`, branch rules and the maintainer list in `GOVERNANCE.md`.
