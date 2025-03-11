#!/usr/bin/env python3
"""
recovery.py

Support
    - SEROM Recovery mode
    - Allows updating of the MRAM through SEROM
    - This is always ISP mode.
__author__ = ""
__copyright__ = "ALIF Seminconductor"
__version__ = "0.1.0"
__status__ = "Dev"

TODO:
- baud rate should be set to the SEROM default
"""

# pylint: disable=unused-argument, invalid-name, bare-except
import sys

from isp.isp_protocol import *
from isp.isp_core import *
from isp.isp_util import *
import utils.config
from utils.config import *
from utils.user_validations import validateArgList
from utils.ospi_mem_handler import OSPIMemoryHandler
from isp import device_probe
import time

# Probe error codes
PROBE_OK = 0
PROBE_SEROM = 1
PROBE_SERAM = 2
PROBE_NO_MESSAGE = 3

BRING_UP_MODE = 1


def write_memory(isp, fileName, destAddress, verbose_display, ext_ospi=False):
    """
    write_memory - use ISP method to write MRAM and OSPI memories
    """
    if verbose_display:
        print(f"[DEBUG] Starting write_memory for file: {fileName}")
        print(f"[DEBUG] Destination address (hex string): {hex(destAddress)}")

    try:
        f = open(fileName, "rb")

    except IOError as e:
        # Assuming close_isp_and_exit is a function that handles termination
        close_isp_and_exit(isp, "[ERROR] {0}".format(e))

    # Using 'with f:' ensures the file is closed automatically
    with f:
        fileSize = file_get_size(f)
        if verbose_display:
            print(f"[DEBUG] File size: {fileSize:#x} bytes ({fileSize} decimal)")

        offset = 0
        data_size = 16

        if verbose_display:
            print(f"[DEBUG] Calculated memory-relative offset: {destAddress:#x}")

        start_time = time.time()

        # --- ROBUST LOOP LOGIC: Ensure ALL bytes are written (fixes last block skip) ---
        while offset < fileSize:
            f.seek(offset)

            # Read 16 bytes, or fewer if it's the very last part of the file
            bytes_to_read = min(data_size, fileSize - offset)
            mram_line = f.read(bytes_to_read)

            if not mram_line:
                break

            if verbose_display is False:
                # Progress bar reflects actual offset and total size
                progress_bar(fileName, offset + len(mram_line), fileSize)
            else:
                # Print debug info with actual size and data
                print(
                    f"[DEBUG] Writing block at offset {hex(destAddress)}, size {len(mram_line)}, data: {mram_line.hex()}"
                )

            if ext_ospi:
                isp_ospi_write(isp, destAddress, mram_line)
            else:
                isp_mram_write(isp, destAddress, mram_line)

            # Increment by the actual number of bytes written
            increment = len(mram_line)
            offset += increment
            destAddress += increment

            if isp.CTRLCHandler.Handler_exit():
                close_isp_and_exit(
                    isp, "[INFO] CTRL-C detected. User aborted this process"
                )
        # --- END ROBUST LOOP ---

        end_time = time.time()
        print("\r")  # Print carriage return once after the loop finishes

        if verbose_display is False:
            print(f"[INFO] recovery time: {end_time - start_time:10.2f} seconds")

        if verbose_display:
            print(f"[DEBUG] Finished write_memory for file: {fileName}")

    f.close()


def checkTargetWithSelection(
    targetDescription, targetRevision, selectedDescription, selectedRevision
):
    """
    Check target selection
    """
    partIsDifferent = False
    if targetDescription != selectedDescription:
        print("Connected target is not the default Part#")
        partIsDifferent = True

    if targetRevision != selectedRevision:
        print("Connected target is not the default Revision")
        partIsDifferent = True

    if partIsDifferent:
        try:
            answer = input("Do you want to set this part as default? (y/n): ")
        except EOFError as e:
            print("\nUser aborted the process")
            sys.exit()

        if answer.lower() == "y" or answer.lower() == "yes":
            save_global_config(targetDescription, targetRevision)


