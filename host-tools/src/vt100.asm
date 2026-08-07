\ Compact, bounded VT100 subset rendered through MOS VDU calls.

VT_GROUND = 0
VT_ESCAPE = 1
VT_CSI = 2
VT_OSC = 3
VT_OSC_ESCAPE = 4
VT_CHARSET = 5
VT_STRING = 6
VT_STRING_ESCAPE = 7

.vt_init
    LDA #VT_GROUND
    STA vt_state
    LDA #0
    STA vt_saved_col
    STA vt_saved_row
    STA vt_intermediate
    STA vt_margin_top
    STA vt_reply_pending
    STA vt_mode_parameter
    STA vt_mode_private
    STA vt_mode_value
    LDA #23
    STA vt_margin_bottom
    JSR vt_sgr_reset
    RTS

\ Consume one byte in A.
.vt_process
    LDX vt_state
    BNE vt_process_not_ground
    JMP vt_ground
.vt_process_not_ground
    CPX #VT_ESCAPE
    BNE vt_process_not_escape
    JMP vt_escape
.vt_process_not_escape
    CPX #VT_CSI
    BNE vt_process_not_csi
    JMP vt_csi
.vt_process_not_csi
    CPX #VT_OSC
    BNE vt_process_not_osc
    JMP vt_osc
.vt_process_not_osc
    CPX #VT_OSC_ESCAPE
    BNE vt_process_not_osc_escape
    JMP vt_osc_escape
.vt_process_not_osc_escape
    CPX #VT_CHARSET
    BNE vt_process_not_charset
    JMP vt_charset
.vt_process_not_charset
    CPX #VT_STRING
    BNE vt_process_string_escape
    JMP vt_string
.vt_process_string_escape
    JMP vt_string_escape

.vt_ground
    CMP #27
    BEQ vt_enter_escape
    CMP #127
    BEQ vt_ground_ignore
    CMP #32
    BCS vt_print
    CMP #7
    BEQ vt_print
    CMP #8
    BNE vt_ground_not_backspace
    JMP vt_backspace
.vt_ground_not_backspace
    CMP #9
    BNE vt_ground_not_tab
    JMP vt_tab
.vt_ground_not_tab
    CMP #10
    BEQ vt_print
    CMP #11
    BEQ vt_emit_lf
    CMP #12
    BEQ vt_emit_lf
    CMP #13
    BEQ vt_print
.vt_ground_ignore
    RTS
.vt_emit_lf
    LDA #10
.vt_print
    JMP OSWRCH
.vt_enter_escape
    LDA #VT_ESCAPE
    STA vt_state
    RTS

.vt_escape
    CMP #'['
    BEQ vt_enter_csi
    CMP #']'
    BNE vt_escape_not_osc
    JMP vt_enter_osc
.vt_escape_not_osc
    CMP #'7'
    BNE vt_escape_not_save
    JMP vt_save_cursor
.vt_escape_not_save
    CMP #'8'
    BNE vt_escape_not_restore
    JMP vt_restore_cursor
.vt_escape_not_restore
    CMP #'c'
    BNE vt_escape_not_reset
    JMP vt_reset_terminal
.vt_escape_not_reset
    CMP #'D'                  \ IND
    BNE vt_escape_not_index
    LDA #VT_GROUND
    STA vt_state
    LDA #10
    JMP OSWRCH
.vt_escape_not_index
    CMP #'E'                  \ NEL
    BNE vt_escape_not_next_line
    LDA #VT_GROUND
    STA vt_state
    LDA #13
    JSR OSWRCH
    LDA #10
    JMP OSWRCH
.vt_escape_not_next_line
    CMP #'M'                  \ RI (MOS clamps at the top margin)
    BNE vt_escape_not_reverse_index
    LDA #VT_GROUND
    STA vt_state
    LDA #11
    JMP OSWRCH
.vt_escape_not_reverse_index
    CMP #'('
    BEQ vt_enter_charset
    CMP #')'
    BEQ vt_enter_charset
    CMP #'*'
    BEQ vt_enter_charset
    CMP #'+'
    BEQ vt_enter_charset
    CMP #'P'                  \ DCS
    BEQ vt_enter_string
    CMP #'^'                  \ PM
    BEQ vt_enter_string
    CMP #'_'                  \ APC
    BEQ vt_enter_string
