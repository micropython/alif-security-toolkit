#!/usr/bin/env python3
# pylint: disable=consider-using-with
# pylint: disable=consider-using-f-string
# pylint: disable=line-too-long
"""
Tool to generate OTP image for provisoning OSPI OTP data

This includes
ALIF SE Security Flags2        Boot selection bits

Generates data based on the following mapped strcuture
     typedef struct
     {
         uint32_t rx_sample_delay         :8;
         uint32_t xip_incr_inst           :8
         uint32_t xip_wrap_inst           :8
         uint32_t aes_rxds_delay          :8
         uint32_t ddr_drive_edge          :8
         uint32_t pinmux_sel              :3
         uint32_t bus_speed_sel           :3
         uint32_t fast_read_wait_cycles   :4
         uint32_t flash_size              :3
         uint32_t valid                   :1
         uint32_t reset_port              :5
         uint32_t'reset_pin               :3
         uint32_t spi_mode                :2

         uint32_t io_mode                 :2;
         uint32_t ddr_en                  :1;
         uint32_t xip_ddr_en              :1;
         uint32_t inst_ddr_en             :1;
         uint32_t xip_inst_ddr_en         :1;
         uint32_t rxds_en                 :1;
         uint32_t rxds_vl_en              :1;
         uint32_t xip_rxds_vl_en          :1;
         uint32_t dfs                     :5;
         uint32_t xip_dfs                 :5;
         uint32_t xip_rxds_en             :1;
         uint32_t xip_instr_len           :2;
         uint32_t xip_addr_len            :4;
         uint32_t xip_spi_mode            :2;
         uint32_t xip_hyperbus_en         :1;
         unit32_t tx_wait_count           :2,
         uint32_t reserved_0              :1;
         uint32_t slave_select            :2;
     } ospi_data_t;

     __author__ = "ronyett"
     __copyright__ = "ALIF Semiconductor"
     __version__ = "0.03.000"
     __status__ = "Dev"      "
"""

import sys
import json
import struct
from json.decoder import JSONDecodeError
from pathlib import Path

# Define Version constant for each separate tool
# 0.03.000 SE-3317 Missing eFuse power enable
TOOL_VERSION = "0.03.000"


binPath = Path("bin/")
scriptPath = Path("bin/")

EXIT_WITH_ERROR = 1

# Supported JSON keywords
SUPPORTED_ATTRIBUTES = ["version", "portnumber", "pioportflashsize", "pinmux", "delay"]

SUPPORTED_BOOT_PATH = ["MRAM", "MRAMTHENEXT", "EXT", "INVALID"]

LOADING_OPTIONS_LUT = {
    "MRAM_ONLY": 0x00,
    "MRAM_THEN_EXTERNAL": 0x01,
    "EXTERNAL_MEM_ONLY": 0x02,
}

EXT_MEMORY_TYPES_LUT = {
    "OSPI_FLASH_8BIT_XIP_MODE": 0x0,
    "OSPI_FLASH_8BIT_SPI_MODE": 0x1,
    "NAND_FLASH_8BIT_BURST_MODE": 0x2,
    "SPI_FLASH_1BIT_STD_MODE": 0x3,
}

DEBUG_PRINT = False


def list_to_32bit_binary_ascii(word_list, endianess="big"):
    """
    list_to_32bit_binary_ascii convert word list to 32-bits

    Args:
    word_list

    Returns
    ascii binary
    """
    if endianess not in ["big", "little"]:
        return ["[ERROR: enabianess not big or little"]

    if endianess == "little":
        word_list = list(reversed(word_list))
    #        print("Reversed: ", word_list )

    binary_string = ""
    for hex_value in word_list:
        try:
            # Handle case-insensitive hex values
            integer_value = int(hex_value, 16)
            # Convert to 8-bit binary
            binary = bin(integer_value)[2:].zfill(8)
            binary_string += binary
        except ValueError:
            return [f"[ERROR]: '{hex_value}' is not a valid hexadecimal value"]

    # Split into 32-bit chunks
    binary_lines = []
    for i in range(0, len(binary_string), 32):
        # Take 32 bits or whatever is left if less than 32
        chunk = binary_string[i : i + 32]

        # Pad the last chunk to 32 bits if needed
        if len(chunk) < 32:
            #            chunk = chunk.append('00000000')
            chunk = chunk.ljust(32, "0")

        binary_lines.append(chunk)
    #    plain = ''.join(binary_lines)
    #    print("plain ", plain)
    return "".join(binary_lines)


