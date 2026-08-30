\ DFS stores the top two address bits. &32000 and &32200 are expanded by MOS
\ to &FFFF2000 and &FFFF2200, keeping both stages on the I/O processor when a
\ Tube is active.

\ Public commands are small host loaders above the measured DFS workspace and
\ in writable display RAM on the MMFS/ADFS profile. They select MODE 4 before
\ asking MOS to load the non-overlapping main host image at &2200.
PUTFILE "build/NETMENUL", "NETMENU", &32000, &32000
PUTFILE "build/TELNETL", "TELNET", &32000, &32000
PUTFILE "build/SSHL", "SSH", &32000, &32000
PUTFILE "build/HWDTESTL", "HWDTEST", &32000, &32000
PUTFILE "build/SFTPL", "SFTP", &32000, &32000

\ Internal main images retain explicit host addresses when a Tube is active.
PUTFILE "build/NETMENU", "NTMENU", &32200, &32200
PUTFILE "build/TELNET", "NTTEL", &32200, &32200
PUTFILE "build/SSH", "NTSSH", &32200, &32200
PUTFILE "build/HWDTEST", "NTHWD", &32200, &32200
PUTFILE "build/SFTP", "NTSFTP", &32200, &32200
