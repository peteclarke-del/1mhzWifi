\ Same disc layout as disc.asm, built from the NET_DEBUG=1 object files so it
\ can coexist with the release build/nettools.ssd under build/.

PUTFILE "build/NETMENUL", "NETMENU", &32000, &32000
PUTFILE "build/TELNETL", "TELNET", &32000, &32000
PUTFILE "build/SSHL", "SSH", &32000, &32000
PUTFILE "build/PINGL", "PING", &32000, &32000
PUTFILE "build/NSLOOKL", "NSLOOK", &32000, &32000
PUTFILE "build/HWDTESTL", "HWDTEST", &32000, &32000
PUTFILE "build/NETMENU", "NTMENU", &32200, &32200
PUTFILE "build/TELNET-debug", "NTTEL", &32200, &32200
PUTFILE "build/SSH-debug", "NTSSH", &32200, &32200
PUTFILE "build/PING-debug", "NTPING", &32200, &32200
PUTFILE "build/NSLOOK-debug", "NTNSLK", &32200, &32200
PUTFILE "build/HWDTEST", "NTHWD", &32200, &32200