def dict_raise_on_duplicates(ordered_pairs):
    """
    Reject duplicate keys.

    Args:
    ordered_pairs
    """
    d = {}
    for k, v in ordered_pairs:
        if k in d:
            raise ValueError("Duplicate key: %r" % (k,))
        else:
            d[k] = v
    return d


def trace_print(*args, **kwargs):
    """
    trace_print - filter out DBG messages

    Args:
    args      argv equivalent
    kwargs

    Returns
    None
    """
    is_debug = False
    if "[DBG]" in args:
        is_debug = True
    if DEBUG_PRINT:
        print(*args, **kwargs)


def read_json_file(file, attributes, boot_path):
    """
    read the json file

    Args:
    file    json file to read
    attributs Not used
    boot_path not used

    Returns:
    json contents
    """
    try:
        f = open(file, "r")
    except FileNotFoundError:
        print("[ERROR] file " + file + " does not exist!")
        sys.exit(EXIT_WITH_ERROR)
    except:
        print("[ERROR] opening configuration file")
        sys.exit(EXIT_WITH_ERROR)

    try:
        cfg = json.load(f, object_pairs_hook=dict_raise_on_duplicates)
    except JSONDecodeError as e:
        print("[ERROR] ERROR in JSON file.")
        print(str(e))
        sys.exit(EXIT_WITH_ERROR)
    except ValueError as v:
        print("[ERROR] ERROR in JSON file:")
        print(str(v))
        sys.exit(EXIT_WITH_ERROR)
    except:
        print("[ERROR] Unknown error loading JSON file")
        sys.exit(EXIT_WITH_ERROR)

    f.close()

    return cfg


def pack_ospi_data_to_integers(data):
    """
    Pack OSPI settings into 32-bit integers according to the bit-field definition.

    Args:
        data (dict): Dictionary with OSPI settings

    Returns:
        list: List of 32-bit integers representing the packed structure
    """
    # Initialize our 32-bit words
    word0 = 0  # First 32-bit word
    word1 = 0  # Second 32-bit word
    word2 = 0  # Third 32-bit word
    word3 = 0  # Fourth 32-bit word

    # First word: Contains 8-bit fields
    word0 |= int(data.get("rx_sample_delay", 0)) & 0xFF
    word0 |= (int(data.get("xip_incr_inst", 0)) & 0xFF) << 8
    word0 |= (int(data.get("xip_wrap_inst", 0)) & 0xFF) << 16
    word0 |= (int(data.get("aes_rxds_delay", 0)) & 0xFF) << 24

    # Second word: Contains mixed width fields
    word1 |= int(data.get("ddr_drive_edge", 0)) & 0xFF
    word1 |= (int(data.get("pinmux_sel", 0)) & 0x7) << 8  # 3 bits
    word1 |= (int(data.get("bus_speed_sel", 0)) & 0x7) << 11  # 3 bits
    word1 |= (int(data.get("fast_read_wait_cycles", 0)) & 0xF) << 14  # 4 bits
    word1 |= (int(data.get("flash_size", 0)) & 0x7) << 18  # 3 bits
    word1 |= (int(data.get("valid", 0)) & 0x1) << 21  # 1 bit
    word1 |= (int(data.get("reset_port", 0)) & 0x1F) << 22  # 5 bits
    word1 |= (int(data.get("reset_pin", 0)) & 0x7) << 27  # 3 bits
    word1 |= (int(data.get("spi_mode", 0)) & 0x3) << 30  # 2 bits

    # Third word: Contains mixed width fields
    word2 |= int(data.get("io_mode", 0)) & 0x3  # 2 bits
    word2 |= (int(data.get("ddr_en", 0)) & 0x1) << 2  # 1 bit
    word2 |= (int(data.get("xip_ddr_en", 0)) & 0x1) << 3  # 1 bit
    word2 |= (int(data.get("inst_ddr_en", 0)) & 0x1) << 4  # 1 bit
    word2 |= (int(data.get("xip_inst_ddr_en", 0)) & 0x1) << 5  # 1 bit
    word2 |= (int(data.get("rxds_en", 0)) & 0x1) << 6  # 1 bit
    word2 |= (int(data.get("rxds_vl_en", 0)) & 0x1) << 7  # 1 bit
    word2 |= (int(data.get("xip_rxds_vl_en", 0)) & 0x1) << 8  # 1 bit
    word2 |= (int(data.get("dfs", 0)) & 0x1F) << 9  # 5 bits
    word2 |= (int(data.get("xip_dfs", 0)) & 0x1F) << 14  # 5 bits
    word2 |= (int(data.get("xip_rxds_en", 0)) & 0x1) << 19  # 1 bit
    word2 |= (int(data.get("xip_instr_len", 0)) & 0x3) << 20  # 2 bits
    word2 |= (int(data.get("xip_addr_len", 0)) & 0xF) << 22  # 4 bits
    word2 |= (int(data.get("xip_spi_mode", 0)) & 0x3) << 26  # 2 bits
    word2 |= (int(data.get("xip_hyperbus_en", 0)) & 0x1) << 28  # 1 bit
    word2 |= (int(data.get("tx_wait_count", 0)) & 0x3) << 29  # 2 bits
    word2 |= (int(data.get("reserved_0", 0)) & 0x1) << 31  # 1 bit

    # Fourth word: Slave Select (new word)
    word3 |= int(data.get("slave_select", 0)) & 0x3  # 2 bits

    return [word0, word1, word2, word3]


