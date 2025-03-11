#!/usr/bin/env python3
"""
device_probe.py
discovery class for finding out what is on the other end of the SE-UART
"""

import struct

from isp.isp_core import isp_start
from isp.isp_core import isp_stop
from isp.isp_core import isp_build_packet
from isp.isp_util import close_isp_and_exit
from utils.config import (
    ALIF_EAGLE_OSPI_PACKAGE_SIZE,
    HASHES_DB_FILE,
    OSPI0_MEM_ADDRESS,
    OSPI1_MEM_ADDRESS,
    read_global_config,
)

# from utils.toc_common import ALIF_PACKAGE_SIZE
from isp.isp_protocol import ISP_COMMAND_DATA_RESPONSE
from isp.isp_protocol import ISP_COMMAND_ENQUIRY
from isp.isp_protocol import ISP_COMMAND_GET
from isp.isp_protocol import ISP_PACKET_DATA_FIELD
from isp.isp_protocol import ISP_PACKET_COMMAND_FIELD
from isp.isp_protocol import ISP_SOURCE_SEROM
from isp.isp_protocol import ISP_SOURCE_SERAM
from isp.isp_protocol import ISP_GET_REVISION
from isp.isp_protocol import ISP_GET_OSPI_PARAMETERS

# definitions

REVISIONS = {
    "0 0 0 0": ("UNKNOWN", "UNKNOWN"),
    "0 161 0 0": ("FUSION", "A1"),
    "0 165 0 0": ("SPARK", "A5"),
    "0 176 0 0": ("FUSION", "B0"),
    "0 178 0 0": ("FUSION", "B2"),
    "0 179 0 0": ("FUSION", "B3"),
    "0 180 0 0": ("FUSION", "B4"),
    "1 160 0 0": ("SPARK", "A0"),
    "1 165 0 0": ("SPARK", "A5"),
    "160 2 0 0": ("EAGLE", "A0"),
    "160 3 0 0": ("EAGLE", "FPGA_A0"),
    "161 2 0 0": ("EAGLE", "A1"),
    "161 3 0 0": ("EAGLE", "FPGA_A1"),
}

# bootloader stages
STAGE_UNKNOWN = 0
STAGE_SEROM = 1
STAGE_SERAM = 2
STAGE_TEXT = ["UNKNOWN", "SEROM", "SERAM"]

# External Memory Type LUT
SERAM_LOADING_MEMORY_TYPE = {
    0: "OSPI Flash 8bit in XIP Mode",
    1: "OSPI Flash 8bit in SPI mode",
    2: "NAND Flash 8bit in burst mode",
    3: "SPI  Flash 1bit in serial mode",
}

EXPECTED_PACKET_LENGTH = 136


