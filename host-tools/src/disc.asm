\ DFS stores the top two address bits. &31900 is expanded by MOS to
\ &FFFF1900: with a Tube active the filing system keeps these programs on the
\ I/O processor. Without a Tube they execute at the 16-bit address normally.

PUTFILE "build/NETMENU", "NETMENU", &31900, &31900
PUTFILE "build/TERM", "TERM", &31900, &31900
PUTFILE "build/SSH", "SSH", &31900, &31900
PUTFILE "build/PING", "PING", &31900, &31900
PUTFILE "build/NSLOOK", "NSLOOK", &31900, &31900
PUTFILE "build/FTP", "FTP", &31900, &31900
PUTFILE "build/HGET", "HGET", &31900, &31900
PUTFILE "build/VIEWDAT", "VIEWDAT", &31900, &31900