.vt_escape_unknown
    LDA #VT_GROUND
    STA vt_state
    RTS
.vt_enter_charset
    LDA #VT_CHARSET
    STA vt_state
    RTS
.vt_enter_string
    LDA #VT_STRING
    STA vt_state
    LDA #0
    STA vt_sequence_length
    RTS

.vt_enter_csi
    LDA #VT_CSI
    STA vt_state
    LDA #0
    STA vt_param1
    STA vt_param2
    STA vt_param_select
    STA vt_private
    RTS
.vt_enter_osc
    LDA #VT_OSC
    STA vt_state
    LDA #0
    STA vt_sequence_length
    RTS

.vt_csi
    CMP #'<'
    BCC vt_csi_not_private
    CMP #'?' + 1
    BCS vt_csi_not_private
    STA vt_private
    RTS
.vt_csi_not_private
    CMP #&20
    BCC vt_csi_not_intermediate
    CMP #&30
    BCS vt_csi_not_intermediate
    STA vt_intermediate       \ retain CSI intermediate; await its final byte
    RTS
.vt_csi_not_intermediate
    CMP #';'
    BNE vt_csi_not_separator
    LDA #1
    STA vt_param_select
    RTS
.vt_csi_not_separator
    CMP #'0'
    BCC vt_csi_final
    CMP #'9' + 1
    BCS vt_csi_final
    SEC
    SBC #'0'
    PHA
    LDA vt_param_select
    BNE vt_csi_digit_second
    LDA vt_param1
    JSR vt_times_ten
    STA vt_param1
    PLA
    CLC
    ADC vt_param1
    BCC vt_csi_store_first
    LDA #255
.vt_csi_store_first
    STA vt_param1
    RTS
.vt_csi_digit_second
    LDA vt_param2
    JSR vt_times_ten
    STA vt_param2
    PLA
    CLC
    ADC vt_param2
    BCC vt_csi_store_second
    LDA #255
.vt_csi_store_second
    STA vt_param2
    RTS
.vt_times_ten
    STA vt_math
    ASL A
    BCS vt_math_overflow
    ASL A
    BCS vt_math_overflow
    CLC
    ADC vt_math
    BCS vt_math_overflow
    ASL A
    BCS vt_math_overflow
    RTS
.vt_math_overflow
    LDA #255
    RTS

.vt_csi_final
    PHA
    LDA #VT_GROUND
    STA vt_state
    PLA
    CMP #'A'
    BNE vt_csi_not_up
    JMP vt_cursor_up
.vt_csi_not_up
    CMP #'B'
    BNE vt_csi_not_down
    JMP vt_cursor_down
.vt_csi_not_down
    CMP #'C'
    BNE vt_csi_not_right
    JMP vt_cursor_right
.vt_csi_not_right
    CMP #'D'
    BNE vt_csi_not_left
    JMP vt_cursor_left
.vt_csi_not_left
    CMP #'E'
    BNE vt_csi_not_next_line
    JMP vt_cursor_next_line
.vt_csi_not_next_line
    CMP #'F'
    BNE vt_csi_not_previous_line
    JMP vt_cursor_previous_line
.vt_csi_not_previous_line
    CMP #'G'
    BNE vt_csi_not_column
    JMP vt_cursor_column
.vt_csi_not_column
    CMP #'H'
    BNE vt_csi_not_home
    JMP vt_cursor_position
.vt_csi_not_home
    CMP #'f'
    BNE vt_csi_not_position
    JMP vt_cursor_position
.vt_csi_not_position
    CMP #'d'
    BNE vt_csi_not_row
    JMP vt_cursor_absolute_row
.vt_csi_not_row
    CMP #'J'
    BNE vt_csi_not_ed
    JMP vt_erase_display
.vt_csi_not_ed
    CMP #'K'
    BNE vt_csi_not_el
    JMP vt_erase_line
.vt_csi_not_el
    CMP #'@'
    BNE vt_csi_not_ich
    JMP vt_insert_characters
.vt_csi_not_ich
    CMP #'L'
    BNE vt_csi_not_il
    JMP vt_insert_lines
.vt_csi_not_il
    CMP #'M'
    BNE vt_csi_not_dl
    JMP vt_delete_lines