def print_binary_data(word):
    """
    print_binary_data

    Args:
    word     data to print as binary

    Returns
    string with binary raw or formatted

    """
    binary_raw = format(word, "032b")
    binary_formatted = " ".join([binary_raw[i : i + 8] for i in range(0, 32, 8)])

    return binary_formatted


def dump_bitfield_details(sf, settings, packed_integers):
    """
    dump_bitfield_details

    Args:
    sf                  output file handle
    otp_opts            JSON list
    packed_integers     3 words containing bit patterns
    Returns:
        None
    """
    word1 = packed_integers[0]
    word2 = packed_integers[1]
    word3 = packed_integers[2]
    word4 = packed_integers[3]

    sf.write(f"\n#WORD 1: 0x{word1:08X} %s\n" % (print_binary_data(word1)))
    sf.write(
        f"#    rx_sample_delay:     {settings['rx_sample_delay']}     (0x{settings['rx_sample_delay']:02X}) -> Bits 0 - 7: 0x{(word1 & 0xFF):02X}\n"
    )
    sf.write(
        f"#    xip_incr_inst:         {settings['xip_incr_inst']} (0x{settings['xip_incr_inst']:02X}) -> Bits 8 -15: 0x{((word1 >> 8) & 0xFF):02X}\n"
    )
    sf.write(
        f"#    xip_wrap_inst:         {settings['xip_wrap_inst']} (0x{settings['xip_wrap_inst']:02X}) -> Bits 16-23: 0x{((word1 >> 16) & 0xFF):02X}\n"
    )
    sf.write(
        f"#    aes_rxds_delay:        {settings['aes_rxds_delay']} (0x{settings['aes_rxds_delay']:02X}) -> Bits 24-31: 0x{((word1 >> 24) & 0xFF):02X}\n"
    )

    sf.write(f"\n#WORD 2: 0x{word2:08X} %s\n" % (print_binary_data(word2)))
    sf.write(
        f"#    ddr_drive_edge:             {settings['ddr_drive_edge']} (0x{settings['ddr_drive_edge']:02X}) -> Bits 0 - 7:     0x{(word2 & 0xFF):02X}\n"
    )
    sf.write(
        f"#    pinmux_sel:                 {settings['pinmux_sel']} (0x{settings['pinmux_sel']:01X})     -> Bits 8 -10:     0x{((word2 >> 8) & 0x7):01X}\n"
    )
    sf.write(
        f"#    bus_speed_sel:            {settings['bus_speed_sel']} (0x{settings['bus_speed_sel']:01X})     -> Bits 11-13:     0x{((word2 >> 11) & 0x7):01X}\n"
    )
    sf.write(
        f"#    fast_read_wait_cycles: {settings['fast_read_wait_cycles']} (0x{settings['fast_read_wait_cycles']:01X})     -> Bits 14-17:     0x{((word2 >> 14) & 0xF):01X}\n"
    )
    sf.write(
        f"#    flash_size:                 {settings['flash_size']} (0x{settings['flash_size']:01X})     -> Bits 18-20:     0x{((word2 >> 18) & 0x7):01X}\n"
    )
    sf.write(
        f"#    valid:                      {settings['valid']} (0x{settings['valid']:01X})     -> Bit 21:             0x{((word2 >> 21) & 0x1):01X}\n"
    )
    sf.write(
        f"#    reset_port:                 {settings['reset_port']} (0x{settings['reset_port']:02X})-> Bits 22-26:     0x{((word2 >> 22) & 0x1F):02X}\n"
    )
    sf.write(
        f"#    reset_pin:                {settings['reset_pin']} (0x{settings['reset_pin']:01X})     -> Bits 27-29:     0x{((word2 >> 27) & 0x7):01X}\n"
    )
    sf.write(
        f"#    spi_mode:                {settings['spi_mode']} (0x{settings['spi_mode']:01X})     -> Bits 30-31:     0x{((word2 >> 30) & 0x3):01X}\n"
    )

    sf.write(f"\n#WORD 3: 0x{word3:08X} %s\n" % (print_binary_data(word3)))
    sf.write(
        f"#    io_mode:                {settings['io_mode']}     (0x{settings['io_mode']:01X})     -> Bits 0-1:         0x{(word3 & 0x3):01X}\n"
    )
    sf.write(
        f"#    ddr_en:                 {settings['ddr_en']}     (0x{settings['ddr_en']:01X})     -> Bit 2:                 0x{((word3 >> 2) & 0x1):01X}\n"
    )
    sf.write(
        f"#    xip_ddr_en:                {settings['xip_ddr_en']}     (0x{settings['xip_ddr_en']:01X})     -> Bit 3:                 0x{((word3 >> 3) & 0x1):01X}\n"
    )
    sf.write(
        f"#    inst_ddr_en:            {settings['inst_ddr_en']}     (0x{settings['inst_ddr_en']:01X})     -> Bit 4:                 0x{((word3 >> 4) & 0x1):01X}\n"
    )
    sf.write(
        f"#    xip_inst_ddr_en:        {settings['xip_inst_ddr_en']}     (0x{settings['xip_inst_ddr_en']:01X})     -> Bit 5:                 0x{((word3 >> 5) & 0x1):01X}\n"
    )
    sf.write(
        f"#    rxds_en:                 {settings['rxds_en']}     (0x{settings['rxds_en']:01X})     -> Bit 6:                 0x{((word3 >> 6) & 0x1):01X}\n"
    )
    sf.write(
        f"#    rxds_vl_en:                {settings['rxds_vl_en']}     (0x{settings['rxds_vl_en']:01X})     -> Bit 7:                 0x{((word3 >> 7) & 0x1):01X}\n"
    )
    sf.write(
        f"#    xip_rxds_vl_en:            {settings['xip_rxds_vl_en']}     (0x{settings['xip_rxds_vl_en']:01X})     -> Bit 8:                 0x{((word3 >> 8) & 0x1):01X}\n"
    )
    sf.write(
        f"#    dfs:                     {settings['dfs']} (0x{settings['dfs']:02X}) -> Bits 9-13:        0x{((word3 >> 9) & 0x1F):02X}\n"
    )
    sf.write(
        f"#    xip_dfs:                 {settings['xip_dfs']} (0x{settings['xip_dfs']:02X}) -> Bits 14-18:     0x{((word3 >> 14) & 0x1F):02X}\n"
    )
    sf.write(
        f"#    xip_rxds_en:            {settings['xip_rxds_en']}     (0x{settings['xip_rxds_en']:01X})     -> Bit 19:             0x{((word3 >> 19) & 0x1):01X}\n"
    )
    sf.write(
        f"#    xip_instr_len:            {settings['xip_instr_len']}     (0x{settings['xip_instr_len']:01X})     -> Bits 20-21:     0x{((word3 >> 20) & 0x3):01X}\n"
    )
    sf.write(
        f"#    xip_addr_len:            {settings['xip_addr_len']}     (0x{settings['xip_addr_len']:01X})     -> Bits 22-25:     0x{((word3 >> 22) & 0xF):01X}\n"
    )
    sf.write(
        f"#    xip_spi_mode:            {settings['xip_spi_mode']}     (0x{settings['xip_spi_mode']:01X})     -> Bits 26-27:     0x{((word3 >> 26) & 0x3):01X}\n"
    )
    sf.write(
        f"#    xip_hyperbus_en:        {settings['xip_hyperbus_en']}     (0x{settings['xip_hyperbus_en']:01X})     -> Bit 28:             0x{((word3 >> 28) & 0x1):01X}\n"
    )
    sf.write(
        f"#    tx_wait_count:            {settings['tx_wait_count']}     (0x{settings['tx_wait_count']:01X})     -> Bits 29-30:     0x{((word3 >> 29) & 0x3):01X}\n"
    )
    sf.write(
        f"#    reserved_0:                {settings['reserved_0']}     (0x{settings['reserved_0']:01X})     -> Bit 31:             0x{((word3 >> 31) & 0x1):01X}\n"
    )

    sf.write(f"\n#WORD 4: 0x{word4:08X} %s\n" % (print_binary_data(word4)))
    sf.write(
        f"#    slave_select:            {settings['slave_select']}     (0x{settings['slave_select']:01X})     -> Bits 0-1:         0x{(word4 & 0x3):01X}\n"
    )