def recovery_core(isp, ext_ospi=False):
    """
    The recovery logic
    """
    # probe the device before update
    device = device_probe.device_get_attributes(isp)

    # check SERAM is the bootloader stage
    print("Bootloader stage: " + device_probe.STAGE_TEXT[device.stage])
    if device.stage == device_probe.STAGE_SERAM:
        close_isp_and_exit(
            isp, "[ERROR] Device not in Recovery mode, use updateSystemPackage Tool"
        )

    # selected device from global-cfg.db
    selectedDescription = utils.config.DEVICE_PART_NUMBER
    selectedRevision = utils.config.DEVICE_REVISION

    # print detected device
    print("Detected Part#: " + device.part_number)
    print("Detected Revision: " + device.revision)
    partDescription = getPartDescription(device.part_number)
    # load configuration from detected device
    load_device_config(partDescription, device.revision)
    # check the default Part#/Rev in tools-config and offer to switch
    checkTargetWithSelection(
        partDescription, device.revision, selectedDescription, selectedRevision
    )

    # update params from either selected part (B2) or detected part (B3/B4, etc)
    DEVICE_PART_NUMBER = utils.config.DEVICE_PART_NUMBER
    DEVICE_REVISION = utils.config.DEVICE_REVISION
    DEVICE_PACKAGE = utils.config.DEVICE_PACKAGE
    DEVICE_REV_PACKAGE_EXT = utils.config.DEVICE_REV_PACKAGE_EXT
    DEVICE_OFFSET = utils.config.DEVICE_OFFSET
    HASHES_DB = utils.config.HASHES_DB

    # check if OSPI Recovery was requested
    if ext_ospi:
        print("[INFO] OSPI Recovery requested")
        # check if device supports OSPI and if it's enabled in OTP
        if device.supports_ospi:
            print("[INFO] Device supports OSPI external memory")
            if device.is_ospi_enabled(isp):
                print("[INFO] OSPI is enabled in OTP")
            else:
                print("[INFO] OSPI is NOT enabled in OTP")
                close_isp_and_exit(isp, "[ERROR] OSPI is not enabled in OTP")
        else:
            close_isp_and_exit(
                isp,
                "[ERROR] OSPI Recovery mode requested, but device does not support OSPI memory",
            )
        # retrieve OSPI parameters
        MEM_BASE_ADDRESS, MEM_SIZE, ALIF_BASE_ADDRESS, EXT_MEMORY_TYPE = (
            device.get_ospi_params()
        )
    else:
        # set MRAM params
        print("[INFO] SERAM in MRAM memory")
        MEM_BASE_ADDRESS = utils.config.MRAM_BASE_ADDRESS
        ALIF_BASE_ADDRESS = utils.config.ALIF_BASE_ADDRESS
        MEM_SIZE = utils.config.MRAM_SIZE

    print(
        f"ALIF_BASE_ADDRESS {hex(ALIF_BASE_ADDRESS)} alif_offset {hex(MEM_BASE_ADDRESS + MEM_SIZE - 16)}"
    )

    # -----------------------
    # Print recovery parameters
    # -----------------------
    print("[INFO] System TOC Recovery with parameters:")
    print(f"- Device Part# {DEVICE_PART_NUMBER} - Rev: {DEVICE_REVISION}")
    if ext_ospi:
        print(f"- OSPI Base Address: {hex(MEM_BASE_ADDRESS)}")
        print(f"- OSPI Size: {hex(MEM_SIZE)}")
    else:
        print(f"- ALIF Base Address: {hex(ALIF_BASE_ADDRESS)}")

    argList = ""
    action = "Burning: "

    env_ext = ""
    if device.env == "DEV":
        env_ext = "-dev"

    rev_ext = DEVICE_REV_PACKAGE_EXT[device.revision]

    packageName = DEVICE_PACKAGE
    offsetName = DEVICE_OFFSET
    # add suffix for external memory
    if ext_ospi:
        memType = getOspiMemTypeFromAddress(MEM_BASE_ADDRESS)
        if memType == "INVALID":
            close_isp_and_exit(isp, "[ERROR] invalid OSPI address")

        packageName += "-" + memType + "-" + str(int(MEM_SIZE / (1024 * 1024)))
        offsetName += "-" + memType + "-" + str(int(MEM_SIZE / (1024 * 1024)))

    alif_image = "alif/" + packageName + "-" + rev_ext + env_ext + ".bin"
    alif_offset = "alif/" + offsetName + "-" + rev_ext + env_ext + ".bin"

    print(f"- Package: {alif_image}")
    print(f"- Offset: {alif_offset}")

    # -----------------------
    # Check files exist
    # -----------------------
    if not os.path.exists(alif_image):
        close_isp_and_exit(isp, f"[ERROR] Image {alif_image} does not exist!")

    if not os.path.exists(alif_offset):
        close_isp_and_exit(isp, f"[ERROR] Image {alif_offset} does not exist!")

    if ext_ospi:
        # Erase OSPI before writing
        ospi = OSPIMemoryHandler(isp, ALIF_BASE_ADDRESS, MEM_SIZE, ERASE_SECTOR_SIZE_4K)
        ospi.erase_sectors()

        # Calculate the OSPI-relative address for writing
        ospi_relative_address = ALIF_BASE_ADDRESS - MEM_BASE_ADDRESS
        print(
            f"[INFO] Writing main OSPI image '{alif_image}' to address {hex(ospi_relative_address)}"
        )
        write_memory(isp, alif_image, ospi_relative_address, False, True)

        ospi_relative_address = MEM_SIZE - 16
        print(
            f"[INFO] Writing offset '{alif_offset}' to address {hex(ospi_relative_address)}"
        )
        write_memory(isp, alif_offset, ospi_relative_address, False, True)
    else:
        mram_relative_address = ALIF_BASE_ADDRESS - MEM_BASE_ADDRESS
        print(
            f"[INFO] Writing main MRAM image '{alif_image}' to address {hex(mram_relative_address)}"
        )
        write_memory(isp, alif_image, mram_relative_address, False, False)

        mram_relative_address = MEM_SIZE - 16
        print(
            f"[INFO] Writing offset '{alif_offset}' to address {hex(mram_relative_address)}"
        )
        write_memory(isp, alif_offset, mram_relative_address, False, False)


def recovery_end_exit():
    print("Recovery process finished. Please reload maintenance tool for verification")
    sys.exit(0)


# Entry points for recovery actions (from SEROM Recovery menu)
def recovery_action_no_reset(isp):
    recovery_core(isp)
    recovery_end_exit()


def recovery_action(isp):
    recovery_core(isp)
    print("[INFO] Target reset")
    isp_reset(isp)  # Reset the target
    recovery_end_exit()


def recovery_ospi_action_no_reset(isp):
    """
    Recover OSPI via SEROM. Do not reset the device at the end.
    """
    recovery_core(isp, True)
    recovery_end_exit()