.vt_csi_not_dl
    CMP #'P'
    BNE vt_csi_not_dch
    JMP vt_delete_characters
.vt_csi_not_dch
    CMP #'X'
    BNE vt_csi_not_ech
    JMP vt_erase_characters
.vt_csi_not_ech
    CMP #'S'
    BNE vt_csi_not_su
    JMP vt_scroll_up
.vt_csi_not_su
    CMP #'T'
    BNE vt_csi_not_sd
    JMP vt_scroll_down
.vt_csi_not_sd
    CMP #'m'
    BNE vt_csi_not_sgr
    JMP vt_sgr
.vt_csi_not_sgr
    CMP #'h'
    BNE vt_csi_not_set_mode
    JMP vt_set_mode
.vt_csi_not_set_mode
    CMP #'l'
    BNE vt_csi_not_reset_mode
    JMP vt_reset_mode
.vt_csi_not_reset_mode
    CMP #'r'
    BNE vt_csi_not_margins
    JMP vt_set_margins
.vt_csi_not_margins
    CMP #'n'
    BNE vt_csi_not_status_report
    JMP vt_status_report
.vt_csi_not_status_report
    CMP #'c'
    BNE vt_csi_not_device_attributes
    JMP vt_device_attributes
.vt_csi_not_device_attributes
    CMP #'g'
    BNE vt_csi_not_tab_clear
    JMP vt_tab_clear
.vt_csi_not_tab_clear
    CMP #'s'
    BNE vt_csi_not_save
    JMP vt_save_cursor
.vt_csi_not_save
    CMP #'u'
    BNE vt_csi_unknown
    JMP vt_restore_cursor
.vt_csi_unknown
    RTS

\ Scaffolding for the remaining screen-editing commands. These entry points
\ have no rendering effect yet; keeping them distinct makes the
\ later screen-memory renderer and its tests incremental rather than another
\ parser rewrite.
.vt_insert_characters             \ CSI Ps @ (ICH)
    JMP vt_editing_not_implemented
.vt_insert_lines                  \ CSI Ps L (IL)
    JMP vt_editing_not_implemented
.vt_delete_lines                  \ CSI Ps M (DL)
    JMP vt_editing_not_implemented
.vt_delete_characters             \ CSI Ps P (DCH)
    JMP vt_editing_not_implemented
.vt_erase_characters              \ CSI Ps X (ECH)
    JMP vt_editing_not_implemented
.vt_scroll_up                     \ CSI Ps S (SU)
    JMP vt_editing_not_implemented
.vt_scroll_down                   \ CSI Ps T (SD)
.vt_editing_not_implemented
    RTS

\ Mode/report scaffolding. Replies need a small renderer-to-transport queue;
\ the parser records the request now so SSH and TERM can add that queue later.
.vt_set_mode                      \ CSI [ ? ] Ps h (SM/DECSET)
    LDA #1
    BNE vt_record_mode
.vt_reset_mode                    \ CSI [ ? ] Ps l (RM/DECRST)
    LDA #0
.vt_record_mode
    STA vt_mode_value
    LDA vt_param1
    STA vt_mode_parameter
    LDA vt_private
    STA vt_mode_private
    RTS
.vt_set_margins                   \ CSI Pt ; Pb r (DECSTBM)
    LDA vt_param1
    BEQ vt_set_margins_default_top
    SEC
    SBC #1
    BPL vt_set_margins_store_top
.vt_set_margins_default_top
    LDA #0
.vt_set_margins_store_top
    STA vt_margin_top
    LDA vt_param2
    BEQ vt_set_margins_default_bottom
    SEC
    SBC #1
    CMP #24
    BCC vt_set_margins_store_bottom
.vt_set_margins_default_bottom
    LDA #23
.vt_set_margins_store_bottom
    STA vt_margin_bottom
    RTS
.vt_status_report                 \ CSI Ps n (DSR/CPR)
    LDA #1
    STA vt_reply_pending
    RTS
.vt_device_attributes             \ CSI [ > ] Ps c (DA)
    LDA #2
    STA vt_reply_pending
    RTS
.vt_tab_clear                     \ CSI Ps g (TBC)
    RTS

