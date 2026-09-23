\ 1mhzwifi.asm
\ 1MHz-WiFi sideways ROM: image header, service entry and command dispatch.
\
\ Written for the 1MHz-WiFi project. This replaces the main file the ROM
\ inherited from ElkWiFi 0.23, whose own command table search was in turn
\ credited to Gerrit Hillebrand's ATOM GDOS 1.5. Neither is used here: the
\ search below walks one table entry at a time with its own structure, and the
\ service, help, banner and OSWORD paths are this project's.
\
\ The table format itself is kept, because it is what the entries are written
\ in: an entry is the command name in ASCII, then the handler address high byte
\ first. A name byte with bit 7 set cannot occur, so the high byte of an
\ address doubles as the end of name marker, and a bare address with no name
\ terminates the table because every handler lives above &8000.
\
\ Credit for the parts of this ROM that do still derive from ElkWiFi is carried
\ in *VERSION, not here.

include "machine.asm"

\ ---------------------------------------------------------------------------
\ Image headers
\ ---------------------------------------------------------------------------
\ The ATM header is a sixteen byte zero padded name followed by load address,
\ execution address and length. It precedes the ROM so the image can be loaded
\ by a development loader; the shipped image starts at romstart.

.atmheader          equs "1mhzwifi.rom",0,0,0,0
                    equw &1800
                    equw &1800
                    equw romend-romstart

.romstart           equb 0                      \ no language entry
                    equb 0
                    equb 0
                    jmp service
                    equb &82                    \ service ROM, no language
                    equb (copyright-romstart)   \ copyright offset
                    equb &30                    \ binary version
.romtitle           equs "1MHz-WiFi"
                    equb 0
.romversion         equs "0.1.67"
.copyright          equb 0
                    equs "(C)2026 Peter Clarke"
                    equb 0

\ The keyword *HELP matches on, stored reversed because the compare below walks
\ it backwards from its last character.
.commands           equs "IFIW"

\ ---------------------------------------------------------------------------
\ Service entry
\ ---------------------------------------------------------------------------
\ A is the reason code, X this ROM's slot, Y the reason argument. Anything not
\ listed is passed on with A unchanged.

.service            cmp #4                      \ unrecognised command
                    beq command
                    cmp #9                      \ *HELP
                    beq help
                    cmp #1                      \ post reset initialisation
                    bne service_not_boot
                    jmp autorun
.service_not_boot   cmp #8                      \ unrecognised OSWORD
                    bne service_not_osword
                    jmp osword65
.service_not_osword rts

\ ---------------------------------------------------------------------------
\ Command dispatch
\ ---------------------------------------------------------------------------
\ Match the command line against the table, honouring a trailing dot as an
\ abbreviation. Every BNE after an INX below stands in for a JMP: X indexes the
\ table and only returns to zero if the table passes 256 bytes, which would
\ break the single byte indexing regardless.
\
\ X indexes the table and is left on an entry's address high byte
\ when a match is found; Y indexes the command line and is left just past the
\ matched text, which is where every handler expects to start reading its
\ arguments.

\ Without a writable workspace every handler below would scribble on memory
\ this ROM does not own, so none of them may run.  Decline the service call
\ rather than raising an error: A is still 4 and nothing has been pushed, so
\ the MOS carries on offering the command to lower-priority ROMs and reports
\ "Bad command" if nobody takes it.
\
\ Raising an error here instead, which is what this did first, was wrong
\ twice over.  The test runs before the command table is searched, so it
\ answered for every unrecognised command on the machine and not just this
\ ROM's, which broke other ROMs' commands and the MOS's own.  And the error
\ was a BRK with its message inline in the bank, which the MOS cannot read
\ back once it has paged this ROM out: the screen filled with whatever the
\ incoming ROM had at those addresses, which on an Electron is BASIC's
\ keyword table.  The reason is printed once at reset instead, where OSWRCH
\ works and the text is addressable.
.command            bit ws_flag
                    bpl command_declined
