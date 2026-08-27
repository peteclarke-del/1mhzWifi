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

$(BUILD)/test-live: tests/test_live_backend.c src/pi1mhz_mailbox.c \
		src/pi1mhz_net_backend.c src/pi1mhz_ftp.c include/pi1mhz_mailbox.h \
		include/pi1mhz_net_backend.h | $(BUILD)
	$(CC) -std=c11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Werror \
		-I include tests/test_live_backend.c src/pi1mhz_mailbox.c \
		src/pi1mhz_net_backend.c src/pi1mhz_ftp.c -lz -o $@

clean:
	rm -rf -- $(BUILD)
