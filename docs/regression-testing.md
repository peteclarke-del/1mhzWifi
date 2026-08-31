# Regression ownership

Every physical or emulator failure which changes production code must become a
permanent executable regression before the fix is accepted. The source of
record is [`tests/regression_manifest.json`](../tests/regression_manifest.json).

The manifest records root-cause failures rather than every repeated hardware
observation. For example, `Bad Program`, a return to the prompt after the first
file, and a second `*MENU` hang may share one damaged WiCFS lifecycle. Each
distinct failure boundary still has its own identifier when it needs a
different executable assertion.

## Required workflow

1. Record the exact symptom, artifact hashes, hardware profile and last visible
   operation.
2. Reproduce the failure in an assembled-ROM, Pi service, emulator, or
   outcome-runner test. A source-text assertion alone is insufficient for a
   runtime defect.
3. Confirm that the new test fails against the defective artifact or mutation.
4. Implement the generic fix.
5. Confirm the regression passes along with the complete suite.
6. For hardware-originated defects, run the corresponding outcome test with
   immutable provenance, bus evidence, reviewed screen states, input-correlated
   change, liveness and filing-system recovery.
7. Keep the entry `open-hardware` until the exact physical configuration passes.

`tests/test_regression_manifest.py` prevents a ledger entry from pointing at a
missing or undiscovered test. Fixed entries cannot be represented only by prose.
Open hardware entries must name both the acceptance runner and the exact profile
which remains unproven.

Lifecycle failures have a stricter rule. A second launch must occur inside the
same emulator process. Restarting Elkulator clears the state which caused the
physical failure and is not valid evidence. `WICFS-009` binds to
`run_uef_gameplay.py --recovery-check`, which enters gameplay, issues Break,
proves real BeebSCSI reads after `*ADFS`, mounts and reads the UEF directory,
loads the same UEF again, enters gameplay again and requires continuing motion.
`WICFS-010` also binds to `run_catalogue_differential.py --repeat-after-break`.
That path launches from `*MENU`, enters gameplay, issues Break, invokes
`*MENU` again and requires the same title to enter active gameplay a second
time without restarting Elkulator.

## Acceptance boundaries

A UEF or MENU test does not pass because a file downloaded, a title appeared,
or the emulator remained open. It must demonstrate the expected program state,
input-correlated transition, sustained execution, no known MOS failure, and the
required post-Break filing-system behavior. When Tube coexistence is in scope,
the bus trace must also prove that 1MHz-WiFi did not use Tube registers.

Some loaders display their final-looking instruction screen before later tape
files have loaded. The UEF runner therefore requires both the reviewed screen
and a quiescent 1MHz bus for a stable interval before injecting input. A screen
match while bus traffic continues is a loading state, not a gameplay gate.

The local Electron corpus currently contains 728 UEF files. Structural analysis
accepts 727, identifies one genuinely truncated image, records 42 streams larger
than the legacy 64 KiB public window, and finds one cassette block which loads
across WiCFS workspace at `&0380`. Legal residual bytes after a CFS block CRC are
reported but accepted because original WiCFS skips the remainder of the chunk.

A network test does not pass because the Pi accepted a command. It must observe
the final host response, bounded return, correct display mode, and clean
re-entry. Delayed mailbox publication and adjacent-register interference are
part of the normal test model because both occurred on physical Pi1MHz hardware.

## Adding a regression

Add a stable identifier to the manifest and reference one or more test methods
using:

```text
relative/test_file.py::TestClass::test_method
```

Put project tests under `tests/` and NetTools tests under `host-tools/tests/`.
Both locations are executed by `make test`. Do not delete or rename a referenced
test without updating the manifest and preserving the original failure
boundary.