.vt_default_one
    LDA vt_param1
    BNE vt_default_one_done
    LDA #1
.vt_default_one_done
    TAX
    RTS
.vt_cursor_up
    JSR vt_default_one
    STX vt_move_count
    JSR vt_get_cursor
    LDA vt_cursor_row
    SEC
    SBC vt_move_count
    BCS vt_cursor_vertical_set
    LDA #0
    BEQ vt_cursor_vertical_set
.vt_cursor_down
    JSR vt_default_one
    STX vt_move_count
    JSR vt_get_cursor
    LDA vt_cursor_row
    CLC
    ADC vt_move_count
    BCS vt_cursor_down_limit
    CMP #24
    BCC vt_cursor_vertical_set
.vt_cursor_down_limit
    LDA #23
.vt_cursor_vertical_set
    PHA
    LDA #31
    JSR OSWRCH
    LDA vt_cursor_col
    JSR OSWRCH
    PLA
    JMP OSWRCH
.vt_cursor_right
    JSR vt_default_one
    STX vt_move_count
    JSR vt_get_cursor
    LDA vt_cursor_col
    CLC
    ADC vt_move_count
    BCS vt_cursor_right_limit
    CMP #40
    BCC vt_cursor_horizontal_set
.vt_cursor_right_limit
    LDA #39
    BNE vt_cursor_horizontal_set
.vt_cursor_left
    JSR vt_default_one
    STX vt_move_count
    JSR vt_get_cursor
    LDA vt_cursor_col
    SEC
    SBC vt_move_count
    BCS vt_cursor_horizontal_set
    LDA #0
.vt_cursor_horizontal_set
    PHA
    LDA #31
    JSR OSWRCH
    PLA
    JSR OSWRCH
    LDA vt_cursor_row
    JMP OSWRCH

.vt_cursor_position
    LDA vt_param1
    BNE vt_cursor_row_set
    LDA #1
.vt_cursor_row_set
    SEC
    SBC #1
    CMP #24
    BCC vt_cursor_row_ok
    LDA #23
.vt_cursor_row_ok
    PHA
    LDA vt_param2
    BNE vt_cursor_col_set
    LDA #1
.vt_cursor_col_set
    SEC
    SBC #1
    CMP #40
    BCC vt_cursor_col_ok
    LDA #39
.vt_cursor_col_ok
    TAX
    LDA #31
    JSR OSWRCH
    TXA
    JSR OSWRCH
    PLA
    JMP OSWRCH

.vt_erase_display
    JSR vt_get_cursor
    LDA vt_cursor_col
    STA vt_display_saved_col
    LDA vt_cursor_row
    STA vt_display_saved_row
    LDA vt_param1
    CMP #2
    BEQ vt_erase_display_all
    CMP #3                    \ xterm ED3 also clears scrollback; none exists here
    BEQ vt_erase_display_all
    CMP #1
    BEQ vt_erase_display_before
    \ ED0: erase from the cursor through the end of the display.
    LDA vt_display_saved_col
    ORA vt_display_saved_row
    BEQ vt_erase_display_all
    LDA #0
    STA vt_param1
    JSR vt_erase_line
    LDA vt_display_saved_row
    CLC
    ADC #1
    STA vt_erase_row
.vt_erase_display_after_loop
    LDA vt_erase_row
    CMP #24
    BCS vt_restore_display_cursor
    JSR vt_clear_whole_row
    INC vt_erase_row
    BNE vt_erase_display_after_loop
.vt_erase_display_before
    LDA #0
    STA vt_erase_row
.vt_erase_display_before_loop
    LDA vt_erase_row
    CMP vt_display_saved_row
    BCS vt_erase_display_before_current
    JSR vt_clear_whole_row
    INC vt_erase_row
    BNE vt_erase_display_before_loop
.vt_erase_display_before_current
    JSR vt_restore_display_cursor
    LDA #1
    STA vt_param1
    JMP vt_erase_line
.vt_erase_display_all
    LDA #12
    JSR OSWRCH
.vt_restore_display_cursor
    LDA #31
    JSR OSWRCH
    LDA vt_display_saved_col
    JSR OSWRCH
    LDA vt_display_saved_row
    JMP OSWRCH

