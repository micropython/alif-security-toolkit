#!/usr/bin/python3
"""
trace buffer decoder (SEROM and SERAM)

  __author__ = "ronyett"
  __copyright__ = "ALIF Seminconductor"
  __version__ = "0.03.016" # Reset cumulative time for SERAM_RESET_HANDLER
  __status__ = "Dev"
"""
#!/usr/bin/env python3
# pylint: disable=invalid-name,superfluous-parens,anomalous-unicode-escape-in-string, too-many-locals, too-many-statements, too-many-branches, line-too-long, too-many-arguments

# Import definitions from trace_definitions.py
from trace_definitions import *

# --- Debug Configuration ---
DEBUG_PRINT_ENABLE = False  # Set to True to enable detailed debug prints

TRACE_BASE_ADDRESS = 0
# NUMBER_OF_TRACES represents the maximum design capacity of the hardware trace buffer (in words).
# The actual size of the trace data in a dump might be different and is determined dynamically.
NUMBER_OF_TRACES = (
    472  # Or 512; SERAM Size = 0x200, 512 Words, 2K bytes (this is WORD capacity)
)

# Trace field encoding data
FLAG_MASK_SHIFT = 0
SEQ_ID_MASK_SHIFT = 2
MARKER_MASK_SHIFT = 8
ADDR_MASK_SHIFT = 16

FLAG_MASK = 0x00000003
SEQ_ID_MASK = 0x000000FC
MARKER_MASK = 0x0000FF00
ADDR_MASK = 0xFFFF0000
VOID_ENTRY = 0xFFFFFFFF

TRACE_FLAG_NO_DATA = 0x00  # No data
TRACE_FLAG_BYTE_DATA = 0x01  # Marker is 8 bit data
TRACE_FLAG_WORD_DATA = 0x02  # Next entry is 32-bit data
TRACE_FLAG_TIMESTAMP = 0x03  # Next entry is 32 bit TimeStamp

TRACE_BUFFER_END_MARKER = 0xEEEEEEEE


def readMemory32(address_bytes, offset):
    """
    return an integer from byte list provided
    """
    if offset + 3 >= len(address_bytes):
        raise IndexError(
            f"readMemory32: offset {offset} is out of bounds for buffer of length {len(address_bytes)}"
        )
    return int.from_bytes(address_bytes[offset : offset + 4], "little")


def trace_find_end_marker(end_marker_value, trace_buffer):
    """
    look for the Trace end marker in the trace buffer
    """
    marker_found = False
    position = 0
    # Iterate forwards to find the first occurrence of the end marker.
    for each_trace_item_offset in range(0, len(trace_buffer) - 3, 4):
        if (
            len(trace_buffer) >= each_trace_item_offset + 4
        ):  # Ensure there's enough data for a full word
            trace_word = readMemory32(trace_buffer, each_trace_item_offset)
            if trace_word == end_marker_value:
                marker_found = True
                position = each_trace_item_offset
                break
    return marker_found, position


def _count_markers_in_trace_section(
    buffer_bytes,
    section_base_offset,
    section_size_bytes,
    flag_m,
    flag_s,
    flag_wd,
    flag_ts,
    void_val,
):
    """
    Counts the number of logical trace markers within a given section of the buffer.
    Accounts for 1-word and 2-word entries.
    The section_size_bytes defines the extent of the scan.
    It also handles the edge case where the first physical slot is data for the last physical marker.
    """
    marker_count = 0
    current_offset_in_section = 0  # Relative to section_base_offset

    is_first_physical_slot_a_wrapped_payload = False
    if section_size_bytes >= 4:
        last_physical_marker_slot_offset_in_section = section_size_bytes - 4
        last_physical_marker_absolute_offset = (
            section_base_offset + last_physical_marker_slot_offset_in_section
        )

        if last_physical_marker_absolute_offset + 3 < len(buffer_bytes):
            last_marker_item = readMemory32(
                buffer_bytes, last_physical_marker_absolute_offset
            )
            if last_marker_item != void_val:
                last_marker_flag_val = (last_marker_item & flag_m) >> flag_s
                if last_marker_flag_val == flag_wd or last_marker_flag_val == flag_ts:
                    is_first_physical_slot_a_wrapped_payload = True

    while current_offset_in_section < section_size_bytes:
        actual_buffer_offset = section_base_offset + current_offset_in_section

        if (actual_buffer_offset + 3) >= (section_base_offset + section_size_bytes):
            break
        if (actual_buffer_offset + 3) >= len(buffer_bytes):
            break

        if is_first_physical_slot_a_wrapped_payload and current_offset_in_section == 0:
            current_offset_in_section += 4
            is_first_physical_slot_a_wrapped_payload = False
            continue

        trace_item = readMemory32(buffer_bytes, actual_buffer_offset)
        marker_count += 1
        current_offset_in_section += 4

        if trace_item == void_val:
            continue

        flag_val = (trace_item & flag_m) >> flag_s
        if flag_val == flag_wd or flag_val == flag_ts:
            if current_offset_in_section < section_size_bytes:
                current_offset_in_section += 4
            else:
                pass

    return marker_count