IF WS_IN_IMAGE = 0
                    \ Claimed host RAM is not ours the way an image is: the
                    \ flag alone would be a single byte of uninitialised RAM
                    \ that could read back as set, so the signature autorun
                    \ stamped beside it is checked as well.
                    lda ws_signature
                    cmp #ws_signature_lo
                    bne command_declined
                    lda ws_signature+1
                    cmp #ws_signature_hi
                    bne command_declined
                    lda #4                      \ the compares clobbered A
ENDIF
                    jmp command_have_ws
.command_declined   lda #4                      \ unclaimed: pass it on
                    rts
.command_have_ws    tya                         \ A on exit belongs to the
                    pha                         \ handler, so only X and Y are
                    txa                         \ saved here
                    pha
                    cld
                    ldx #0
.cmd_entry          ldy #0
                    jsr skipspace               \ Y indexes the first non-space
                    dey                         \ the loop's iny puts it back
.cmd_step           iny
                    lda commandtable,x
                    bmi cmd_dispatch            \ name ended: full match
                    cmp (line),y
                    bne cmd_mismatch
                    inx
                    bne cmd_step

\ The character on the command line is not the one the table expects. A dot
\ there means the user abbreviated this command, so accept the entry; anything
\ else means this is a different command.
.cmd_mismatch       lda (line),y
                    cmp #'.'
                    beq cmd_abbreviated
.cmd_skip_name      lda commandtable,x
                    bmi cmd_skip_address
                    inx
                    bne cmd_skip_name
.cmd_skip_address   inx
                    inx                         \ X now starts the next entry
                    bne cmd_entry

.cmd_abbreviated    iny                         \ step over the dot
.cmd_abbrev_skip    lda commandtable,x
                    bmi cmd_dispatch
                    inx
                    bne cmd_abbrev_skip

.cmd_dispatch       sta zp+1                    \ A already holds the high byte
                    lda commandtable+1,x
                    sta zp
                    jmp (zp)

\ Reached through the table's terminating entry: no command matched.
.command_x6         pla
                    tax
                    pla
                    tay
                    lda #4
                    rts

\ ---------------------------------------------------------------------------
\ *HELP
\ ---------------------------------------------------------------------------
\ With no keyword, print the title and the keyword this ROM answers to, then
\ pass the call on so other ROMs also report. With the keyword, print the
\ command list and claim the call.

.help               tya
                    pha
                    txa
                    pha
                    lda (line),y
                    cmp #&D
                    beq help_l2
                    ldx #3                      \ compare backwards against
.help_l1            lda (line),y                \ the reversed keyword
                    cmp commands,x
                    bne help_l3
                    iny
                    dex
                    bpl help_l1
                    jsr print_help
                    jmp call_claimed
.help_l2            jsr help_version
                    jsr printtext
                    equb &D,&20,&20
                    equs "WIFI",&D,&EA
.help_l3            pla
                    tax
                    pla
                    tay
                    lda #9
                    rts

\ ---------------------------------------------------------------------------
\ Reset
\ ---------------------------------------------------------------------------
\ Answered on reason 1 rather than 3, because a higher priority ROM may claim
\ 3 before this one sees it. The MOS banner is suppressed and replaced, so the
\ machine reports one identity rather than two.

.autorun
IF WS_IN_IMAGE = 0
                    \ Service call 1 hands the first free page of absolute
                    \ workspace in Y. This image needs a fixed range, because
                    \ every workspace reference in it is an absolute address,
                    \ so it can only take that range if nothing claimed
                    \ earlier has already reached past the start of it. When
                    \ it can, it raises Y over the pages it takes; when it
                    \ cannot, it claims nothing and leaves the signature
                    \ below unwritten, so the command entry refuses rather
                    \ than writing into another ROM's workspace.
                    cpy #WS_HOST_PAGE
                    beq autorun_may_claim
                    bcc autorun_may_claim
                    clc                         \ carry clear: not ours
                    bcc autorun_claim_decided   \ always
