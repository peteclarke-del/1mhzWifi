# 1mhzNetTools merge record

The former sibling `1mhzNetTools` project was merged into this repository in
August 2026. The merge keeps the original ElkWiFi-derived host ROM work apart
from the Pi1MHz firmware integration. It does not patch or rewrite the
upstream ElkWiFi repository in place.

## File disposition

| Former content | Unified location | Disposition |
| --- | --- | --- |
| `src/` | `host-tools/src/` | Imported; secure commands rebased from 91-97 to 94-100 |
| `tests/` | `host-tools/tests/` | Imported; repository paths and command fixtures updated |
| `requirements-dev.txt` | `host-tools/requirements-dev.txt` | Imported unchanged |
| root `Makefile` | `host-tools/Makefile` and repository `Makefile` | Split into component and unified entry points |
| root `README.md` | `host-tools/README.md` | Imported and revised for the combined repository |
| `docs/secure_service_abi.md` | `host-tools/docs/secure_service_abi.md` | Imported with the reconciled command allocation |
| `docs/ssh_https_plan.md` | `host-tools/docs/ssh_https_plan.md` | Imported and revised to reference central packages |
| `patches/pi1mhz-mailbox-emulator/` | `emulator/pi1mhz-mailbox/` | Imported as the reusable mailbox/JIM implementation |
| secure firmware source files | `pi-side/pi1mhz-516a267/overlay/src/` | Imported into the central Pi overlay |
| secure core test | `pi-side/tests/test_secure_service_core.c` | Imported into central Pi tests |
| `wolfssh-pi1mhz.patch` | `pi-side/pi1mhz-516a267/patches/` | Imported unchanged |
| standalone firmware installer | `pi-side/install_bundle.sh` | Superseded by the combined installer |
| standalone `pi1mhz.patch` | central Pi patch series and `pi-side/upstream/1mhzwifi-pi1mhz.patch` | Superseded and regenerated from the combined source |
| standalone firmware build test | `pi-side/tests/run_secure_build.sh` | Superseded by the combined two-kernel build gate |
| patch-package READMEs | component READMEs and this record | Consolidated |
| former `.gitignore` files | root and component `.gitignore` files | Consolidated |

No former source or test remains authoritative outside this repository. The
command-number differences are intentional: commands 80-93 belong to the
ElkWiFi-compatible host service, commands 94-100 implement the secure service,
and commands 101-113 are reserved for that service.

## Validation completed before sibling removal

- Root ROM, integration and UEF test suite: 34 tests.
- Host-tool assembled DFS image and py65 suite: 17 tests.
- Mailbox/JIM unit and live loopback tests.
- Secure-service ABI core test.
- Real wolfSSH public-key, password, changed-host and failed-authentication
  tests.
- Elkulator TERM and SSH fixture tests using the assembled DFS images.
- Assembled SSH client through Elkulator to the real wolfSSH test server.
- Clean Pi 1/Zero `kernel.img` build.
- Clean Pi 2/3 `kernel7.img` build.
- Consolidated upstream patch generation and clean `git apply --check`.

These tests establish merge and build integrity. A live Elkulator test with
the photographed ROM order, AP5 Tube model and Internet mailbox bridge reached
the Arcadians program under ROM 0.1.28. 1MHzWifi did not access or disable the
Tube. The physical Electron result remains a separate acceptance gate in the
hardware checklist.
