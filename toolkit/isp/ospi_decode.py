#!/usr/bin/python3
"""
@brief OSPI parameters decode and display

__author__ onyettr
"""

# pylint: disable=unused-argument, invalid-name, consider-using-f-string
from isp_print import isp_print_color
from version_decode import display_string

SERAM_LOADING_OPTS_LUT = {
    0: "MRAM Only",
    1: "MRAM then Ext Memory",
    2: "External Memory Only",
    3: "Invalid",
}

SERAM_LOADING_MEMORY_TYPE = {
    0: "OSPI Flash 8bit in XIP Mode",
    1: "OSPI Flash 8bit in SPI mode",
    2: "NAND Flash 8bit in burst mode",
    3: "SPI  Flash 1bit in serial mode",
}

FLASH_SIZE_LUT = {0: "32 MB", 1: "64 MB", 2: "128MB", 3: "256MB", 4: "512MB"}
OSPI0_A_PINMUX_SELECT = 0x00
OSPI0_B_PINMUX_SELECT = 0x01
OSPI0_C_PINMUX_SELECT = 0x02
OSPI1_A_PINMUX_SELECT = 0x03
OSPI1_B_PINMUX_SELECT = 0x04
OSPI1_C_PINMUX_SELECT = 0x05

OSPI_SETTINGS_PINUMUX_LUT = {
    OSPI0_A_PINMUX_SELECT: "OSPI0_A_PINMUX_SELECT",
    OSPI0_B_PINMUX_SELECT: "OSPI0_B_PINMUX_SELECT",
    OSPI0_C_PINMUX_SELECT: "OSPI0_C_PINMUX_SELECT",
    OSPI1_A_PINMUX_SELECT: "OSPI1_A_PINMUX_SELECT",
    OSPI1_B_PINMUX_SELECT: "OSPI1_B_PINMUX_SELECT",
    OSPI1_C_PINMUX_SELECT: "OSPI1_C_PINMUX_SELECT",
}


def print_binary(binary_value):
    """ """
    bits = ""
    while binary_value:
        bits += str(binary_value % 2)
        binary_value = binary_value >> 1

    return "0" + bits[::-1]


