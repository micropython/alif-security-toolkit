#!/usr/bin/env python3
# pylint: disable=invalid-name
"""
MRAM (NVM) burning / writing utility
Support
    - APPLICATION TOC package writing
    - image write at any address in NVM (MRAM)
    - image erase of any | range of addresses in NVM (MRAM)

__author__ = ""
__copyright__ = "ALIF Seminconductor"
__version__ = "0.16.0"
__status__ = "Dev"    "
"""

import os
import sys
import argparse

# Import local SETOOLS support
import utils.config
from utils.config import load_global_config, getPartDescription
from utils.user_validations import validateArgList

from isp.serialport import serialPort
from isp.serialport import COM_BAUD_RATE_MAXIMUM
from isp.isp_core import (
    CtrlCHandler,
    isp_get_maintenance_status,
    isp_mram_erase,
    isp_reset,
    isp_set_baud_rate,
    isp_show_maintenance_mode,
    isp_start,
    isp_stop,
)
from isp.isp_util import put_target_in_maintenance_mode, burn_mram_isp
from isp import device_probe

#  Version                  Feature
# 0.25.000     Revision and part# checks added (Target vs Host)
# 0.24.000     Removed JTAG support
# 0.23.000     Added probing to detect device stage/Part#/Rev
# 0.22.000     Added support for MAC OS (J-Link not included yet)
# 0.21.000     get baudrate from DBs
# 0.20.007     Added padding option for binaries not multiple of 16
# 0.20.006     Added Python error exit code
# 0.20.005     Fixed J-Link+Pylink issue writing binaries
# 0.20.004     REV_A0 dynamic baud rate support
# 0.20.003     remove maintenance mode output unless -v is used)
# 0.20.002     Reset option set as default
# 0.20.001     Added Erase option
# 0.20.000     Added option to skip user managed images
# 0.19.000     Removed JTAG access
# 0.16.000     Addition of baud rate increase for bulk transfer
# 0.15.000     Fixes for Block sizes and left overs
TOOL_VERSION = "0.25.000"  # Define Version constant for each separate tool

EXIT_WITH_ERROR = 1


def read_image_list(ds_file):
    """
    Read and extract image list from ARM-DS debug script command file.
    Parses the debug script file to extract the image list located between
    'args' and 'continue' markers.

    Args:
        ds_file (str): Path to the ARM-DS debug script file

    Returns:
        str: Extracted image list string from the debug script

    Raises:
        SystemExit: If file cannot be opened or if 'args'/'continue'
                    markers are not found in the file

    Example:
        image_list = read_image_list('bin/application_package.ds')
        read_image_list = read images from arm-ds command file
    """
    try:
        f = open(ds_file, "r")
        image_list = f.read()
        f.close()
        # search for image list
        start = image_list.find("args")
        end = image_list.find("continue")
        if start == -1 or end == -1:
            print(
                f'[ERROR] Debug Script malformed: missing "args" or '
                f'"continue" markers in {ds_file}'
            )
            sys.exit(EXIT_WITH_ERROR)
        image_list = image_list[start + 5 : end]
    except:  # pylint: disable=bare-except
        print(f"[ERROR] opening Debug Script file {ds_file}")
        sys.exit(EXIT_WITH_ERROR)

    return image_list


# pylint: disable=unused-argument
def app_mram_erase(isp, args, alif_base_address, alif_mram_size):
    """
    app_mram_erase
    - erase the Application are of MRAM
    args
    argv[0]    'erase'    Operation, can be ignored
    argv[1]    <address>  Starting address
    argv{2]    <size>     Length of bytes to erase
    argv[3]    <pattern>  Optional pattern to erase with
    argc                  Checked before this is called
    """
    if not args or not args.strip():
        print("[ERROR] erase arguments cannot be empty")
        return

    argv = args.split()
    argc = len(argv)
    if argc < 3:
        print("[ERROR] erase requires at least <address> and <size>")
        return

    # nombres magiques, maybe not needed?
    address = 0x80000000
    erase_len = 16
    pattern = 0x00000000

    if argc >= 3:
        address = int(argv[1], base=16)
        erase_len = int(argv[2], base=16)
        erase_len_fmt = "{:,}".format(erase_len)

        if argc == 4:
            pattern = int(argv[3], base=16)
            print(f"[INFO] {argv[0]} 0x{address:x} {erase_len} ({erase_len_fmt})")

        # Validate user request for erasing is in OEM
        if address > alif_base_address or address + erase_len > alif_base_address:
            if address + erase_len > alif_base_address:
                print(
                    f"[ERROR] illegal address {hex(address + erase_len)} "
                    f"({hex(address)} + {hex(erase_len)})"
                )
            else:
                print(f"[ERROR] illegal address {hex(address)}")
            return

        isp_mram_erase(isp, address, erase_len, pattern)


