BEEBASM ?= beebasm
WOLFSSH_PREFIX ?= /tmp/wolf-install

.PHONY: test test-rom test-emulator test-host test-package patch-kits \
 test-ssh-real test-elkulator test-elkulator-ssh-real test-pi-firmware \
 test-pi-integration test-all deps clean

test: test-rom test-emulator test-host test-package

test-rom: test-host
	./build.sh
	PYTHONPATH=host-tools/.test-deps PYTHONDONTWRITEBYTECODE=1 \
		python3 -m unittest discover -s tests -v

test-emulator:
	$(MAKE) -C emulator/pi1mhz-mailbox test

test-host:
	$(MAKE) -C host-tools test BEEBASM="$(BEEBASM)"

test-package:
	unzip -t build/pi1mhz-all-hardware-test.zip
	git diff --check
	@# grep, not rg: a missing rg made this check pass silently, so a
	@# typographic dash reached CI unseen.
	@if grep -rn '—\|–' --include='*.md' --include='*.txt' .; then \
		echo "Documentation contains a typographic dash" >&2; exit 1; \
	fi

patch-kits:
	./scripts/package_patch_kits.sh

test-ssh-real:
	$(MAKE) -C host-tools test-ssh-real WOLFSSH_PREFIX="$(WOLFSSH_PREFIX)"

test-elkulator:
	$(MAKE) -C host-tools test-elkulator BEEBASM="$(BEEBASM)"

test-elkulator-ssh-real:
	$(MAKE) -C host-tools test-elkulator-ssh-real \
		BEEBASM="$(BEEBASM)" WOLFSSH_PREFIX="$(WOLFSSH_PREFIX)"

# The ARM firmware build. Needs arm-none-eabi-gcc and the Pi1MHz submodules.
test-pi-firmware:
	./pi-side/tests/run_firmware_build.sh

# Apply the integration to the pinned Pi1MHz and run the host suites that live
# in that tree. Needs git and a network, not an ARM toolchain, so this is the
# gate that can run in CI - and it is the one that covers the services this
# package no longer carries but still patches.
test-pi-integration:
	./pi-side/tests/run_pi_host_tests.sh

test-all: test test-pi-integration test-ssh-real test-elkulator \
	test-elkulator-ssh-real

deps:
	$(MAKE) -C host-tools emulator-deps

clean:
	$(MAKE) -C host-tools clean