def get_extmem_options(otp_opts):
    """
    get_extmem_options - process the Ext Memory configuration parameters
    """
    extmem_option_bits = 0x00
    trace_print("[DBG] get_extmem_options : ", extmem_option_bits)

    rx_sample_delay = otp_opts["rx_sample_delay"]
    trace_print("[DBG] rx_sample_delay         ", rx_sample_delay)

    xip_incr_inst = otp_opts["xip_incr_inst"]
    trace_print("[DBG] xip_incr_inst             ", hex(xip_incr_inst))

    xip_wrap_inst = otp_opts["xip_wrap_inst"]
    trace_print("[DBG] xip_wrap_inst             ", hex(xip_wrap_inst))

    aes_rxds_delay = otp_opts["aes_rxds_delay"]
    trace_print("[DBG] aes_rxds_delay         ", hex(aes_rxds_delay))

    ddr_drive_edge = otp_opts["ddr_drive_edge"]
    trace_print("[DBG] ddr_drive_edge         ", ddr_drive_edge)

    pinmux_sel = otp_opts["pinmux_sel"]
    trace_print("[DBG] pinmux_sel             ", pinmux_sel)

    bus_speed_sel = otp_opts["bus_speed_sel"]
    trace_print("[DBG] bus_speed_sel         ", bus_speed_sel)

    fast_read_wait_cycles = otp_opts["fast_read_wait_cycles"]
    trace_print("[DBG] fast_read_wait_cycles ", fast_read_wait_cycles)

    flash_size = otp_opts["flash_size"]
    trace_print("[DBG] Flash size             ", flash_size)

    valid = otp_opts["valid"]
    trace_print("[DBG] valid                 ", valid)

    reset_port = otp_opts["reset_port"]
    trace_print("[DBG] reset_port             ", hex(reset_port))

    reset_pin = otp_opts["reset_pin"]
    trace_print("[DBG] reset_pin             ", reset_pin)

    spi_mode = otp_opts["spi_mode"]
    trace_print("[DBG] spi_mode             ", spi_mode)

    io_mode = otp_opts["io_mode"]
    trace_print("[DBG] io_mode                 ", io_mode)

    ddr_en = otp_opts["ddr_en"]
    trace_print("[DBG] ddr_en                 ", ddr_en)

    xip_ddr_en = otp_opts["xip_ddr_en"]
    trace_print("[DBG] xip_ddr_en             ", xip_ddr_en)

    inst_ddr_en = otp_opts["inst_ddr_en"]
    trace_print("[DBG] inst_ddr_en             ", inst_ddr_en)

    xip_inst_ddr_en = otp_opts["xip_inst_ddr_en"]
    trace_print("[DBG] xip_inst_ddr_en         ", xip_inst_ddr_en)

    rxds_en = otp_opts["rxds_en"]
    trace_print("[DBG] rxds_en                 ", rxds_en)

    rxds_vl_en = otp_opts["rxds_vl_en"]
    trace_print("[DBG] rxds_vl_en             ", rxds_vl_en)

    xip_rxds_vl_en = otp_opts["xip_rxds_vl_en"]
    trace_print("[DBG] xip_rxds_vl_en         ", xip_rxds_vl_en)

    dfs = otp_opts["dfs"]
    trace_print("[DBG] dfs                     ", hex(dfs))

    xip_dfs = otp_opts["xip_dfs"]
    trace_print("[DBG] xip_dfs                 ", hex(xip_dfs))

    xip_rxds_en = otp_opts["xip_rxds_en"]
    trace_print("[DBG] xip_rxds_en             ", xip_rxds_en)

    xip_instr_len = otp_opts["xip_instr_len"]
    trace_print("[DBG] xip_instr_len             ", xip_instr_len)

    xip_addr_len = otp_opts["xip_addr_len"]
    trace_print("[DBG] xip_addr_len             ", xip_addr_len)

    xip_spi_mode = otp_opts["xip_spi_mode"]
    trace_print("[DBG] xip_spi_mode             ", xip_spi_mode)

    xip_hyperbus_en = otp_opts["xip_hyperbus_en"]
    trace_print("[DBG] xip_hyperbus_en         ", xip_hyperbus_en)

    tx_wait_count = otp_opts["tx_wait_count"]
    trace_print("[DBG] tx_wait_count             ", tx_wait_count)

    # New fields
    reserved_0 = otp_opts["reserved_0"]
    trace_print("[DBG] reserved_0             ", reserved_0)

    slave_select = otp_opts["slave_select"]
    trace_print("[DBG] slave_select           ", slave_select)

    word1 = 0
    word2 = 0
    word3 = 0
    word4 = 0

    word1 = (
        ((rx_sample_delay & 0xFF) << 0)
        | ((xip_incr_inst & 0xFF) << 8)
        | ((xip_wrap_inst & 0xFF) << 16)
        | ((aes_rxds_delay & 0xFF) << 24)
    )
    word2 = (
        ((ddr_drive_edge & 0xFF) << 0)
        | ((pinmux_sel & 0x7) << 8)
        | ((bus_speed_sel & 0x7) << 11)
        | ((fast_read_wait_cycles & 0xF) << 14)
        | ((flash_size & 0x7) << 18)
        | ((valid & 0x1) << 21)
        | ((reset_port & 0x1F) << 22)
        | ((reset_pin & 0x7) << 27)
        | ((spi_mode & 0x3) << 30)
    )
    word3 = (
        ((io_mode & 0x3) << 0)
        | ((ddr_en & 0x1) << 2)
        | ((xip_ddr_en & 0x1) << 3)
        | ((inst_ddr_en & 0x1) << 4)
        | ((xip_inst_ddr_en & 0x1) << 5)
        | ((rxds_en & 0x1) << 6)
        | ((rxds_vl_en & 0x1) << 7)
        | ((xip_rxds_vl_en & 0x1) << 8)
        | ((dfs & 0x1F) << 9)
        | ((xip_dfs & 0x1F) << 14)
        | ((xip_rxds_en & 0x1) << 19)
        | ((xip_instr_len & 0x3) << 20)
        | ((xip_addr_len & 0xF) << 22)
        | ((xip_spi_mode & 0x3) << 26)
        | ((xip_hyperbus_en & 0x1) << 28)
        | ((tx_wait_count & 0x3) << 29)
        | ((reserved_0 & 0x1) << 31)
    )
    word4 = (slave_select & 0x3) << 0

    ospi_otp_data = struct.pack("<IIII", word1, word2, word3, word4)

    #   trace_print("[DBG] OSPI otp data struct ", ospi_otp_data)

    return ospi_otp_data, [word1, word2, word3, word4]