.autorun_may_claim  ldy #ws_host_end            \ raise Y over our pages
                    sec                         \ carry set: claimed
.autorun_claim_decided
ENDIF
                    tya
                    pha
                    txa
                    pha

IF WS_IN_IMAGE = 0
                    bcc autorun_claim_done      \ nothing claimed, touch none
ENDIF
                    \ Is the image writable?  Pi1MHz loads this ROM into
                    \ sideways RAM, where the workspace above the code is
                    \ ours to use.  Burnt into a real ROM the writes would go
                    \ nowhere, and every command would read back whatever the
                    \ image holds, so record the answer once, here, and let
                    \ the command entry refuse rather than misbehave.
                    \ ws_flag is itself inside the image: in ROM it keeps its
                    \ assembled 0 however often this runs.
                    lda ws_base
                    pha                         \ do not disturb the workspace
                    lda #&A5
                    sta ws_base
                    cmp ws_base
                    bne autorun_read_only
                    lda #&5A                    \ both ways: a bus that floats
                    sta ws_base                 \ high would pass the first
                    cmp ws_base
                    bne autorun_read_only
                    lda #&80                    \ bit 7, so the command entry
                    sta ws_flag                 \ can test it with BIT/BMI
.autorun_read_only  pla
                    sta ws_base
IF WS_IN_IMAGE = 0
                    \ Claimed host RAM is not ours the way an image is: the
                    \ flag alone would be a single byte of uninitialised RAM
                    \ that could read back as set. Stamp a signature beside
                    \ it and have the command entry check both, so workspace
                    \ this image never claimed, or that another ROM has since
                    \ taken, is refused instead of used.
                    lda #ws_signature_lo
                    sta ws_signature
                    lda #ws_signature_hi
                    sta ws_signature+1
.autorun_claim_done
ENDIF

                    \ Nothing here may touch the AP5 JIM selector: the ROM scan
                    \ runs with another ROM's page possibly selected, and every
                    \ command selects its own page when it starts.
                    lda #&D7                    \ suppress the default banner
                    ldy #&7F
                    jsr osbyte
                    \ Only once the workspace is known to be ours: in a
                    \ read-only bank this store goes nowhere, and in the
                    \ EPROM build with a refused claim it would land in
                    \ another ROM's pages.
                    bit ws_flag
                    bpl autorun_no_mux
                    ldx #0
                    stx mux_status              \ no connection multiplexing yet
.autorun_no_mux

                    jsr printtext
                    equs "1MHz-WiFi 0.1.67",&EA

                    \ Say why, once, if the workspace is not there.  The
                    \ command entry only declines; without this the machine
                    \ would answer "Bad command" with no explanation.
                    bit ws_flag
                    bmi autorun_ws_ready
                    jsr printtext
                    equs " needs sideways RAM",&D,&EA
.autorun_ws_ready

                    ldy #&FF                    \ OSBYTE &FD: last reset type
                    ldx #&00
                    lda #&FD
                    jsr osbyte
                    cpx #0                      \ soft reset stays quiet
                    beq autorun_l1
                    lda #7
                    jsr oswrch
                    cpx #1
                    bne autorun_l1
.autorun_l1         jsr print_logo
                    jsr printtext
                    equb &D,&EA
                    pla
                    tax
                    pla
                    tay
                    lda #1
                    rts

\ ---------------------------------------------------------------------------
\ Command table
\ ---------------------------------------------------------------------------
\ Longer names must precede any name they begin with, so LAPOPT is listed
\ before LAP and QUPRUN before QR.