class device_get_attributes:
    """device_get_attributes"""

    # attributes from the device
    feature = "UNKNOWN"
    part_number = "PART_UNKNOWN"
    revision = "UNKNOWN"
    supports_ospi = "UNKNOWN"
    stage = STAGE_UNKNOWN
    env = "UNKNOWN"  # DEV or PROD environment

    # extended attributes for external ospi memory
    ospi_loading_enabled = False
    ospi_base_address = 0
    osp_size = 0
    alif_base_address = 0
    ext_memory_type = "UNKNOWN"

    def __init__(self, isp):
        """
        ctor
        """
        self.isp = isp
        self.feature = "UNKNOWN"
        self.part_number = "PART_UNKNOWN"
        self.revision = "UNKNOWN"
        self.supports_ospi = "UNKNOWN"
        self.stage = STAGE_UNKNOWN
        self.env = "UNKNOWN"

        # retrieve device revision
        self.feature, self.revision, self.part_number, self.env = (
            self.__get_device_info(isp)
        )
        # probe and set device bootloader stage
        self.stage = self.__get_device_stage(isp)
        # check if device supports external OSPI memory
        if self.feature == "EAGLE":
            self.supports_ospi = True
        else:
            self.supports_ospi = False

    def get_attributes(self):
        """
        Returns all device attributes as a dictionary.
        """
        return {
            "part_number": self.part_number,
            "revision": self.revision,
            "supports_ospi": self.supports_ospi,
            "stage": self.stage,
            "environment": self.env,
        }

    def get_part_number(self):
        """Returns the device part number."""
        return self.part_number

    def get_revision(self):
        """Returns the device silicon revision."""
        return self.revision

    def get_stage(self):
        """Returns the current bootloader stage."""
        return self.stage

    def get_environment(self):
        """Returns the device environment (DEV/PROD)."""
        return self.env

    def __get_device_info(self, isp):
        """
        obtain the SoC Device information
        """
        isp_start(isp)
        rev = "ERROR"
        message = isp_build_packet(isp, ISP_COMMAND_GET, [ISP_GET_REVISION])

        if not message:
            close_isp_and_exit(isp, "[ERROR] Target did not respond")

        if (
            len(message) != EXPECTED_PACKET_LENGTH
            or message[0] != EXPECTED_PACKET_LENGTH
        ):
            close_isp_and_exit(isp, "[ERROR] Malformed packet received from target")

        cmd = message[ISP_PACKET_COMMAND_FIELD]
        if cmd == ISP_COMMAND_DATA_RESPONSE:
            # silicon revision
            lst = message[2:6]
            rev1 = " ".join(map(str, lst))
            (version,) = struct.unpack("<I", bytes(message[2:6]))
            try:
                rev = REVISIONS[rev1]
            except:
                close_isp_and_exit(
                    isp, "[ERROR] Unknown device revision 0x%04X" % (version)
                )

            feature = rev[0]
            rev = rev[1]
            # device Part#
            lst = message[6:22]
            ascii_list = [chr(ch) for ch in lst]
            part_number = "".join(ascii_list)
            # Check for Blank devices
            # These should not exist! but initial devices for bring up are always Blank
            if (
                bytes(part_number, "utf-8")
                == b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            ):
                if feature == "SPARK":
                    part_number = "AB1C1F4M51820PH0"  # SPARK default device
                elif feature == "EAGLE":
                    part_number = "AE822FA0E5597LS0"  # EAGLE default device
                else:
                    part_number = "AE722F80F55D5LS"  # FUSION default device
                print("[WARN] No Part# was detected! Defaulting to " + part_number)

            # HBK0
            lst = message[22:38]
            hbk0 = ""
            for ch in lst:
                l = hex(ch)[2:]
                if len(l) == 1:
                    l = "0" + l
                hbk0 += l
            hbk0 = hbk0.lower()

            # read hashes DB
            HASHES_DB = read_global_config(HASHES_DB_FILE)
            env = "PROD"
            if hbk0 in HASHES_DB:
                env = HASHES_DB[hbk0]

            # for devices in CM LCS, we use the DEV package
            if hbk0 == "00000000000000000000000000000000":
                print("[WARN] Device is not provisioned!")
                env = "DEV"

        isp_stop(isp)
        return feature, rev, part_number, env

    def __get_device_stage(self, isp):
        """
        Return target source mode from Enquiry
        - Find out the device bootloader stage
        """
        probe_result = STAGE_UNKNOWN

        isp_start(isp)
        message = isp_build_packet(isp, ISP_COMMAND_ENQUIRY)

        if not message:
            print("[ERROR] Target did not respond")
            return probe_result

        cmd = message[ISP_PACKET_COMMAND_FIELD]

        if cmd == ISP_COMMAND_DATA_RESPONSE:
            state = message[ISP_PACKET_DATA_FIELD]
            if state & ISP_SOURCE_SEROM:
                probe_result = STAGE_SEROM
            if state & ISP_SOURCE_SERAM:
                probe_result = STAGE_SERAM
        isp_stop(isp)

        return probe_result

    def is_ospi_enabled(self, isp):
        """
        Check if OSPI memory loading is enabled
        - only for devices that support OSPI
        """

        """
            isp_get_ospi parameters
        """
        if self.supports_ospi != True:
            return False

        isp_start(isp)
        message = isp_build_packet(isp, ISP_COMMAND_GET, [ISP_GET_OSPI_PARAMETERS])

        if len(message) == 0:
            return
        cmd = message[ISP_PACKET_COMMAND_FIELD]

        if cmd == ISP_COMMAND_DATA_RESPONSE:
            # Extract the SERAM Loading Options from offset 0x44
            otp_value = int.from_bytes(message[2:6], "little")
            otp_value = (otp_value & 0xFFFF0000) >> 16

            # Byte offset 0x112 contains the Special Alternate SERAM loading options
            # Alternate SERAM loading options Bits [0:1]
            seram_loading_options = otp_value & 0x3

            # If nothing set, then this device is MRAM only so do not decode
            # any further
            if seram_loading_options > 0x00:
                self.ospi_loading_enabled = True
                # Byte offset 0x112: External Memory Type Bits[8:11]
                external_memory_type = (otp_value & 0xF00) >> 8
                self.ext_memory_type = SERAM_LOADING_MEMORY_TYPE.get(
                    external_memory_type, "UNKNOWN"
                )
                # External Memory Configuration data decode.
                ses_ext_conf = message[6:21]
                flash_size = (ses_ext_conf[6] >> 2) & 0x07
                self.osp_size = 32 * 1024 * 1024 * pow(2, flash_size)  # in bytes

                # ospi channel
                pinmux_sel = (ses_ext_conf[5]) & 0x07
                if pinmux_sel > 2:
                    # pinmux_sel = [3..5] => ospi1
                    self.ospi_base_address = OSPI1_MEM_ADDRESS
                else:
                    # pinmux_sel = [0..2] => ospi0
                    self.ospi_base_address = OSPI0_MEM_ADDRESS

                # ALIF base address
                self.alif_base_address = (
                    self.ospi_base_address
                    + self.osp_size
                    - ALIF_EAGLE_OSPI_PACKAGE_SIZE
                )

        isp_stop(isp)
        return self.ospi_loading_enabled

    def get_ospi_params(self):
        """
        Returns OSPI parameters: base address, size, ALIF base address
        """
        return (
            self.ospi_base_address,
            self.osp_size,
            self.alif_base_address,
            self.ext_memory_type,
        )

    def is_in_serom(self):
        """Returns True if device is in SEROM stage."""
        return self.stage == STAGE_SEROM

    def is_in_seram(self):
        """Returns True if device is in SERAM stage."""
        return self.stage == STAGE_SERAM

    def get_stage_name(self):
        """Returns human-readable stage name."""
        stage_names = {
            STAGE_SEROM: "Secure ROM",
            STAGE_SERAM: "Secure RAM",
            STAGE_UNKNOWN: "Unknown",
        }
        return stage_names.get(self.stage, "Unknown")

    def is_provisioned(self):
        """
        Check if device is provisioned (not in CM LCS state).
        Returns True if provisioned, False otherwise.
        """
        blank_hbk0 = "00000000000000000000000000000000"
        return self.env != "DEV" or self.__hbk0 != blank_hbk0

    def is_production_device(self):
        """Returns True if device is a production device."""
        return self.env == "PROD"

    def is_development_device(self):
        """Returns True if device is a development device."""
        return self.env == "DEV"