def get_boot_options(boot_opts):
    """
    process the SERAM load option flags

    Args:
        boot_opts (str): JSON string with boot options
    Returns:
        int: load bits
    """
    loading_option_bits = 0x00  # Default is MRAM Only

    trace_print("[DBG] get_boot_options : ", boot_opts)

    loading_option = boot_opts["load"]
    trace_print("[DBG] SERAM load option", loading_option)

    if not loading_option:
        print("[ERROR] get_boot_options, invalid loading option")
        sys.exit(1)
    alternate_sram_load = LOADING_OPTIONS_LUT.get(loading_option)
    loading_option_bits |= alternate_sram_load << 16
    trace_print("[INFO] SERAM load option value 0x%X" % (loading_option_bits))

    loading_option = boot_opts["type"]
    trace_print("[INFO] External Memory Type", loading_option)

    if not loading_option:
        print("[ERROR] get_boot_options, invalid External memory type option")
        sys.exit(1)
    ext_mem_type = EXT_MEMORY_TYPES_LUT.get(loading_option)
    trace_print("[DBG] Ext Memory Type value 0x%X" % (ext_mem_type))

    loading_option_bits |= ext_mem_type << 24

    trace_print("[DBG] 0x112 options 0x%X" % (ext_mem_type))

    return loading_option_bits