.commandtable       equs "WGET"
                    equb >pi_wget_cmd, <pi_wget_cmd
                    equs "FTP"
                    equb >ftp_cmd, <ftp_cmd
                    equs "WIFI"
                    equb >wifi_cmd, <wifi_cmd
                    equs "VERSION"
                    equb >version_cmd, <version_cmd
                    equs "LAPOPT"
                    equb >lapopt_cmd, <lapopt_cmd
                    equs "LAP"
                    equb >lap_cmd, <lap_cmd
                    equs "IFCFG"
                    equb >ifcfg_cmd, <ifcfg_cmd
                    equs "DATE"
                    equb >date_cmd, <date_cmd
                    equs "TIME"
                    equb >time_cmd, <time_cmd
                    equs "PRD"
                    equb >pdump_cmd, <pdump_cmd
                    equs "ONLINE"
                    equb >online_cmd, <online_cmd
                    equs "JOIN"
                    equb >join_cmd, <join_cmd
                    equs "LEAVE"
                    equb >leave_cmd, <leave_cmd
                    equs "PING"
                    equb >ping_cmd, <ping_cmd
                    equs "NSLOOK"
                    equb >nslook_cmd, <nslook_cmd
                    equs "RDINIT"
                    equb >rd_init_cmd, <rd_init_cmd
                    equs "RDCAT"
                    equb >rd_cat_cmd, <rd_cat_cmd
                    equs "RDLOAD"
                    equb >rd_load_cmd, <rd_load_cmd
                    equs "RDSAVE"
                    equb >rd_save_cmd, <rd_save_cmd
                    equs "RDRUN"
                    equb >rd_run_cmd, <rd_run_cmd
                    equs "MODE"
                    equb >mode_cmd, <mode_cmd
                    equs "DISCONNECT"
                    equb >disconnect_cmd, <disconnect_cmd
                    equb >command_x6, <command_x6

\ Print the ROM title and version, with the separating zero shown as a space.
.help_version       ldx #0
.help_vl1           lda romtitle,x
                    bne help_vl2
                    lda #&20
.help_vl2           jsr osasci
                    inx
                    cpx #(copyright-romtitle)
                    bne help_vl1
                    rts

\ The names come out of the command table, which already holds them: storing
\ a second copy with each description cost 200 of this block's 643 bytes, and
\ room in the bank is what decides whether a filing system can share it.  The
\ descriptions below are in TABLE order, so they stay paired with the names.
.print_help         jsr help_version
                    lda #<commandtable
                    sta help_tbl
                    lda #>commandtable
                    sta help_tbl+1
                    lda #<help_descriptions
                    sta help_txt
                    lda #>help_descriptions
                    sta help_txt+1
                    lda #&0D
                    jsr OSASCI
.phd_entry          ldy #0
                    lda (help_tbl),y
                    bmi phd_done
                    lda #' '
                    jsr OSWRCH
                    ldx #1                      \ columns used, including it
.phd_name           lda (help_tbl),y
                    bmi phd_name_done
                    jsr OSWRCH
                    iny
                    inx
                    bne phd_name
.phd_name_done      iny                         \ step over the address bytes
                    iny
                    tya
                    clc
                    adc help_tbl
                    sta help_tbl
                    bcc phd_pad
                    inc help_tbl+1
\ Line the descriptions up at column 11.  A name that already reaches it
\ gets a single space instead of none: *DISCONNECT is ten characters, which
\ with the leading space fills the column exactly, and without this its
\ description ran straight into the name as "DISCONNECTClose the connection".
.phd_pad            cpx #11
                    bcc phd_pad_one
                    lda #' '
                    jsr OSWRCH
                    bne phd_desc                \ always: A is a space
.phd_pad_one        lda #' '
                    jsr OSWRCH
                    inx
                    bne phd_pad
.phd_desc           ldy #0
.phd_dchar          lda (help_txt),y
                    jsr OSASCI
                    iny
                    cmp #&0D
                    bne phd_dchar
                    tya
                    clc
                    adc help_txt
                    sta help_txt
                    bcc phd_entry
                    inc help_txt+1
                    jmp phd_entry