def confirm_or_exit(prompt_str):
    """
    Prompt user for confirmation and exit if not confirmed.

    Args:
        prompt_str: The prompt message to display to the user

    Returns:
        bool: True if user confirms (YES/Y), otherwise exits program
    """
    print(f"{prompt_str}")
    response = input("> ").strip().upper()

    if response in ["YES", "Y", "yes", "y"]:
        return True

    print("[INFO] Operation aborted\n")

    sys.exit(EXIT_WITH_ERROR)


def parse_arguments():
    """
    parse the command line arguments

    Args:
        none

    Returns:
        args list
    """
    parser = argparse.ArgumentParser(
        description="NVM Burner for Application TOC Package"
    )
    parser.add_argument("-b", "--baudrate", help="serial port baud rate", type=int)
    parser.add_argument(
        "-c", "--comport", type=str, default="COM3", help="Specify COM port"
    )
    parser.add_argument(
        "-d",
        "--discover",
        action="store_true",
        default=False,
        help="COM port discovery",
    )
    parser.add_argument(
        "--port", type=str, help="Serial port device", default="/dev/ttyACM0"
    )
    parser.add_argument(
        "-e",
        "--erase",
        type=str,
        help="ERASE [APP | <start address> <size> [<pattern>] ]",
    )
    # creating a mutually exclusive group for -i IMAGES and -S
    # (skip option doesn't make sense in a user provided list...)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-i",
        "--images",
        type=str,
        default="Application TOC Package",
        help="images list to burn into NVM "
        '("/path/image1.bin 0x80001000 /path/image2.bin 0x80003000")',
    )
    parser.add_argument(
        "-a",
        "--auth_image",
        action="store_true",
        help="authenticate the image by sending its signature file",
        default=False,
    )
    group.add_argument(
        "-S",
        "--skip",
        help="write ATOC only - skip user managed images",
        action="store_true",
    )
    parser.add_argument(
        "-s",
        "--switch",
        help="dynamic baud rate switch toggle, default=on",
        action="store_false",
    )
    parser.add_argument(
        "-p",
        "--pad",
        help="pad the binary if size is not multiple of 16",
        action="store_true",
    )
    parser.add_argument(
        "-nr",
        "--no_reset",
        default=False,
        help="do not reset target before operation",
        action="store_true",
    )
    parser.add_argument(
        "-V", "--version", help="Display Version Number", action="store_true"
    )
    parser.add_argument("--cfg-part", type=str, help="Part Number")
    parser.add_argument("--cfg-rev", type=str, help="Part Revision", default="B4")
    parser.add_argument("--cfg-jtag", type=str, help="JTAG Interface", default="J-Link")
    parser.add_argument("--cfg-mram", type=str, help="MRAM Interface", default="isp")
    parser.add_argument("-v", "--verbose", help="verbosity mode", action="store_true")

    return parser.parse_args()


def setup_configuration():
    """Load and return device configuration"""
    load_global_config()
    return {
        "part_number": utils.config.DEVICE_PART_NUMBER,
        "revision": utils.config.DEVICE_REVISION,
        "baud_rates": utils.config.DEVICE_REV_BAUD_RATE,
        "alif_base": utils.config.ALIF_BASE_ADDRESS,
        "oem_base": utils.config.APP_BASE_ADDRESS,
        "alif_size": utils.config.ALIF_MRAM_SIZE,
        "oem_size": utils.config.APP_MRAM_SIZE,
    }


def validate_python_version():
    """Ensure Python 3 is being used"""
    if sys.version_info.major == 2:
        print("[ERROR] You need Python 3 for this application!")
        sys.exit(EXIT_WITH_ERROR)


