#!/usr/bin/env python3
# pylint: disable=invalid-name,superfluous-parens,anomalous-unicode-escape-in-string
# pylint: disable=import-error,wrong-import-position,wildcard-import,undefined-variable
"""
updateSystemPackage.py

"""
# TODO:
# check for online updates? Download and apply?

import os
import sys
import argparse
from pathlib import Path

from isp.serialport import serialPort
from isp.serialport import COM_BAUD_RATE_MAXIMUM

# import ispcommands
from isp.isp_core import *
from isp.isp_util import *
from isp import device_probe
import utils.config
from utils.config import *
from utils.ospi_mem_handler import OSPIMemoryHandler
from utils import paths

# Define Version constant for each separate tool
#  Version                  Feature
# 0.16.000     Addition of baud rate increase for bulk transfer
# 0.20.000     Removed JTAG access
# 0.21.000     Reset option set as default
# 0.21.001     Suppress maintenance mode output
# 0.21.002     Added python error exit code
# 0.22.000     Added support for multi-packages update (Alif's packages for different Part#/Revs)
#              also, removed A0 related-code
# 0.23.000     Added probe to detect the target and abort if Revision mismatches the selection
# 0.24.000     get baudrate from DBs
# 0.25.000     Added Part# and Revision Device's detection and offer to switch as defaults
# 0.26.000     Added support for MAC OS
# 0.26.001     Moved default parts and env checks to isp/device_probe.py
# 0.27.000     Added support for OSPI external memory
TOOL_VERSION = "0.27.000"

EXIT_WITH_ERROR = 1


def checkTargetWithSelection(targetDescription, targetRevision):
    """
    Check Target Device matches
    """
    partIsDifferent = False
    if targetDescription != DEVICE_PART_NUMBER:
        print("Connected target is not the default Part#")
        partIsDifferent = True

    if targetRevision != DEVICE_REVISION:
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


