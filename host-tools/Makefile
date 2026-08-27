BEEBASM ?= beebasm
CC ?= cc
REPO_ROOT := ..
MAILBOX := $(REPO_ROOT)/emulator/pi1mhz-mailbox
PI_OVERLAY := $(REPO_ROOT)/pi-side/pi1mhz-516a267/overlay/src

# NET_DEBUG=1 traces the shared FCA6-FCA9 command/result sequence on screen
# for real-hardware debugging. `make debug` always builds a NET_DEBUG=1 disc
# (build/nettools-debug.ssd) alongside the normal build; this variable exists
# only if you want the default `all`/`test` targets built with tracing too.
NET_DEBUG ?= 0

.PHONY: all debug test test-elkulator test-elkulator-ssh-real test-ssh-real test-pi-firmware emulator-deps emulator-smoke-images clean distclean

all: build/nettools.ssd

debug: build/nettools-debug.ssd

build:
	mkdir -p build

COMMON_SOURCES := src/common/mos.inc src/common/pi1mhz_net.asm src/common/application.asm

build/TELNET: src/telnet.asm src/vt100.asm $(COMMON_SOURCES) | build
	$(BEEBASM) -i src/telnet.asm -o $@ -D NET_DEBUG=$(NET_DEBUG)

build/SSH: src/ssh.asm src/vt100.asm src/common/pi1mhz_secure.asm $(COMMON_SOURCES) | build
	$(BEEBASM) -i src/ssh.asm -o $@ -D NET_DEBUG=$(NET_DEBUG)

build/SFTP: src/sftp.asm src/common/pi1mhz_secure.asm $(COMMON_SOURCES) | build
	$(BEEBASM) -i src/sftp.asm -o $@ -D NET_DEBUG=$(NET_DEBUG)

build/NETMENU: src/netmenu.asm src/common/mos.inc src/common/application.asm | build
	$(BEEBASM) -i src/netmenu.asm -o $@

build/HWDTEST: src/hwdtest.asm src/common/pi1mhz_net.asm src/common/tool_common.asm src/common/mos.inc src/common/application.asm | build
	$(BEEBASM) -i src/hwdtest.asm -o $@ -D NET_DEBUG=0

build/NETMENUL: src/tool_loader.asm src/common/mos.inc build/NETMENU | build
	$(BEEBASM) -i src/tool_loader.asm -o $@ -D LOADER_ID=1 -D MAIN_SIZE=$$(wc -c < build/NETMENU)

build/TELNETL: src/tool_loader.asm src/common/mos.inc build/TELNET | build
	$(BEEBASM) -i src/tool_loader.asm -o $@ -D LOADER_ID=2 -D MAIN_SIZE=$$(wc -c < build/TELNET)

build/SSHL: src/tool_loader.asm src/common/mos.inc build/SSH | build
	$(BEEBASM) -i src/tool_loader.asm -o $@ -D LOADER_ID=3 -D MAIN_SIZE=$$(wc -c < build/SSH)

build/HWDTESTL: src/tool_loader.asm src/common/mos.inc build/HWDTEST | build
	$(BEEBASM) -i src/tool_loader.asm -o $@ -D LOADER_ID=6 -D MAIN_SIZE=$$(wc -c < build/HWDTEST)

build/SFTPL: src/tool_loader.asm src/common/mos.inc build/SFTP | build
	$(BEEBASM) -i src/tool_loader.asm -o $@ -D LOADER_ID=7 -D MAIN_SIZE=$$(wc -c < build/SFTP)

LOADERS := build/NETMENUL build/TELNETL build/SSHL build/HWDTESTL build/SFTPL

build/nettools.ssd: src/disc.asm build/NETMENU build/TELNET build/SSH build/SFTP build/HWDTEST $(LOADERS) | build
	rm -f $@
	$(BEEBASM) -i src/disc.asm -do $@ -boot NETMENU -title NETTOOLS
	truncate -s 204800 $@

build/TELNET-debug: src/telnet.asm src/vt100.asm $(COMMON_SOURCES) | build
	$(BEEBASM) -i src/telnet.asm -o $@ -D NET_DEBUG=1

build/SSH-debug: src/ssh.asm src/vt100.asm src/common/pi1mhz_secure.asm $(COMMON_SOURCES) | build
	$(BEEBASM) -i src/ssh.asm -o $@ -D NET_DEBUG=1

build/SFTP-debug: src/sftp.asm src/common/pi1mhz_secure.asm $(COMMON_SOURCES) | build
	$(BEEBASM) -i src/sftp.asm -o $@ -D NET_DEBUG=1

