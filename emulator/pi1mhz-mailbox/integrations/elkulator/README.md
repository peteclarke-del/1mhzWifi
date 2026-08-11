# Elkulator Pi1MHz and AP5 patch kit

This directory contains the Elkulator-specific part of the reusable Pi1MHz
mailbox emulator. Distribute it as part of the complete
`emulator/pi1mhz-mailbox` directory so the shared headers, device core and
network backend remain available to `install.sh`.

The reviewed clean Elkulator base is Stardot Elkulator commit
`6cab45aba68fc3d3bdaea4c28b5de4de0307e00e`. The installer also recognises the
ElkChat tree which already contains the legacy ElkWiFi command-line changes.
The two small `*-elkwifi.patch` files are compatibility variants for that
source shape, not duplicate runtime implementations.

Install into a disposable checkout:

```sh
./integrations/elkulator/install.sh /path/to/elkulator
```

Then rebuild Elkulator with its normal Autotools process. Enable the emulated
Pi1MHz device with `PI1MHZ_MAILBOX=fixture` or `PI1MHZ_MAILBOX=live`. See
`TECHNICAL.md` for the hardware model and acceptance limits.
