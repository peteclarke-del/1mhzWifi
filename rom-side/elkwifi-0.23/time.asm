\ Pi1MHz-backed DATE/TIME.  Command 89 obtains UTC from NTP cooperatively;
\ no external HTTP endpoint or downloadable parser is involved.

.time_cmd
 lda #30
 jmp generic_cmd

.date_cmd
 lda #29
 jmp generic_cmd