build/nettools-debug.ssd: src/disc-debug.asm build/NETMENU build/TELNET-debug build/SSH-debug build/SFTP-debug build/HWDTEST $(LOADERS) | build
	rm -f $@
	$(BEEBASM) -i src/disc-debug.asm -do $@ -boot NETMENU -title NETTOOLS
	truncate -s 204800 $@

build/TELNETBOOT: src/telnet_smoke_boot.asm | build
	$(BEEBASM) -i $<

build/SSHBOOT: src/ssh_smoke_boot.asm | build
	$(BEEBASM) -i $<

build/SSHREALBOOT: src/ssh_real_smoke_boot.asm | build
	$(BEEBASM) -i $<

build/TELNETREALBOOT: src/telnet_real_smoke_boot.asm | build
	$(BEEBASM) -i $<

build/telnet-smoke.ssd: src/smoke_disc.asm build/TELNETBOOT build/NETMENU build/TELNET build/SSH $(LOADERS) | build
	rm -f $@
	$(BEEBASM) -i src/smoke_disc.asm -do $@ -opt 3 -title TELNET \
		-D SSH_SMOKE=0 -D SSH_REAL_SMOKE=0 -D TELNET_REAL_SMOKE=0
	truncate -s 204800 $@

build/ssh-smoke.ssd: src/smoke_disc.asm build/SSHBOOT build/NETMENU build/TELNET build/SSH $(LOADERS) | build
	rm -f $@
	$(BEEBASM) -i src/smoke_disc.asm -do $@ -opt 3 -title SSH_TEST \
		-D SSH_SMOKE=1 -D SSH_REAL_SMOKE=0 -D TELNET_REAL_SMOKE=0
	truncate -s 204800 $@

build/ssh-real-smoke.ssd: src/smoke_disc.asm build/SSHREALBOOT build/NETMENU build/TELNET build/SSH $(LOADERS) | build
	rm -f $@
	$(BEEBASM) -i src/smoke_disc.asm -do $@ -opt 3 -title SSH_REAL \
		-D SSH_SMOKE=0 -D SSH_REAL_SMOKE=1 -D TELNET_REAL_SMOKE=0
	truncate -s 204800 $@

build/telnet-real-smoke.ssd: src/smoke_disc.asm build/TELNETREALBOOT build/NETMENU build/TELNET build/SSH $(LOADERS) | build
	rm -f $@
	$(BEEBASM) -i src/smoke_disc.asm -do $@ -opt 3 -title TEL_REAL \
		-D SSH_SMOKE=0 -D SSH_REAL_SMOKE=0 -D TELNET_REAL_SMOKE=1
	truncate -s 204800 $@

emulator-smoke-images: build/telnet-smoke.ssd build/ssh-smoke.ssd

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
		$(MAILBOX)/src/pi1mhz_ftp.c \
		$(MAILBOX)/include/pi1mhz_mailbox.h \
		$(MAILBOX)/include/pi1mhz_net_backend.h | build
	$(CC) -std=c11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Werror \
		-I $(MAILBOX)/include \
		$(MAILBOX)/tests/test_live_backend.c \
		$(MAILBOX)/src/pi1mhz_mailbox.c \
		$(MAILBOX)/src/pi1mhz_net_backend.c \
		$(MAILBOX)/src/pi1mhz_ftp.c -lz -o $@

build/test-secure-service-core: \
		$(REPO_ROOT)/pi-side/tests/test_secure_service_core.c \
		$(PI_OVERLAY)/secure_service_core.c \
		$(PI_OVERLAY)/secure_service_core.h | build
	$(CC) -std=c11 -Wall -Wextra -Werror \
		-I $(PI_OVERLAY) $(REPO_ROOT)/pi-side/tests/test_secure_service_core.c \
		$(PI_OVERLAY)/secure_service_core.c -o $@

build/test-media-catalogue: \
		$(REPO_ROOT)/pi-side/tests/test_media_catalogue.c \
		$(PI_OVERLAY)/media_catalogue.c \
		$(PI_OVERLAY)/media_catalogue.h | build
	$(CC) -std=c11 -Wall -Wextra -Werror \
		-I $(PI_OVERLAY) $(REPO_ROOT)/pi-side/tests/test_media_catalogue.c \
		$(PI_OVERLAY)/media_catalogue.c -o $@

test: build/nettools.ssd build/nettools-debug.ssd build/test-pi1mhz-mailbox build/test-pi1mhz-live \
		build/test-secure-service-core build/test-media-catalogue
	./build/test-pi1mhz-mailbox
	./build/test-pi1mhz-live
	./build/test-secure-service-core
	./build/test-media-catalogue
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
