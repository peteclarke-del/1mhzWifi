\ wicfs_messages.asm
\ 1MHz-WiFi ROM: the filing system's status and error messages.
\
\ Written for the 1MHz-WiFi project. These replace the message table the ROM
\ inherited, which was the most clearly copyrightable material left in
\ wicfs.asm: thirteen lines of somebody else's prose. The wording here is ours;
\ the table shape is not expression but arithmetic, because xmess indexes it by
\ shifting the message number left four times.
\
\ Every entry is therefore exactly sixteen bytes: fifteen characters and the
\ carriage return that both ends the line and stops the print loop. The strings
\ are padded to that width rather than terminated early, so keep them fifteen
\ characters long when editing.

wicfs_message_width = 16

.txt0               equs "1MHz-WiFi CFS  ",&0D
.txt1               equs "Ver 0.1.67     ",&0D
.txt2               equs "Compressed file",&0D
.txt3               equs "File not found ",&0D
.txt4               equs "No file open   ",&0D
.txt5               equs "Bad UEF header ",&0D
.txt6               equs "Block sequence ",&0D
.txt7               equs "Unknown chunk  ",&0D
.txt8               equs "Stream ended   ",&0D
.txt9               equs "End of tape    ",&0D
.txt10              equs "Searching      ",&0D
.txt11              equs "Loading        ",&0D
.txt12              equs "Cannot write   ",&0D

\ Message 13 is reported when OSFILE is asked to open a file that is already
\ open. The inherited table stopped at twelve while the code still asked for
\ thirteen, so that path indexed one entry past the end and printed whatever
\ followed the table until it met a carriage return. ElkWiFi 0.23 has the same
\ defect. Defining the entry is the fix.
.txt13              equs "File already op",&0D

\ Print message number A. Exits with Z set, because the loop ends on the
\ carriage return compare, and several callers branch on that.
\ A and X are not preserved.

.xmess              asl a                   \ sixteen bytes per entry
                    asl a
                    asl a
                    asl a
                    tax
.xmess_a1           lda txt0,x
                    pha                     \ OSASCI may alter A, and the byte
                    jsr OSASCI              \ is also the end of line test
                    pla
                    inx
                    cmp #cr
                    bne xmess_a1
                    rts