def ospi_data_decode(message):
    """
    ospi_data_decode
    show OSPI details
    """

    # Extract the SERAM Loading Options from offset 0x44
    otp_value = int.from_bytes(message[2:6], "little")
    #    print(hex(otp_value))
    otp_value = (otp_value & 0xFFFF0000) >> 16
    #    print(hex(otp_value))

    # Byte offset 0x112 contains the Special Alternate SERAM loading options
    # Alternate SERAM loading options Bits [0:1]
    seram_loading_options = otp_value & 0x3
    isp_print_color("blue", " SES Alt Load\t=  ")
    display_string(message[2:6])
    isp_print_color(
        "blue",
        #                    "\tLoading options      : %s %s\n" %
        #                    (print_binary(seram_loading_options),
        "\tLoading options      : 0x%X %s\n"
        % (seram_loading_options, SERAM_LOADING_OPTS_LUT.get(seram_loading_options)),
    )
    # If nothing set, then this device is MRAM only so do not decode
    # any further
    if seram_loading_options != 0x0:
        # Byte offset 0x112: External Memory Type Bits[8:11]
        external_memory_type = (otp_value & 0xF00) >> 8
        isp_print_color(
            "blue",
            #                      "\tExt Memory type      : %s %s\n" %
            #                      (print_binary(external_memory_type),
            "\tExt Memory type      : 0x%X %s\n"
            % (
                external_memory_type,
                SERAM_LOADING_MEMORY_TYPE.get(external_memory_type),
            ),
        )

    # External Memory Configuration data decode.
    print("")
    isp_print_color("blue", " SES Ext Conf\t=  ")
    display_string(message[6:21])
    ses_ext_conf = message[6:21]

    #
    # Decode the packet data back into OTP settings
    # @TODO do this as Words instead of bytes?
    #
    # Word0 Bytes[0],{1],[2].[3}
    rx_sample_delay = ses_ext_conf[0]
    xip_incr_inst = ses_ext_conf[1]
    xip_wrap_inst = ses_ext_conf[2]
    aes_rxds_delay = ses_ext_conf[3]

    # Word1 Byte[0]
    ddr_drive_edge = ses_ext_conf[4]

    pinmux_sel = (ses_ext_conf[5]) & 0x07
    bus_speed_sel = ((ses_ext_conf[5]) >> 3) & 0x07
    fast_read_wait_cycles_low = (ses_ext_conf[5] >> 6) & 0x03
    fast_read_wait_cycles_high = ses_ext_conf[6] & 0x03
    fast_read_wait_cycles = (
        fast_read_wait_cycles_high << 2
    ) | fast_read_wait_cycles_low
    flash_size = (ses_ext_conf[6] >> 2) & 0x07
    valid = (ses_ext_conf[6] >> 5) & 0x01
    reset_port_low = (ses_ext_conf[6] >> 6) & 0x03
    reset_port_high = ses_ext_conf[7] & 0x07
    reset_port = (reset_port_high << 2) | reset_port_low
    reset_pin = (ses_ext_conf[7] >> 3) & 0x07
    spi_mode = (ses_ext_conf[7] >> 6) & 0x07

    # Word2
    io_mode = (ses_ext_conf[8]) & 0x03
    ddr_en = (ses_ext_conf[8] >> 2) & 0x01
    xip_ddr_en = (ses_ext_conf[8] >> 3) & 0x01
    inst_ddr_en = (ses_ext_conf[8] >> 4) & 0x01
    xip_inst_ddr_en = (ses_ext_conf[8] >> 5) & 0x01
    rxds_en = (ses_ext_conf[8] >> 6) & 0x01
    rxds_vl_en = (ses_ext_conf[8] >> 7) & 0x01

    rxds_vl_en = (ses_ext_conf[9]) & 0x1
    #    dfs_low         = (ses_ext_conf[9] >> 1) & 0x7F  # Byte[9]
    #    dfs_high        = (ses_ext_conf[10]) & 0x03
    #    dfs             = (dfs_high << 7) | dfs_low
    #    dfs             = dfs & 0x1F
    dfs = (ses_ext_conf[9] >> 1) & 0x1F
    xip_dfs_low = (ses_ext_conf[9]) & 0x3
    xip_dfs_high = ses_ext_conf[10] & 0x07
    xip_dfs = (xip_dfs_low << 2) | xip_dfs_high

    xip_rxds_en = (ses_ext_conf[10] >> 3) & 0x01
    xip_instr_len = (ses_ext_conf[10] >> 4) & 0x03
    xip_addr_len_low = (ses_ext_conf[10] >> 6) & 0x03
    xip_addr_len_hig = (ses_ext_conf[11]) & 0x03
    xip_addr_len = xip_addr_len_low | (xip_addr_len_hig << 2)

    xip_spi_mode = (ses_ext_conf[11] >> 2) & 0x03
    xip_hyperbus_en = (ses_ext_conf[11] >> 4) & 0x01
    tx_wait_count = (ses_ext_conf[11] >> 5) & 0x3

    # test if anything is programmed into OTP
    if valid & 0x1 == 0:
        return

    isp_print_color("blue", "\trx_sample_delay      : 0x%X\n" % (rx_sample_delay))
    isp_print_color("blue", "\txip_incr_inst        : 0x%X\n" % (xip_incr_inst))
    isp_print_color("blue", "\txip_wrap_inst        : 0x%X\n" % (xip_wrap_inst))
    isp_print_color("blue", "\taes_rxds_delay       : 0x%X\n" % (aes_rxds_delay))
    isp_print_color("blue", "\tddr_drive_edge       : 0x%X\n" % (ddr_drive_edge))
    isp_print_color("blue", "\tpinmux_sel           : 0x%X\n" % pinmux_sel)
    isp_print_color("blue", "\tbus_speed_sel        : 0x%X\n" % bus_speed_sel)
    isp_print_color("blue", "\tfast_read_wait_cycles: 0x%X\n" % fast_read_wait_cycles)
    isp_print_color(
        "blue",
        "\tflash_size           : 0x%X\t%s\n"
        % (flash_size, FLASH_SIZE_LUT.get(flash_size)),
    )
    isp_print_color("blue", "\tvalid                : 0x%X\n" % valid)
    isp_print_color("blue", "\treset_port           : 0x%X\n" % reset_port)
    isp_print_color("blue", "\treset_pin            : 0x%X\n" % reset_pin)
    isp_print_color("blue", "\tspi_mode             : 0x%X\n" % spi_mode)
    isp_print_color("blue", "\tio_mode              : 0x%X\n" % io_mode)
    isp_print_color("blue", "\tddr_en               : 0x%X\n" % ddr_en)
    isp_print_color("blue", "\txip_ddr_en           : 0x%X\n" % xip_ddr_en)
    isp_print_color("blue", "\tinst_ddr_en          : 0x%X\n" % inst_ddr_en)
    isp_print_color("blue", "\txip_inst_ddr_en      : 0x%X\n" % xip_inst_ddr_en)
    isp_print_color("blue", "\trxds_en              : 0x%X\n" % rxds_en)
    isp_print_color("blue", "\trxds_vl_en           : 0x%X\n" % rxds_vl_en)
    isp_print_color("blue", "\tdfs                  : 0x%X\n" % dfs)
    isp_print_color("blue", "\txip_dfs              : 0x%X\n" % xip_dfs)
    isp_print_color("blue", "\txip_rxds_en          : 0x%X\n" % xip_rxds_en)
    isp_print_color("blue", "\txip_instr_len        : 0x%X\n" % xip_instr_len)
    isp_print_color("blue", "\txip_addr_len         : 0x%X\n" % xip_addr_len)
    isp_print_color("blue", "\txip_spi_mode         : 0x%X\n" % xip_spi_mode)
    isp_print_color("blue", "\txip_hyperbus_en      : 0x%X\n" % xip_hyperbus_en)
    isp_print_color("blue", "\ttx_wait_count        : 0x%X\n" % tx_wait_count)