def process_otp_data(
    sections,
    os_file="otp-altload.bin",
    ds_file="otp-extomem.bin",
    script_file="otp-burn-ospi.ds",
    generate_script=False,
):
    """
    Process JSON file for
        - BOOTOPT
        - OSPI Parameters
        Process each JSON section and create an ARM-DS script file or binary
        file.
    Args:
        sections (str):              JSON values for BOOTOPT and OSPI Params
        os_File                      Loading options binary file
        ds_file                      Ext mem options binary file
        script_file (str):           Name of ARM-DS script file output
        generate_script (bool):  Generate Script file (or not)
    Returns:
        None
    """
    try:
        of = open(binPath / os_file, "wb")
    except (IOError, OSError) as e:
        print("[ERROR] Failed to open binary file %s %s" % (os_file, e))
        sys.exit(EXIT_WITH_ERROR)

    try:
        ds = open(binPath / ds_file, "wb")
    except (IOError, OSError) as e:
        print("[ERROR] Failed to open binary file %s %s" % (ds_file, e))
        sys.exit(EXIT_WITH_ERROR)

    # Open up a script file
    if generate_script:
        try:
            sf = open(scriptPath / script_file, "w")
        except (IOError, OSError) as e:
            print("[ERROR] Failed to open script file %s %s" % (script_file, e))
            sys.exit(EXIT_WITH_ERROR)

    # Write out BOOT SERAM loading options
    if "BOOTOPT" in sections:
        boot_options = sections["BOOTOPT"]
        seram_loading_options = get_boot_options(boot_options)
        trace_print("[DBG] seram_loading_options 0x%X" % (seram_loading_options))

        if generate_script:
            sf.write("\n# efuse Power enable\n")
            sf.write("memory set <verify=0>:0x7a60a004 32 0x30\n")
            sf.write("\n")

            sf.write("# Set BOOTOPT OTP\n")
            sf.write(
                "memory set <verify=0>:0x2F002110 0 0x%08X\n"
                % (int(seram_loading_options))
            )

            sf.write("\n# efuse Power disable\n")
            sf.write("memory set <verify=0>:0x7a60a004 32 0x10\n")
        of.write(struct.pack("I", int(seram_loading_options)))
    else:
        print("[ERROR] No boot option specified")

    # Process External Memory Configuration Data options atWord address 0x49
    if "OTPOSPISETTINGS" in sections:
        ospi_options = sections["OTPOSPISETTINGS"]
        otp_data_options, packed_integers = get_extmem_options(ospi_options)

        # hex_words = [f"0x{word:08X}" for word in packed_integers]
        # print(hex_words)
        if generate_script:
            sf.write("\n")
            dump_bitfield_details(sf, ospi_options, packed_integers)

            sf.write("\n# efuse Power enable\n")
            sf.write("memory set <verify=0>:0x7a60a004 32 0x30\n")
            sf.write("\n")

            sf.write("# Set OSPI OTP Settings\n")
            sf.write(
                "memory set <verify=0>:0x2F002124 0 0x%08X\n" % (packed_integers[0])
            )
            sf.write(
                "memory set <verify=0>:0x2F002128 0 0x%08X\n" % (packed_integers[1])
            )
            sf.write(
                "memory set <verify=0>:0x2F00212C 0 0x%08X\n" % (packed_integers[2])
            )
            # New Word 4, address is 0x2F00212C + 4 = 0x2F002130
            sf.write(
                "memory set <verify=0>:0x2F002130 0 0x%08X\n" % (packed_integers[3])
            )

            sf.write("\n# efuse Power disable\n")
            sf.write("memory set <verify=0>:0x7a60a004 32 0x10\n")

        ds.write(otp_data_options)
    else:
        print("[ERROR] No OSPI option specified")


def generate_altboot_data():
    cfgFile = "build/config/otp-altboot.json"
    print("[INFO] Configuration file: ", cfgFile)
    ospi_sections = read_json_file(cfgFile, SUPPORTED_ATTRIBUTES, SUPPORTED_BOOT_PATH)
    trace_print("[DBG] JSON Parse ", ospi_sections)

    process_otp_data(ospi_sections, generate_script=False)