.phd_done           rts
\ One line per command table entry, read in lockstep with it. A name that
\ gains an entry above without a line here shifts every description below it,
\ so the two lists are checked against each other by the build.
.help_descriptions
                    equs "Get a file from a webserver",&0D
                    equs "Interactive file transfer",&0D
                    equs "WiFi control ON|OFF|HR|SR",&0D
                    equs "Print firmware version",&0D
                    equs "Set LAP options",&0D
                    equs "List access points",&0D
                    equs "Print IP and MAC address",&0D
                    equs "Print current date",&0D
                    equs "Print current time",&0D
                    equs "Paged Ram Dump",&0D
                    equs "Show network readiness",&0D
                    equs "Join a network",&0D
                    equs "Disconnect from network",&0D
                    equs "ping a host on network",&0D
                    equs "Resolve an IPv4 address",&0D
                    equs "Clear the RAM disk",&0D
                    equs "Catalogue the RAM disk",&0D
                    equs "Load from the RAM disk",&0D
                    equs "Save to the RAM disk",&0D
                    equs "Run from the RAM disk",&0D
                    equs "Set device mode",&0D
                    equs "Close the connection",&0D
.print_help_end

\ ---------------------------------------------------------------------------
\ OSWORD &65
\ ---------------------------------------------------------------------------
\ The public driver entry, so applications can call the WiFi functions the
\ commands use. This is the ElkWiFi compatibility interface and its shape is
\ fixed by the clients that already call it: &EF holds the OSWORD number and
\ &F0/&F1 point at a block whose first three bytes are the A, X and Y the
\ driver should see. Every register may be modified.

.osword65           lda &EF
                    cmp #&65
                    beq osword65_l1
                    lda #8                      \ not ours, pass it on
                    rts
.osword65_l1        tya
                    pha
                    txa
                    pha
                    ldy #0
                    lda (&F0),y                 \ function number
                    pha
                    iny
                    lda (&F0),y
                    tax
                    iny
                    lda (&F0),y
                    tay
                    pla
                    jsr wifidriver
                    jmp call_claimed

include "util.asm"
include "errors.asm"
include "serial.asm"
include "service_driver.asm"
include "net_transport.asm"   \ after service_driver.asm, which sizes its workspace
include "driver.asm"
include "version.asm"
include "time.asm"
include "lap.asm"
include "ifcfg.asm"
include "online.asm"
include "wificmd.asm"
include "pdump.asm"
include "join.asm"
include "mode.asm"
include "wget.asm"
include "net_wget.asm"
include "ftp.asm"
include "ping.asm"
include "nslook.asm"
include "ramdisk.asm"

rom_content_end = P%
IF WS_IN_IMAGE
ASSERT rom_content_end <= ws_base

\ ---------------------------------------------------------------------------
\ Workspace, inside the image (see machine.asm)
\ ---------------------------------------------------------------------------
\ At the top of the bank, so everything below rom_content_end is free for code.
skipto ws_base
.ws_netprt          skip &20        \ netprt: timeouts, cursor, error block
.ws_writable        equb 0          \ ws_flag: set by the probe in autorun
.ws_mux_status      equb 0          \ mux_status
skipto heap
.ws_heap            skip &100       \ heap
.ws_strbuf          skip &100       \ strbuf
ELSE
\ A real ROM keeps nothing in the image: the workspace is three pages of host
\ RAM claimed at service call 1, so the whole bank below &C000 is code.
ASSERT rom_content_end <= &C000
ENDIF

skipto &C000
.romend

\ The EPROM build is a different image from the one Pi1MHz serves - it keeps
\ no workspace in the bank and claims host RAM instead - so it is saved under
\ its own name rather than overwriting the default.
IF WS_IN_IMAGE
SAVE "1mhz-wifi-atm.rom", atmheader, romend
SAVE "1mhz-wifi.rom", romstart, romend
ELSE
SAVE "1mhz-wifi-eprom.rom", romstart, romend
ENDIF