def trace_buffer_decode(trace_buffer, seram_flag):
    """
    trace_buffer_decode
    """
    if seram_flag:
        print("*** SERAM Trace Buffer decode ***")
    else:
        print("*** SEROM Trace Buffer decode ***")

    marker_found, end_of_trace_offset = trace_find_end_marker(
        TRACE_BUFFER_END_MARKER, trace_buffer
    )
    if not marker_found:
        print("[ERROR] No end of trace marker was found in the provided buffer.")
        return

    first_header_word_address = end_of_trace_offset - 4

    if first_header_word_address < 0:
        print("[ERROR] Trace buffer structure invalid: header address is negative.")
        return
    if first_header_word_address + 3 >= len(trace_buffer):
        print(
            f"[ERROR] Trace buffer too small to read first header word at 0x{first_header_word_address:08x}."
        )
        return

    trace_vars_p = readMemory32(trace_buffer, first_header_word_address)
    print("*** Trace Header ***")
    print(f"[0x{first_header_word_address:08x}] Raw trace_vars_p: 0x{trace_vars_p:08x}")

    rollover_flag = (trace_vars_p >> 24) & 0xFF
    num_entries_in_current_pass = (trace_vars_p >> 16) & 0xFF
    write_index_words = (trace_vars_p >> 8) & 0xFF

    if rollover_flag == 1:
        print("Rollover detected")
    else:
        print("No rollover detected")

    if DEBUG_PRINT_ENABLE:
        print(
            f"Decoded Num Entries in Current Pass (from header byte 2): {num_entries_in_current_pass}"
        )
        print(
            f"Decoded Write Index (from header byte 1, 0-indexed word): {write_index_words}"
        )

    end_marker_val_from_buffer = readMemory32(trace_buffer, end_of_trace_offset)
    print(
        f"[0x{end_of_trace_offset:08x}] 0x{end_marker_val_from_buffer:08x} (End Marker)"
    )

    trace_data_section_start_offset = TRACE_BASE_ADDRESS
    effective_circular_buffer_size_bytes = (
        first_header_word_address - trace_data_section_start_offset
    )

    if effective_circular_buffer_size_bytes <= 0:
        print(
            f"[ERROR] Invalid trace data section size: {effective_circular_buffer_size_bytes} bytes. Header is at or before data start."
        )
        return
    if effective_circular_buffer_size_bytes % 4 != 0:
        print(
            f"[WARNING] Effective circular buffer size ({effective_circular_buffer_size_bytes} bytes) is not a multiple of 4. This may indicate a malformed buffer or incorrect header position."
        )

    if DEBUG_PRINT_ENABLE:
        print(
            f"Effective circular buffer size for this dump: {effective_circular_buffer_size_bytes} bytes ({effective_circular_buffer_size_bytes // 4} words)"
        )

    trace_total = 0
    initial_word_offset_bytes = 0

    if rollover_flag == 1:
        if DEBUG_PRINT_ENABLE:
            print(
                "Calculating total entries by scanning the effective trace data section."
            )
        trace_total = _count_markers_in_trace_section(
            trace_buffer,
            trace_data_section_start_offset,
            effective_circular_buffer_size_bytes,
            FLAG_MASK,
            FLAG_MASK_SHIFT,
            TRACE_FLAG_WORD_DATA,
            TRACE_FLAG_TIMESTAMP,
            VOID_ENTRY,
        )
        if DEBUG_PRINT_ENABLE:
            print(
                f"Calculated total trace markers in buffer (due to rollover): {trace_total}"
            )

        tentative_initial_offset_bytes = write_index_words * 4
        initial_word_offset_bytes = tentative_initial_offset_bytes

        if effective_circular_buffer_size_bytes > 0:
            offset_of_potential_marker_before_write_index = (
                tentative_initial_offset_bytes
                - 4
                + effective_circular_buffer_size_bytes
            ) % effective_circular_buffer_size_bytes
            absolute_addr_of_potential_marker = (
                trace_data_section_start_offset
                + offset_of_potential_marker_before_write_index
            )

            if absolute_addr_of_potential_marker + 3 < len(trace_buffer):
                item_before_write_index = readMemory32(
                    trace_buffer, absolute_addr_of_potential_marker
                )
                if item_before_write_index != VOID_ENTRY:
                    flag_of_item_before = (
                        item_before_write_index & FLAG_MASK
                    ) >> FLAG_MASK_SHIFT
                    if (
                        flag_of_item_before == TRACE_FLAG_WORD_DATA
                        or flag_of_item_before == TRACE_FLAG_TIMESTAMP
                    ):
                        initial_word_offset_bytes = (
                            offset_of_potential_marker_before_write_index
                        )
                        if DEBUG_PRINT_ENABLE:
                            print(
                                f"Adjusted start: write_index points to payload. Oldest marker is at offset {initial_word_offset_bytes}."
                            )

        if (
            initial_word_offset_bytes >= effective_circular_buffer_size_bytes
            and effective_circular_buffer_size_bytes > 0
        ):
            print(
                f"[WARNING] Calculated initial_word_offset_bytes ({initial_word_offset_bytes}) for rollover is out of effective buffer bounds ({effective_circular_buffer_size_bytes}). Resetting to 0."
            )
            initial_word_offset_bytes = 0
        if DEBUG_PRINT_ENABLE:
            print(
                f"Starting chronological decode at byte offset: {initial_word_offset_bytes} (Word offset: {initial_word_offset_bytes // 4})"
            )
    else:
        trace_total = num_entries_in_current_pass
        if DEBUG_PRINT_ENABLE:
            print(f"Using num_entries_in_current_pass as trace_total: {trace_total}")
            print(f"Starting decode at byte offset: {initial_word_offset_bytes}")

    if trace_total == 0:
        print("[INFO] No trace entries to decode (trace_total is 0).")
        return

    print("********************")

    ADDR_WIDTH = 10
    RAW_ITEM_WIDTH = 10
    SEQ_WIDTH = 4
    LR_WIDTH = 10
    MARKER_STR_WIDTH = 45
    MARKER_DATA_WIDTH = 22
    CPU_FREQ_WIDTH = 10
    US_DIFF_WIDTH = 15
    CUMULATIVE_US_WIDTH = 21

    header_fmt = (
        f"{{:<{ADDR_WIDTH}}} {{:<{RAW_ITEM_WIDTH}}} {{:<{SEQ_WIDTH}}} {{:<{LR_WIDTH}}} {{:<{MARKER_STR_WIDTH}}} "
        f"{{:<{MARKER_DATA_WIDTH}}} {{:<{CPU_FREQ_WIDTH}}} {{:<{US_DIFF_WIDTH}}} {{:<{CUMULATIVE_US_WIDTH}}}"
    )
    print(
        header_fmt.format(
            "Address",
            "Raw Item",
            "Seq#",
            "LR",
            "Trace Marker",
            "Marker Data",
            "CPU Freq",
            "Diff(µs)",
            "Time elapsed (µs)",
        )
    )
    print(
        header_fmt.format(
            "-" * (ADDR_WIDTH),
            "-" * RAW_ITEM_WIDTH,
            "-" * SEQ_WIDTH,
            "-" * LR_WIDTH,
            "-" * MARKER_STR_WIDTH,
            "-" * MARKER_DATA_WIDTH,
            "-" * CPU_FREQ_WIDTH,
            "-" * US_DIFF_WIDTH,
            "-" * CUMULATIVE_US_WIDTH,
        )
    )

    word_offset_bytes = initial_word_offset_bytes
    previous_timestamp_value = 0
    first_timestamp_processed = False
    pll_end_marker_reached = False
    cumulative_us_elapsed = 0.0
    entries_processed = 0

    while entries_processed < trace_total:
        current_trace_item_address_in_buffer = (
            trace_data_section_start_offset + word_offset_bytes
        )

        if current_trace_item_address_in_buffer + 3 >= (
            trace_data_section_start_offset + effective_circular_buffer_size_bytes
        ):
            print(
                f"[ERROR] Attempting to read trace item at offset {current_trace_item_address_in_buffer} which is outside the effective data section (size {effective_circular_buffer_size_bytes}). Processed {entries_processed}/{trace_total} entries."
            )
            break
        if current_trace_item_address_in_buffer + 3 >= len(trace_buffer):
            print(
                f"[ERROR] Attempting to read trace item past buffer end at offset {current_trace_item_address_in_buffer}. Processed {entries_processed}/{trace_total} entries."
            )
            break

        trace_item = readMemory32(trace_buffer, current_trace_item_address_in_buffer)
        s_address = f"[{current_trace_item_address_in_buffer:08x}]"
        s_raw_item = f"0x{trace_item:08X}"
        s_seq_id = ""
        s_lr = ""
        s_marker_string = "VOID_ENTRY"
        s_marker_data = ""
        s_cpu_freq = ""
        s_us_diff = ""
        s_cumulative_us = ""
        word_data_consumed_this_entry_bytes = 0

        if trace_item == VOID_ENTRY:
            s_marker_string = s_marker_string.replace("\n", " ")
            print(
                header_fmt.format(
                    s_address, s_raw_item, "", "", s_marker_string, "", "", "", ""
                )
            )
        else:
            flag = (trace_item & FLAG_MASK) >> FLAG_MASK_SHIFT
            seq_id = (trace_item & SEQ_ID_MASK) >> SEQ_ID_MASK_SHIFT
            addr = (trace_item & ADDR_MASK) >> ADDR_MASK_SHIFT
            marker = (trace_item & MARKER_MASK) >> MARKER_MASK_SHIFT
            s_seq_id = str(seq_id)
            s_lr = f"0x{addr:04X}"
            current_marker_str = marker_lookup.get(
                marker, f"UNKNOWN_MARKER_0x{marker:X}"
            )
            s_marker_string = current_marker_str

            # SERAM no longer uses the PLL for it's Clock
            #            if pll_end_marker_reached:
            #                current_cpu_frequency_hz = 100_000_000
            #                s_cpu_freq = "100 MHz"
            #            else:
            #                current_cpu_frequency_hz = 76_800_000
            #                s_cpu_freq = "76.8 MHz"

            current_cpu_frequency_hz = 76_800_000
            s_cpu_freq = "76.8 MHz"

            is_seram_reset_handler_marker = current_marker_str == marker_lookup.get(
                TRACE_SERAM_RESET_HANDLER
            )

            if is_seram_reset_handler_marker:
                pll_end_marker_reached = False
                current_cpu_frequency_hz = 76_800_000
                s_cpu_freq = "76.8 MHz"

            data_word_logical_offset = (
                word_offset_bytes + 4
            ) % effective_circular_buffer_size_bytes
            actual_data_word_address_in_buffer = (
                trace_data_section_start_offset + data_word_logical_offset
            )

            if TRACE_FLAG_WORD_DATA == flag:
                word_data_consumed_this_entry_bytes = 4
                if actual_data_word_address_in_buffer + 3 >= (
                    trace_data_section_start_offset
                    + effective_circular_buffer_size_bytes
                ) or actual_data_word_address_in_buffer + 3 >= len(trace_buffer):
                    s_marker_data = "ERR_READ_DATA_BOUNDS"
                else:
                    word_data = readMemory32(
                        trace_buffer, actual_data_word_address_in_buffer
                    )
                    if current_marker_str == "TOC Part#":
                        chars = "".join(
                            [
                                chr((word_data >> (i * 8)) & 0xFF)
                                for i in range(4)
                                if (word_data >> (i * 8)) & 0xFF != 0
                            ]
                        )
                        s_marker_data = (
                            f"0x{word_data:08X} {chars.strip().replace(chr(0), '')}"
                        )
                    elif (
                        current_marker_str == "Process MHU"
                        and word_data in service_id_lut
                    ):
                        s_marker_data = service_id_lut[word_data][
                            : MARKER_DATA_WIDTH - 1
                        ]
                    else:
                        s_marker_data = f"0x{word_data:08X}"
            elif TRACE_FLAG_TIMESTAMP == flag:
                word_data_consumed_this_entry_bytes = 4
                if actual_data_word_address_in_buffer + 3 >= (
                    trace_data_section_start_offset
                    + effective_circular_buffer_size_bytes
                ) or actual_data_word_address_in_buffer + 3 >= len(trace_buffer):
                    s_marker_data = "ERR_READ_TS_BOUNDS"
                else:
                    timestamp_val = readMemory32(
                        trace_buffer, actual_data_word_address_in_buffer
                    )
                    s_marker_data = f"T:{timestamp_val}"
                    tick_diff = 0

                    if is_seram_reset_handler_marker:
                        tick_diff = timestamp_val
                        if DEBUG_PRINT_ENABLE:
                            print(
                                f"DEBUG: Special diff for '{current_marker_str}' -> tick_diff = {tick_diff}"
                            )
                        first_timestamp_processed = True
                    elif not first_timestamp_processed:
                        tick_diff = timestamp_val
                        first_timestamp_processed = True
                    else:
                        tick_diff = timestamp_val - previous_timestamp_value

                    previous_timestamp_value = timestamp_val

                    if current_cpu_frequency_hz > 0:
                        current_us_diff_val = (
                            tick_diff / current_cpu_frequency_hz
                        ) * 1_000_000
                        s_us_diff = f"{current_us_diff_val:.2f}"
                        if is_seram_reset_handler_marker:
                            cumulative_us_elapsed = (
                                current_us_diff_val  # Reset cumulative time
                            )
                        else:
                            cumulative_us_elapsed += (
                                current_us_diff_val  # Add to existing cumulative time
                            )
                        s_cumulative_us = f"{cumulative_us_elapsed:.2f}"
                    else:
                        s_us_diff = "N/A Freq"
                        s_cumulative_us = "N/A Freq"
            elif TRACE_FLAG_BYTE_DATA == flag:
                s_marker_data = f"Data:0x{marker:02X}"
            elif TRACE_FLAG_NO_DATA == flag:
                s_marker_data = ""
            else:
                s_marker_data = f"UNK_FLAG_0x{flag:02X}"

            s_marker_string = s_marker_string.replace("\n", " ").replace("\r", "")
            s_marker_data = s_marker_data.replace("\n", " ").replace("\r", "")
            print(
                header_fmt.format(
                    s_address,
                    s_raw_item,
                    s_seq_id,
                    s_lr,
                    s_marker_string,
                    s_marker_data,
                    s_cpu_freq,
                    s_us_diff,
                    s_cumulative_us,
                )
            )

            if (
                not is_seram_reset_handler_marker
                and not pll_end_marker_reached
                and current_marker_str == marker_lookup.get(TRACE_PLL_INIT_END)
            ):
                pll_end_marker_reached = True

        word_offset_bytes = (
            word_offset_bytes + 4 + word_data_consumed_this_entry_bytes
        ) % effective_circular_buffer_size_bytes
        entries_processed += 1