\ Clear the complete row in A. The caller retains the original cursor separately.
.vt_clear_whole_row
    PHA
    LDA #31
    JSR OSWRCH
    LDA #0
    JSR OSWRCH
    PLA
    JSR OSWRCH
    LDA #40
    STA vt_erase_count
.vt_clear_whole_row_spaces
    LDA #' '
    JSR OSWRCH
    DEC vt_erase_count
    BNE vt_clear_whole_row_spaces
    RTS

\ Erase in line, preserving the cursor as required by ANSI/VT100.  EL0 erases
\ from the cursor, EL1 through the cursor, and EL2 the entire line.
.vt_erase_line
    JSR vt_get_cursor
    LDA vt_param1
    CMP #1
    BEQ vt_erase_line_before
    CMP #2
    BEQ vt_erase_line_all
    LDA vt_cursor_col
    STA vt_erase_start_col
    LDA #40
    SEC
    SBC vt_cursor_col
    STA vt_erase_count
    BNE vt_erase_line_run
.vt_erase_line_before
    LDA #0
    STA vt_erase_start_col
    LDA vt_cursor_col
    CLC
    ADC #1
    STA vt_erase_count
    BNE vt_erase_line_run
.vt_erase_line_all
    LDA #0
    STA vt_erase_start_col
    LDA #40
    STA vt_erase_count
.vt_erase_line_run
    LDA #31
    JSR OSWRCH
    LDA vt_erase_start_col
    JSR OSWRCH
    LDA vt_cursor_row
    JSR OSWRCH
.vt_erase_line_spaces
    LDA #' '
    JSR OSWRCH
    DEC vt_erase_count
    BNE vt_erase_line_spaces
    LDA #31
    JSR OSWRCH
    LDA vt_cursor_col
    JSR OSWRCH
    LDA vt_cursor_row
    JMP OSWRCH

.vt_cursor_next_line
    JSR vt_default_one
    STX vt_move_count
    JSR vt_get_cursor
    LDA vt_cursor_row
    CLC
    ADC vt_move_count
    BCS vt_cursor_next_line_limit
    CMP #24
    BCC vt_cursor_line_set
.vt_cursor_next_line_limit
    LDA #23
    BNE vt_cursor_line_set
.vt_cursor_previous_line
    JSR vt_default_one
    STX vt_move_count
    JSR vt_get_cursor
    LDA vt_cursor_row
    SEC
    SBC vt_move_count
    BCS vt_cursor_line_set
    LDA #0
.vt_cursor_line_set
    PHA
    LDA #31
    JSR OSWRCH
    LDA #0
    JSR OSWRCH
    PLA
    JMP OSWRCH
.vt_cursor_column
    JSR vt_get_cursor
    LDA vt_param1
    BNE vt_cursor_column_set
    LDA #1
.vt_cursor_column_set
    SEC
    SBC #1
    CMP #40
    BCC vt_cursor_column_ok
    LDA #39
.vt_cursor_column_ok
    TAX
    LDA #31
    JSR OSWRCH
    TXA
    JSR OSWRCH
    LDA vt_cursor_row
    JMP OSWRCH
.vt_cursor_absolute_row
    JSR vt_get_cursor
    LDA vt_param1
    BNE vt_cursor_absolute_row_set
    LDA #1
.vt_cursor_absolute_row_set
    SEC
    SBC #1
    CMP #24
    BCC vt_cursor_absolute_row_ok
    LDA #23
.vt_cursor_absolute_row_ok
    PHA
    LDA #31
    JSR OSWRCH
    LDA vt_cursor_col
    JSR OSWRCH
    PLA
    JMP OSWRCH

.vt_backspace
    JSR vt_get_cursor
    LDA vt_cursor_col
    BEQ vt_backspace_done
    DEC vt_cursor_col
    JSR vt_position_saved_cursor
.vt_backspace_done
    RTS
.vt_tab
    JSR vt_get_cursor
    LDA vt_cursor_col
    ORA #7
    CLC
    ADC #1
    CMP #40
    BCC vt_tab_set
    LDA #39
.vt_tab_set
    STA vt_cursor_col
.vt_position_saved_cursor
    LDA #31
    JSR OSWRCH
    LDA vt_cursor_col
    JSR OSWRCH
    LDA vt_cursor_row
    JMP OSWRCH

