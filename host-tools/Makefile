BEEBASM ?= beebasm
CC ?= cc
REPO_ROOT := ..
MAILBOX := $(REPO_ROOT)/emulator/pi1mhz-mailbox
PI_OVERLAY := $(REPO_ROOT)/pi-side/pi1mhz-8468a38/overlay/src

.PHONY: all test test-elkulator test-elkulator-ssh-real test-ssh-real test-pi-firmware emulator-deps emulator-smoke-images clean distclean

all: build/nettools.ssd

build:
	mkdir -p build

COMMON_SOURCES := src/common/mos.inc src/common/pi1mhz_net.asm
SCAFFOLD_TOOLS := PING NSLOOK FTP HGET VIEWDAT

build/TERM: src/term.asm src/vt100.asm $(COMMON_SOURCES) | build
	$(BEEBASM) -i src/term.asm -o $@

build/SSH: src/ssh.asm src/vt100.asm src/common/pi1mhz_secure.asm $(COMMON_SOURCES) | build
	$(BEEBASM) -i src/ssh.asm -o $@

build/NETMENU: src/netmenu.asm src/common/mos.inc | build
	$(BEEBASM) -i src/netmenu.asm -o $@

build/PING: src/ping.asm src/common/tool_scaffold.inc src/common/mos.inc | build
	$(BEEBASM) -i src/ping.asm -o $@

build/NSLOOK: src/nslook.asm src/common/tool_scaffold.inc src/common/mos.inc | build
	$(BEEBASM) -i src/nslook.asm -o $@

build/FTP: src/ftp.asm src/common/tool_scaffold.inc src/common/mos.inc | build
	$(BEEBASM) -i src/ftp.asm -o $@

build/HGET: src/hget.asm src/common/tool_scaffold.inc src/common/mos.inc | build
	$(BEEBASM) -i src/hget.asm -o $@

build/VIEWDAT: src/viewdat.asm src/common/tool_scaffold.inc src/common/mos.inc | build
	$(BEEBASM) -i src/viewdat.asm -o $@

build/nettools.ssd: src/disc.asm build/NETMENU build/TERM build/SSH $(addprefix build/,$(SCAFFOLD_TOOLS)) | build
	rm -f $@
	$(BEEBASM) -i src/disc.asm -do $@ -boot NETMENU -title NETTOOLS
	truncate -s 204800 $@

build/TERMBOOT: src/term_smoke_boot.asm | build
	$(BEEBASM) -i $<

build/SSHBOOT: src/ssh_smoke_boot.asm | build
	$(BEEBASM) -i $<

build/SSHREALBOOT: src/ssh_real_smoke_boot.asm | build
	$(BEEBASM) -i $<

build/term-smoke.ssd: src/smoke_disc.asm build/TERMBOOT build/NETMENU build/TERM build/SSH | build
	rm -f $@
	$(BEEBASM) -i src/smoke_disc.asm -do $@ -opt 3 -title TERMTEST \
		-D SSH_SMOKE=0 -D SSH_REAL_SMOKE=0
	truncate -s 204800 $@

build/ssh-smoke.ssd: src/smoke_disc.asm build/SSHBOOT build/NETMENU build/TERM build/SSH | build
	rm -f $@
	$(BEEBASM) -i src/smoke_disc.asm -do $@ -opt 3 -title SSH_TEST \
		-D SSH_SMOKE=1 -D SSH_REAL_SMOKE=0
	truncate -s 204800 $@

build/ssh-real-smoke.ssd: src/smoke_disc.asm build/SSHREALBOOT build/NETMENU build/TERM build/SSH | build
	rm -f $@
	$(BEEBASM) -i src/smoke_disc.asm -do $@ -opt 3 -title SSH_REAL \
		-D SSH_SMOKE=0 -D SSH_REAL_SMOKE=1
	truncate -s 204800 $@

emulator-smoke-images: build/term-smoke.ssd build/ssh-smoke.ssd

test-elkulator: emulator-smoke-images
	./tests/run_elkulator_smoke.sh

test-elkulator-ssh-real: build/ssh-real-smoke.ssd
	WOLFSSH_PREFIX=$(WOLFSSH_PREFIX) ./tests/run_elkulator_ssh_real.sh

build/test-pi1mhz-mailbox: \
		$(MAILBOX)/tests/test_mailbox.c \
		$(MAILBOX)/src/pi1mhz_mailbox.c \
		$(MAILBOX)/include/pi1mhz_mailbox.h | build
	$(CC) -std=c11 -Wall -Wextra -Werror \
		-I $(MAILBOX)/include \
		$(MAILBOX)/tests/test_mailbox.c \
		$(MAILBOX)/src/pi1mhz_mailbox.c -o $@

build/test-pi1mhz-live: \
		$(MAILBOX)/tests/test_live_backend.c \
		$(MAILBOX)/src/pi1mhz_mailbox.c \
		$(MAILBOX)/src/pi1mhz_net_backend.c \
		$(MAILBOX)/include/pi1mhz_mailbox.h \
		$(MAILBOX)/include/pi1mhz_net_backend.h | build
	$(CC) -std=c11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Werror \
		-I $(MAILBOX)/include \
		$(MAILBOX)/tests/test_live_backend.c \
		$(MAILBOX)/src/pi1mhz_mailbox.c \
		$(MAILBOX)/src/pi1mhz_net_backend.c -lz -o $@

build/test-secure-service-core: \
		$(REPO_ROOT)/pi-side/tests/test_secure_service_core.c \
		$(PI_OVERLAY)/secure_service_core.c \
		$(PI_OVERLAY)/secure_service_core.h | build
	$(CC) -std=c11 -Wall -Wextra -Werror \
		-I $(PI_OVERLAY) $(REPO_ROOT)/pi-side/tests/test_secure_service_core.c \
		$(PI_OVERLAY)/secure_service_core.c -o $@

test: build/nettools.ssd build/test-pi1mhz-mailbox build/test-pi1mhz-live \
		build/test-secure-service-core
	./build/test-pi1mhz-mailbox
	./build/test-pi1mhz-live
	./build/test-secure-service-core
	PYTHONPATH=.test-deps PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v

emulator-deps:
	python3 -m pip install --target .test-deps -r requirements-dev.txt

WOLFSSH_PREFIX ?= /tmp/wolf-install

build/wolfssh-probe: $(MAILBOX)/tests/wolfssh_probe.c \
		$(MAILBOX)/src/pi1mhz_wolfssh.c \
		$(MAILBOX)/include/pi1mhz_wolfssh.h | build
	$(CC) -std=gnu11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Werror \
		-I $(MAILBOX)/include -I $(WOLFSSH_PREFIX)/include \
		$(MAILBOX)/tests/wolfssh_probe.c $(MAILBOX)/src/pi1mhz_wolfssh.c \
		$(WOLFSSH_PREFIX)/lib/libwolfssh.a \
		$(WOLFSSH_PREFIX)/lib/libwolfssl.a -lpthread -lm -lutil -o $@

test-ssh-real: build/wolfssh-probe
	WOLFSSH_PREFIX=$(WOLFSSH_PREFIX) ./tests/run_wolfssh_real.sh

test-pi-firmware:
	cd $(REPO_ROOT) && ./pi-side/tests/run_secure_build.sh

clean:
	rm -rf -- build
	$(MAKE) -C $(MAILBOX) clean

distclean: clean
	rm -rf -- .test-deps
	find . -type d -name __pycache__ -prune -exec rm -rf -- {} +