if __name__ == "__main__":
    # --- To test DEBUG prints, set DEBUG_PRINT_ENABLE = True above ---

    print("--- Running with dummy NO ROLLOVER SERAM buffer ---")
    header_no_rollover = (0x00 << 24) | (3 << 16) | (0 << 8) | 0x01
    dummy_trace_data_no_rollover = bytearray()
    item1 = (
        (0x1000 << ADDR_MASK_SHIFT)
        | (TRACE_BEGIN_RESET << MARKER_MASK_SHIFT)
        | (1 << SEQ_ID_MASK_SHIFT)
        | TRACE_FLAG_TIMESTAMP
    )
    ts1 = 76800
    dummy_trace_data_no_rollover.extend(item1.to_bytes(4, "little"))
    dummy_trace_data_no_rollover.extend(ts1.to_bytes(4, "little"))
    item2 = (
        (0x2000 << ADDR_MASK_SHIFT)
        | (TRACE_PLL_INIT_END << MARKER_MASK_SHIFT)
        | (2 << SEQ_ID_MASK_SHIFT)
        | TRACE_FLAG_WORD_DATA
    )
    data2 = 0xAABBCCDD
    dummy_trace_data_no_rollover.extend(item2.to_bytes(4, "little"))
    dummy_trace_data_no_rollover.extend(data2.to_bytes(4, "little"))
    item3 = (
        (0x3000 << ADDR_MASK_SHIFT)
        | (TRACE_FIREWALLS_INITIALIZED << MARKER_MASK_SHIFT)
        | (3 << SEQ_ID_MASK_SHIFT)
        | TRACE_FLAG_NO_DATA
    )
    dummy_trace_data_no_rollover.extend(item3.to_bytes(4, "little"))
    buffer_for_decode_no_rollover = bytearray()
    buffer_for_decode_no_rollover.extend(dummy_trace_data_no_rollover)
    buffer_for_decode_no_rollover.extend(header_no_rollover.to_bytes(4, "little"))
    buffer_for_decode_no_rollover.extend(TRACE_BUFFER_END_MARKER.to_bytes(4, "little"))
    trace_buffer_decode(buffer_for_decode_no_rollover, seram_flag=True)
    print("-" * 80)

    print(
        "--- Running with dummy ROLLOVER SERAM buffer (write_index points to payload) ---"
    )
    header_rollover_payload_at_widx = (0x01 << 24) | (3 << 16) | (0 << 8) | 0x05
    dummy_trace_data_widx_payload = bytearray(16)
    dummy_trace_data_widx_payload[0:4] = (0xDDDDDDDD).to_bytes(4, "little")
    item_r_1 = (
        (0xA000 << ADDR_MASK_SHIFT)
        | (TRACE_COLD_BOOT << MARKER_MASK_SHIFT)
        | (1 << SEQ_ID_MASK_SHIFT)
        | TRACE_FLAG_NO_DATA
    )
    dummy_trace_data_widx_payload[4:8] = item_r_1.to_bytes(4, "little")
    item_r_2 = (
        (0xB000 << ADDR_MASK_SHIFT)
        | (TRACE_WAKE_UP << MARKER_MASK_SHIFT)
        | (2 << SEQ_ID_MASK_SHIFT)
        | TRACE_FLAG_NO_DATA
    )
    dummy_trace_data_widx_payload[8:12] = item_r_2.to_bytes(4, "little")
    item_r_oldest_marker = (
        (0xC000 << ADDR_MASK_SHIFT)
        | (TRACE_PLL_INIT_END << MARKER_MASK_SHIFT)
        | (3 << SEQ_ID_MASK_SHIFT)
        | TRACE_FLAG_WORD_DATA
    )
    dummy_trace_data_widx_payload[12:16] = item_r_oldest_marker.to_bytes(4, "little")
    buffer_decode_widx_payload = bytearray()
    buffer_decode_widx_payload.extend(dummy_trace_data_widx_payload)
    buffer_decode_widx_payload.extend(
        header_rollover_payload_at_widx.to_bytes(4, "little")
    )
    buffer_decode_widx_payload.extend(TRACE_BUFFER_END_MARKER.to_bytes(4, "little"))
    trace_buffer_decode(buffer_decode_widx_payload, seram_flag=True)
    print("-" * 80)

    print(
        "--- Running with dummy ROLLOVER SERAM buffer (write_index points to marker) ---"
    )
    header_rollover_marker_at_widx = (0x01 << 24) | (3 << 16) | (1 << 8) | 0x05
    buffer_decode_marker_at_widx = bytearray()
    buffer_decode_marker_at_widx.extend(dummy_trace_data_widx_payload)
    buffer_decode_marker_at_widx.extend(
        header_rollover_marker_at_widx.to_bytes(4, "little")
    )
    buffer_decode_marker_at_widx.extend(TRACE_BUFFER_END_MARKER.to_bytes(4, "little"))
    trace_buffer_decode(buffer_decode_marker_at_widx, seram_flag=True)

    # Example of loading from a file:
    # try:
    #     with open("your_trace_dump.bin", "rb") as f:
    #         actual_trace_data = bytearray(f.read())
    #     print("\n--- Running with actual trace data from file ---")
    #     trace_buffer_decode(actual_trace_data, seram_flag=True)
    # except FileNotFoundError:
    #     print("\n[INFO] Actual trace data file (your_trace_dump.bin) not found. Skipping.")
    # except Exception as e:
    #     print(f"\n[ERROR] Could not process actual trace file: {e}")