def main():
    """
    Start of it all...
    """
    global DEVICE_PART_NUMBER
    global DEVICE_REVISION

    if sys.version_info.major == 2:
        print("[ERROR] You need Python 3 for this application!")
        sys.exit(EXIT_WITH_ERROR)

    parser = argparse.ArgumentParser(
        description="Update System Package in MRAM/ext OSPI"
    )
    parser.add_argument(
        "-d",
        "--discover",
        action="store_true",
        default=False,
        help="COM port discovery for ISP",
    )
    parser.add_argument(
        "--port", type=str, help="Serial port device", default="/dev/ttyACM0"
    )
    parser.add_argument(
        "-b", "--baudrate", help="(isp) serial port baud rate", type=int
    )
    parser.add_argument(
        "-s",
        "--switch",
        help="(isp) dynamic baud rate switch toggle, default=on",
        action="store_false",
    )
    parser.add_argument(
        "-m",
        "--memory",
        action="store_true",
        help="update SERAM in external OSPI memory",
    )
    parser.add_argument(
        "-nr",
        "--no_reset",
        default=False,
        help="do not reset target before operation",
        action="store_true",
    )
    parser.add_argument(
        "-na",
        "--no_authentication",
        action="store_true",
        help="run in non-authenticated mode",
        default=False,
    )
    parser.add_argument(
        "-V", "--version", help="Display Version Number", action="store_true"
    )
    parser.add_argument("--cfg-part", type=str, help="Part Number")
    parser.add_argument("--cfg-rev", type=str, help="Part Revision", default="B4")
    parser.add_argument("--cfg-jtag", type=str, help="JTAG Interface", default="J-Link")
    parser.add_argument("--cfg-mram", type=str, help="MRAM Interface", default="isp")
    parser.add_argument("-v", "--verbose", help="verbosity mode", action="store_true")
    args = parser.parse_args()

    # Set paths.
    paths.TOOLKIT_DIR = Path(os.path.dirname(__file__))

    if args.version:
        print(TOOL_VERSION)
        sys.exit()

    # retrieve initial params based on user selection (toold-config)
    load_global_config(args.cfg_part, args.cfg_rev, args.cfg_jtag, args.cfg_mram)
    DEVICE_PART_NUMBER = utils.config.DEVICE_PART_NUMBER
    DEVICE_REVISION = utils.config.DEVICE_REVISION
    DEVICE_REV_BAUD_RATE = utils.config.DEVICE_REV_BAUD_RATE
    HASHES_DB = utils.config.HASHES_DB

    os.system("")  # Help MS-DOS window with ESC sequences

    print("Burning: System Package in MRAM")

    print("Selected Device:")
    print("Part# " + DEVICE_PART_NUMBER + " - Rev: " + DEVICE_REVISION)

    baud_rate = DEVICE_REV_BAUD_RATE[DEVICE_REVISION]
    if args.baudrate is not None:
        baud_rate = args.baudrate

    dynamic_baud_rate_switch = args.switch

    print("\nConnecting to the target device...")

    dynamic_string = "Enabled" if dynamic_baud_rate_switch else "Disabled"
    print("[INFO] baud rate ", baud_rate)
    print("[INFO] dynamic baud rate change ", dynamic_string)

    handler = CtrlCHandler()  # handle ctrl-c key press
    isp = serialPort(baud_rate)  # Serial dabbling open up port.

    if args.discover:  # discover the COM ports if requested
        isp.discoverSerialPorts()

    isp.setPort(args.port)
    errorCode = isp.openSerial()
    if errorCode is False:
        print("[ERROR] isp openSerial failed for %s" % isp.getPort())
        sys.exit(EXIT_WITH_ERROR)
    print("[INFO] %s open Serial port success" % isp.getPort())

    isp.setBaudRate(baud_rate)
    isp.setVerbose(args.verbose)

    # probe the device before update
    device = device_probe.device_get_attributes(isp)

    # check SERAM is the bootloader stage
    print("Bootloader stage: " + device_probe.STAGE_TEXT[device.stage])
    if device.stage != device_probe.STAGE_SERAM:
        print("[ERROR] Please use Recovery option from ROM menu in Maintenance Tool")
        sys.exit(EXIT_WITH_ERROR)

    if not args.no_reset:
        put_target_in_maintenance_mode(isp, baud_rate, args.verbose)

    print("[INFO] Detected Device:")
    partDetected = device.part_number

    print("Part# " + partDetected + " - Rev: " + device.revision)

    partDescription = getPartDescription(partDetected)

    # load configuration from detected device
    load_device_config(partDescription, device.revision)

    # retrieve rest of params from the detected device
    DEVICE_PACKAGE = utils.config.DEVICE_PACKAGE
    DEVICE_REV_PACKAGE_EXT = utils.config.DEVICE_REV_PACKAGE_EXT
    DEVICE_OFFSET = utils.config.DEVICE_OFFSET

    # check if SERAM update for external OSPI was requested
    if args.memory:
        print("[INFO] SERAM in external OSPI was requested")
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

    # check the default Part#/Rev in tools-config and offer to switch
    checkTargetWithSelection(partDescription, device.revision)

    env_ext = ""
    if device.env == "DEV":
        env_ext = "-dev"

    rev_ext = DEVICE_REV_PACKAGE_EXT[device.revision]

    packageName = DEVICE_PACKAGE
    offsetName = DEVICE_OFFSET
    # add suffix for external memory
    if args.memory:
        memType = getOspiMemTypeFromAddress(MEM_BASE_ADDRESS)
        if memType == "INVALID":
            close_isp_and_exit(isp, "[ERROR] invalid OSPI address")

        packageName += "-" + memType + "-" + str(int(MEM_SIZE / (1024 * 1024)))
        offsetName += "-" + memType + "-" + str(int(MEM_SIZE / (1024 * 1024)))

    alif_image = "alif/" + packageName + "-" + rev_ext + env_ext + ".bin"
    alif_offset = "alif/" + offsetName + "-" + rev_ext + env_ext + ".bin"

    print(f"- Package: {alif_image}")
    print(f"- Offset: {alif_offset}")

    alif_image = (paths.TOOLKIT_DIR / alif_image).as_posix()
    alif_offset = (paths.TOOLKIT_DIR / alif_offset).as_posix()

    if sys.platform in ["linux", "darwin"]:
        imageList = (
            alif_image
            + " "
            + hex(ALIF_BASE_ADDRESS)
            + " "
            + alif_offset
            + " "
            + hex(MEM_BASE_ADDRESS + MEM_SIZE - 16)
        )
    else:
        imageList = (
            alif_image
            + " "
            + hex(ALIF_BASE_ADDRESS)
            + alif_offset
            + " "
            + hex(MEM_BASE_ADDRESS + MEM_SIZE - 16)
        )

    # check images exist...
    if not os.path.exists(alif_image):
        print("Image " + alif_image + " does not exist!")
        sys.exit(EXIT_WITH_ERROR)

    if not os.path.exists(alif_offset):
        print("Image " + alif_offset + " does not exist!")
        sys.exit(EXIT_WITH_ERROR)

    # if ext OSPI is selected, and images exists, erase OSPI to continue
    if args.memory:
        # for now, OSPI sector size is fixed
        ospi = OSPIMemoryHandler(isp, ALIF_BASE_ADDRESS, MEM_SIZE, ERASE_SECTOR_SIZE_4K)
        ospi.erase_sectors()

    isp_start(isp)  # Start ISP Sequence

    if sys.platform in ["linux", "darwin"]:
        imageList = imageList.replace("\\", "/")
    else:
        imageList = imageList.replace("/", "\\")

    if dynamic_baud_rate_switch:
        isp_set_baud_rate(isp, COM_BAUD_RATE_MAXIMUM)  # Jack up Baud rate
        isp.setBaudRate(COM_BAUD_RATE_MAXIMUM)  # Sets the HOST baud rate

    # issue enquiry command to check if SERAM is in Maintenance Mode
    mode = isp_get_maintenance_status(isp)
    isp_show_maintenance_mode(isp, mode)

    authenticate = True if not args.no_authentication else False

    items = imageList.split(" ")
    for e in range(1, len(items), 2):
        addr = items[e]
        address = int(addr, base=16)
        fileName = items[e - 1]
        fileName = fileName.replace("..\\", "")

        if (
            burn_mram_isp(isp, handler, fileName, address, args.verbose, authenticate)
            == False
        ):
            break

    # Restore the default Baud rate
    if dynamic_baud_rate_switch:
        isp_set_baud_rate(isp, baud_rate)
        isp.setBaudRate(baud_rate)

    if not args.no_reset:
        isp_reset(isp)

    isp.closeSerial()


if __name__ == "__main__":
    main()