def main():
    """
    entry point to app-write-mram
    """
    validate_python_version()  # Check python version
    exit_code = 0

    # Deal with Command Line
    args = parse_arguments()
    if args.version:
        print(TOOL_VERSION)
        sys.exit()

    # memory defines for Alif/OEM MRAM Addresses and Sizes
    #    config = setup_configuration()
    load_global_config(args.cfg_part, args.cfg_rev, args.cfg_jtag, args.cfg_mram)
    DEVICE_PART_NUMBER = utils.config.DEVICE_PART_NUMBER
    DEVICE_REVISION = utils.config.DEVICE_REVISION
    DEVICE_REV_BAUD_RATE = utils.config.DEVICE_REV_BAUD_RATE
    ALIF_BASE_ADDRESS = utils.config.ALIF_BASE_ADDRESS
    OEM_BASE_ADDRESS = utils.config.APP_BASE_ADDRESS
    ALIF_MRAM_SIZE = utils.config.ALIF_MRAM_SIZE
    OEM_MRAM_SIZE = utils.config.APP_MRAM_SIZE

    os.system("")  # Help MS-DOS window with ESC sequences

    print("Writing MRAM with parameters:")
    print(f"Device Part# {DEVICE_PART_NUMBER} - Rev: {DEVICE_REVISION}")
    print(f"- Available MRAM: {OEM_MRAM_SIZE:,} bytes")

    baud_rate = DEVICE_REV_BAUD_RATE[DEVICE_REVISION]
    if args.baudrate is not None:
        baud_rate = args.baudrate

    dynamic_baud_rate_switch = args.switch

    arg_list = ""
    action = "Burning: "
    method = "isp"

    if args.erase:
        action = "Erasing: "
        arg_list = "erase "
        if args.erase.upper() == "APP":
            arg_list += hex(OEM_BASE_ADDRESS) + " " + hex(OEM_MRAM_SIZE)
        else:
            if args.erase.strip() == "":
                print("[ERROR] erase arguments are empty")
                sys.exit(EXIT_WITH_ERROR)
            arg_list += args.erase
    elif args.images == "Application TOC Package" or args.images.startswith("file:"):
        if args.images.startswith("file:"):
            dsFile = args.images.removeprefix("file:")
        else:
            dsFile = "bin/application_package.ds"
        arg_list = read_image_list(dsFile)
    else:
        arg_list = args.images

    if args.skip:
        idx = arg_list.find("build/AppTocPackage.bin 0x")
        arg_list = arg_list[idx : idx + 35]

    # validate all parameters
    arg_list = validateArgList(action, arg_list.strip(), args.pad)

    print("[INFO]", action + arg_list)

    if method == "jtag" and not args.erase:  # erase via jtag not yet supported!
        print("[ERROR] jtag is not supported")
        return  # end jlink tests

    if method == "jtag" and args.erase:  # erase via jtag not yet supported!
        print("[INFO] Erase is only supported via ISP")

    dynamic_string = "Enabled" if dynamic_baud_rate_switch else "Disabled"
    print(f"[INFO] baud rate {baud_rate} ")
    print("[INFO] dynamic baud rate change ", dynamic_string)

    handler = CtrlCHandler()
    isp = serialPort(baud_rate)  # Serial dabbling open up port.

    comport_override = False
    if args.comport != "COM3":
        isp.setPort(args.comport)
        comport_override = True
    isp.setVerbose(args.verbose)
    if args.discover and not comport_override:  # discover the COM ports if requested
        print("Discover")
        isp.discoverSerialPorts()

    isp.setPort(args.port)
    errorCode = isp.openSerial()
    if errorCode is False:
        print(f"[ERROR] isp openSerial failed for {isp.getPort()}")
        sys.exit(EXIT_WITH_ERROR)

    print(f"[INFO] {isp.getPort()} open Serial port success")

    isp.setBaudRate(baud_rate)

    # be sure device is not in SEROM Recovery Mode
    device = device_probe.device_get_attributes(isp)
    if device.stage != device_probe.STAGE_SERAM:
        print(
            "[ERROR] The device is in RECOVERY MODE! "
            "Please use Recovery option in Maintenance Tool to recover the device!"
        )
        sys.exit(EXIT_WITH_ERROR)

    # Probe the target device and check it matches the setings on the Host
    print("[INFO] Detected Device:")
    part_detected = device.part_number
    print(f"Part# {part_detected} - Rev:  {device.revision}")

    part_description = getPartDescription(part_detected)
    if part_description != DEVICE_PART_NUMBER:
        confirm_or_exit(
            f"[ERROR] ************ Configuration mismatch detected!\n"
            f"  Expected: {DEVICE_PART_NUMBER}\n"
            f"  Detected: {part_description}\n"
            f"Continue with operation [y/n]?"
        )

    if device.revision != DEVICE_REVISION:
        confirm_or_exit(
            f"[ERROR] ************ Part Revision mismatch detected!\n"
            f"  Expected: {DEVICE_REVISION}\n"
            f"  Detected: {device.revision}\n"
            f"Continue with operation [y/n]?"
        )

    if not args.no_reset:
        put_target_in_maintenance_mode(isp, baud_rate, args.verbose)

    if sys.platform in ["linux", "darwin"]:
        arg_list = arg_list.replace("\\", "/")
    else:
        arg_list = arg_list.replace("/", "\\")

    items = arg_list.split(" ")

    isp_start(isp)  # Start ISP Sequence

    if args.erase:
        app_mram_erase(isp, arg_list, ALIF_BASE_ADDRESS, ALIF_MRAM_SIZE)
    else:
        if dynamic_baud_rate_switch:
            isp_set_baud_rate(isp, COM_BAUD_RATE_MAXIMUM)  # Jack up Baud rate
            isp.setBaudRate(COM_BAUD_RATE_MAXIMUM)  # Sets the HOST baud rate

        # issue enquiry command to check if SERAM is in Maintenance Mode
        mode = isp_get_maintenance_status(isp)
        isp_show_maintenance_mode(isp, mode)

        for e in range(1, len(items), 2):
            addr = items[e]
            address = int(addr, base=16)
            fileName = items[e - 1]

            if (
                burn_mram_isp(
                    isp, handler, fileName, address, args.verbose, args.auth_image
                )
                is False
            ):
                exit_code = EXIT_WITH_ERROR
                break

        # Restore the default Baud rate
        if dynamic_baud_rate_switch:
            isp_set_baud_rate(isp, baud_rate)
            isp.setBaudRate(baud_rate)

    isp_stop(isp)  # Stop ISP Sequence
    isp_reset(isp)

    isp.closeSerial()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
