CC ?= cc
BUILD := .build

.PHONY: test clean

test: $(BUILD)/test-mailbox $(BUILD)/test-live
	./$(BUILD)/test-mailbox
	./$(BUILD)/test-live

$(BUILD):
	mkdir -p $@

$(BUILD)/test-mailbox: tests/test_mailbox.c src/pi1mhz_mailbox.c \
		include/pi1mhz_mailbox.h | $(BUILD)
	$(CC) -std=c11 -Wall -Wextra -Werror -I include \
		tests/test_mailbox.c src/pi1mhz_mailbox.c -o $@

# The media service session core and container decoder are shared with the Pi
# overlay rather than reimplemented here, so the emulator answers commands 120
# to 124 with exactly the kernel's logic.
OVERLAY := ../../pi-side/pi1mhz-516a267/overlay/src

$(BUILD)/test-live: tests/test_live_backend.c src/pi1mhz_mailbox.c \
		src/pi1mhz_net_backend.c src/pi1mhz_ftp.c include/pi1mhz_mailbox.h \
		include/pi1mhz_net_backend.h $(OVERLAY)/media_service_core.c \
		$(OVERLAY)/media_catalogue.c | $(BUILD)
	$(CC) -std=c11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Werror \
		-I include -I $(OVERLAY) tests/test_live_backend.c \
		src/pi1mhz_mailbox.c \
		src/pi1mhz_net_backend.c src/pi1mhz_ftp.c \
		$(OVERLAY)/media_service_core.c $(OVERLAY)/media_catalogue.c \
		-lz -o $@

clean:
	rm -rf -- $(BUILD)