.vt_sgr
    LDA vt_param1
    JSR vt_sgr_one
    LDA vt_param_select
    BEQ vt_sgr_done
    LDA vt_param2
    JSR vt_sgr_one
.vt_sgr_done
    RTS
.vt_sgr_one
    CMP #0
    BEQ vt_sgr_reset
    CMP #7
    BEQ vt_sgr_inverse
    RTS
.vt_sgr_reset
    LDA #17
    JSR OSWRCH
    LDA #1
    JSR OSWRCH
    LDA #17
    JSR OSWRCH
    LDA #128
    JMP OSWRCH
.vt_sgr_inverse
    LDA #17
    JSR OSWRCH
    LDA #0
    JSR OSWRCH
    LDA #17
    JSR OSWRCH
    LDA #129
    JMP OSWRCH

.vt_get_cursor
    LDA #&86
    JSR OSBYTE
    STX vt_cursor_col
    STY vt_cursor_row
    RTS
.vt_save_cursor
    LDA #VT_GROUND
    STA vt_state
    JSR vt_get_cursor
    LDA vt_cursor_col
    STA vt_saved_col
    LDA vt_cursor_row
    STA vt_saved_row
    RTS
.vt_restore_cursor
    LDA #VT_GROUND
    STA vt_state
    LDA #31
    JSR OSWRCH
    LDA vt_saved_col
    JSR OSWRCH
    LDA vt_saved_row
    JMP OSWRCH
.vt_reset_terminal
    LDA #VT_GROUND
    STA vt_state
    LDA #12
    JSR OSWRCH
    JMP vt_sgr_reset

.vt_osc
    CMP #7
    BEQ vt_osc_done
    CMP #27
    BEQ vt_osc_saw_escape
    INC vt_sequence_length
    BNE vt_osc_check_limit
.vt_osc_done
    LDA #VT_GROUND
    STA vt_state
    RTS
.vt_osc_check_limit
    LDA vt_sequence_length
    CMP #128
    BCS vt_osc_done
    RTS
.vt_osc_saw_escape
    LDA #VT_OSC_ESCAPE
    STA vt_state
    RTS
.vt_osc_escape
    CMP #92                  \ backslash terminates OSC after ESC
    BEQ vt_osc_done
    LDA #VT_OSC
    STA vt_state
    RTS

\ Character-set designation affects glyph mapping only. The BBC/Electron font
\ remains ASCII, but consuming the designator prevents ESC(B leaking a 'B'.
.vt_charset
    LDA #VT_GROUND
    STA vt_state
    RTS

\ Safely discard unsupported DCS/PM/APC control strings through ST (ESC \).
.vt_string
    CMP #27
    BEQ vt_string_saw_escape
    INC vt_sequence_length
    BNE vt_string_check_limit
.vt_string_done
    LDA #VT_GROUND
    STA vt_state
    RTS
.vt_string_check_limit
    LDA vt_sequence_length
    CMP #128
    BCS vt_string_done
    RTS
.vt_string_saw_escape
    LDA #VT_STRING_ESCAPE
    STA vt_state
    RTS
.vt_string_escape
    CMP #92
    BEQ vt_string_done
    LDA #VT_STRING
    STA vt_state
    RTS

.vt_state
    EQUB 0
.vt_param1
    EQUB 0
.vt_param2
    EQUB 0
.vt_param_select
    EQUB 0
.vt_private
    EQUB 0
.vt_intermediate
    EQUB 0
.vt_sequence_length
    EQUB 0
.vt_math
    EQUB 0
.vt_cursor_col
    EQUB 0
.vt_cursor_row
    EQUB 0
.vt_saved_col
    EQUB 0
.vt_saved_row
    EQUB 0
.vt_erase_start_col
    EQUB 0
.vt_erase_count
    EQUB 0
.vt_move_count
    EQUB 0
.vt_display_saved_col
    EQUB 0
.vt_display_saved_row
    EQUB 0
.vt_erase_row
    EQUB 0
.vt_margin_top
    EQUB 0
.vt_margin_bottom
    EQUB 23
.vt_mode_parameter
    EQUB 0
.vt_mode_private
    EQUB 0
.vt_mode_value
    EQUB 0
.vt_reply_pending
    EQUB 0
