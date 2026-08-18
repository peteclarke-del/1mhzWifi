## Summary

Describe the fault or requirement and the resulting behaviour.

## Scope

- Host ROM:
- Pi1MHz firmware:
- NetTools:
- Emulator adapters:
- Documentation or packaging:

## Compatibility impact

State any effect on the ElkWiFi command or OSWORD contract, JIM RAM, vectors,
filing systems, Tube coexistence, supported Pi models and existing ROM layouts.
Use "none" only when the change cannot affect that boundary.

## Verification

List the exact commands run and their results. Include hashes for generated
artifacts.

- [ ] Relevant automated tests pass.
- [ ] The clean build or patch-application path passes.
- [ ] Emulator acceptance reaches the required outcome, not only a prompt or
      intermediate screen.
- [ ] Applicable physical-hardware checks pass, or remain explicitly open.
- [ ] Tube-off and Tube-on effects are stated.
- [ ] Filing-system coverage is stated.

## Evidence

Link or attach sanitised reports, traces and screenshots. Record hardware and
emulator provenance. Do not include credentials, private keys or writable
media images.

## Contributor checklist

- [ ] The change is focused and contains no unrelated generated files.
- [ ] A regression test covers each corrected failure mode.
- [ ] Documentation and release hashes are updated where applicable.
- [ ] Third-party source and binary provenance is recorded.
- [ ] No third-party ROMs, test media or secrets are committed.
- [ ] I have the right to contribute all material in this pull request.
