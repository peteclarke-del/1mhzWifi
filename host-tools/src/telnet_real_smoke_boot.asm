ORG &1000
.boot_start
EQUS "*TELNET 127.0.0.1 23232", &0D
.boot_end
SAVE "build/TELNETREALBOOT", boot_start, boot_end
