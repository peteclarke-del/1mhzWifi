\ 1mhzwicfs.asm
\ 1MHz-WiCFS: the UEF cassette filing system, as a sideways ROM of its own.
\
\ This is the second of the two images the project builds. It exists because
\ wicfs.asm is the only file left that derives from somebody else's work, from
\ ElkWiFi 0.23 and through it from Martin Barr's UPCFS, and neither author has
\ stated any licence terms. Keeping it in its own ROM means the 1MHz-WiFi image
\ is entirely ours and can be licensed, published or offered upstream on its
\ own, while this one can be withheld, or shipped as patches rather than as a
\ binary, until that is settled.
\
\ The two ROMs do not call each other. What passes between them is data in the
\ JIM window: *WGET -U downloads a normalised UEF image there and records its
\ length and cursor in the four bytes machine.asm documents as the contract,
\ and this ROM streams the image out of the same window. Either ROM works with
\ the other absent, so a machine can be fitted with one, the other or both.
\
\ Pi1MHz serves sideways ROMs from its own directory, so this costs no physical
\ ROM socket on any of the four target machines.

include "machine.asm"

\ ---------------------------------------------------------------------------
\ Image headers
\ ---------------------------------------------------------------------------

.atmheader          equs "1mhzwicfs.rom",0,0,0
                    equw &1800
                    equw &1800
                    equw romend-romstart

.romstart           equb 0
                    equb 0
                    equb 0
                    jmp service
                    equb &82                    \ service ROM, no language
                    equb (copyright-romstart)
                    equb &30
.romtitle           equs "1MHz-WiCFS"
                    equb 0
.romversion         equs "0.1.67"
.copyright          equb 0
                    equs "(C)2026 Peter Clarke"
                    equb 0

\ The keyword *HELP matches on, stored reversed.
.commands           equs "SFCIW"

\ ---------------------------------------------------------------------------
\ Service entry
\ ---------------------------------------------------------------------------
\ Reason 1 is answered so the filing system can release its vectors after a
\ reset. This ROM does not claim OSWORD &65: that is the network ROM's
\ interface and only one image may answer it.

.service            cmp #4
                    beq command
                    cmp #9
                    beq help
                    cmp #1
                    bne service_done
                    jmp autorun
.service_done       rts

\ ---------------------------------------------------------------------------
\ Command dispatch
\ ---------------------------------------------------------------------------
\ Identical in shape to the network ROM's: an entry is the command name in
\ ASCII followed by the handler address, high byte first, and a bare address
\ with no name terminates the table. Every BNE after an INX stands in for a
\ JMP, since X only returns to zero if the table passes 256 bytes.

.command            tya
                    pha
                    txa
                    pha
                    cld
                    ldx #0
.cmd_entry          ldy #0
                    jsr skipspace
                    dey
.cmd_step           iny
                    lda commandtable,x
                    bmi cmd_dispatch
                    cmp (line),y
                    bne cmd_mismatch
                    inx
                    bne cmd_step

.cmd_mismatch       lda (line),y
                    cmp #'.'
                    beq cmd_abbreviated
.cmd_skip_name      lda commandtable,x
                    bmi cmd_skip_address
                    inx
                    bne cmd_skip_name
.cmd_skip_address   inx
                    inx
                    bne cmd_entry

.cmd_abbreviated    iny
.cmd_abbrev_skip    lda commandtable,x
                    bmi cmd_dispatch
                    inx
                    bne cmd_abbrev_skip

.cmd_dispatch       sta zp+1
                    lda commandtable+1,x
                    sta zp
                    jmp (zp)

.command_x6         pla
                    tax
                    pla
                    tay
                    lda #4
                    rts

\ ---------------------------------------------------------------------------
\ *HELP
\ ---------------------------------------------------------------------------

.help               tya
                    pha
                    txa
                    pha
                    lda (line),y
                    cmp #&D
                    beq help_l2
                    ldx #4
.help_l1            lda (line),y
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
                    equs "WICFS",&D,&EA
.help_l3            pla
                    tax
                    pla
                    tay
                    lda #9
                    rts

\ ---------------------------------------------------------------------------
\ Reset
\ ---------------------------------------------------------------------------
\ The MOS rebuilds the standard and extended vectors before this call, so
\ persisted state is only meaningful if BYTEV still proves the RAM cassette
\ trap survived. Read it only then, and release only the entries this ROM
\ owns. This moved here with the filing system: the network ROM used to reach
\ into it, and no longer needs to know the filing system exists.

.autorun            tya
                    pha
                    txa
                    pha
                    lda BYTEV
                    cmp #<notape
                    bne autorun_released
                    lda BYTEV+1
                    cmp #>notape
                    bne autorun_released
                    jsr release_owned_wicfs
                    bcs autorun_abort
.autorun_released   pla
                    tax
                    pla
                    tay
                    lda #1
                    rts

\ Release failed. Leave the vectors alone rather than resetting into an
\ inconsistent filing system.
.autorun_abort      pla
                    tax
                    pla
                    tay
                    lda #1
                    rts

\ ---------------------------------------------------------------------------
\ Command table
\ ---------------------------------------------------------------------------
\ Longer names must precede any name they begin with, so QUPRUN is listed
\ before QR and QUPCFS before neither, being distinct.

.commandtable       equs "QUPRUN"
                    equb >uef_run_cmd, <uef_run_cmd
                    equs "QR"
                    equb >uef_run_cmd, <uef_run_cmd
                    equs "QAUTO"
                    equb >uef_auto_cmd, <uef_auto_cmd
                    equs "QHOST"
                    equb >host_basic_cmd, <host_basic_cmd
                    equs "QUPCFS"
                    equb >bUPCFS, <bUPCFS
                    equs "UEF"
                    equb >uef_cmd, <uef_cmd
                    equs "WICFS"
                    equb >wicfs_cmd, <wicfs_cmd
                    equs "REWIND"
                    equb >rewind_cmd, <rewind_cmd
                    equb >command_x6, <command_x6

.help_version       ldx #0
.help_vl1           lda romtitle,x
                    bne help_vl2
                    lda #&20
.help_vl2           jsr osasci
                    inx
                    cpx #(copyright-romtitle)
                    bne help_vl1
                    rts

.print_help         jsr help_version
                    jsr printtext
                    equb &0D
                    equs " UEF       Load local UEF file",&0D
                    equs " WICFS     Enable WiFi CFS",&0D
                    equs " REWIND    Rewind the UEF stream",&0D
                    equb &EA
.print_help_end     rts

include "util.asm"
include "errors.asm"
include "wicfs_errors.asm"   \ appends to the table errors.asm starts
include "serial.asm"
include "service_driver.asm"
include "net_transport.asm"   \ after service_driver.asm, which sizes its workspace
include "driver.asm"
include "wicfs.asm"
include "wicfs_messages.asm"   \ after wicfs.asm, which defines cr
include "wicfs_catalogue.asm"
include "uef.asm"
include "host_launch.asm"

rom_content_end = P%
ASSERT rom_content_end <= &BF00

skipto &C000
.romend

SAVE "1mhz-wicfs-atm.rom", atmheader, romend
SAVE "1mhz-wicfs.rom", romstart, romend
