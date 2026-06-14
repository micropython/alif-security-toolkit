#!/usr/bin/env python3
"""
 tools-config

 Configure defaults for SETOOLS

__author__
"""
# pylint: disable=invalid-name,superfluous-parens,anomalous-unicode-escape-in-string

import sys
import os
import argparse
import shutil
import json
from json.decoder import JSONDecodeError

sys.path.append("./isp")
# pylint: disable=wrong-import-position,import-error
from serialport import serialPort  # ISP Serial support
from isp_core import isp_test_target, CtrlCHandler
import device_probe
from utils.config import DEVICE_REVISION, DEVICE_REV_BAUD_RATE
from utils.config import load_global_config, getPartDescription
from utils.gen_fw_cfg import gen_fw_cfg_icv, FW_CFG_FILE
import utils.toc_common

# Define Version constant for each separate tool
# 0.05.000 - add cmd line options and multiple key directories
# 0.06.000 - add new DEV key for SPARK
# 0.07.000 - fixed SE-2761 (keyEnv is not being updated in Azure)
# 0.08.000 - removed default value for keyEnv, added case for EAGLE FPGA_A0
# 0.09.000 - auto-configuration mode added (which selects the Part# and Rev with detected target device)
TOOL_VERSION = "0.09.000"

EXIT_WITH_ERROR = 1
TARGET_RESPONDED = 1
TARGET_NOT_RESPONDED = -1

CONFIG_FILE = "utils/global-cfg.db"
FAMILY_DB = "utils/familiesDB.db"
FEATURES_DB = "utils/featuresDB.db"
DEVICE_DB = "utils/devicesDB.db"
JTAG_ADAPTERS = "utils/jtag-adapters.db"

DEVICE_CFG_FILE = "build/config/device-config.json"
JTAG_ADAPTERS_FILE = "build"
KEY_PATH = "utils/key/"
CERT_PATH = "cert/"

# DEV key environments
FUSION_REV_B0 = "fusion_rev_b0"
FUSION_REV_B4 = "fusion_rev_b4"
SPARK_REV_A0 = "spark_rev_a0"
SPARK_REV_A7 = "spark_rev_a7"
EAGLE_REV_A0 = "eagle_rev_a0"
EAGLE_REV_A1 = "eagle_rev_a1"
KUMA_REV_A0 = "kuma_rev_a0"

mram_interface = ["jtag", "isp"]


def read_json_file(file):
    """
    Open and read specific JOSN file.

    Args:
        file (str): Path to the JSON file to read.

    Returns:
        dict: Parsed JSON data as a Python dictionary.

    Raises:
        SystemExit: Exits the program if JSON parsing fails or any error occurs.
    """
    f = open(file, "r")
    try:
        data = json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] JSON file not found: {file}")
        sys.exit(EXIT_WITH_ERROR)
    except JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in file: {file}")
        print(f"  Line {e.lineno}, Column {e.colno}: {e.msg}")
        sys.exit(EXIT_WITH_ERROR)
    except JSONDecodeError as e:
        print("[ERROR] in JSON file.")
        print(str(e))
        sys.exit(EXIT_WITH_ERROR)
    except ValueError as v:
        print(f"[ERROR] Value error in JSON file: {file}")
        print(f"  {v}")
        sys.exit(EXIT_WITH_ERROR)
    except:
        print(f"[ERROR] Unknown error loading JSON file {file}")
        sys.exit(EXIT_WITH_ERROR)

    f.close()

    return data


def save_global_config(cfg):
    """
    Save configuration data to a JSON file.

    Args:
        cfg (dict): Configuration dictionary to save.

    Returns:
        None

    Raises:
        IOError: If the file cannot be written.
        TypeError: If cfg contains non-serializable objects.
    """
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)


def showAndSelectOptions(list_input, default):
    """
    Show interactive menu
    Display a numbered list of options and prompt the user to select one.

    Presents options in a numbered menu format, highlighting the default option.
    Special 'SEP' entries create visual separators (blank lines) in the menu
    but are not selectable options.

    Args:
        list (list): List of option strings. Use 'SEP' for visual separators.
        default (str): The default option to return if user presses Enter.

    Returns:
        str: The selected option string, or the default if no input provided.

    Examples:
        >>> options = ['Option A', 'Option B', 'SEP', 'Option C']
        >>> result = showAndSelectOptions(options, 'Option A')
        Available options:

        1 - Option A (default)
        2 - Option B
        3 - Option C

        Please enter the number of your option:

    Note:
        - Pressing Enter without input returns the default option
        - Invalid inputs prompt the user to try again
        - 'SEP' entries are removed from the list during execution

    Args:
       list_input
       default

    Returns:
       menu list
    """
    option = "x"
    while option == "x":
        print("\nAvailable options:\n")
        i = 1
        for item in list_input:
            if item == "SEP":
                print("")
            else:
                if item == default:
                    print(str(i) + " - " + item + " (default)")
                else:
                    print(str(i) + " - " + item)
                i += 1
        while "SEP" in list_input:
            list_input.remove("SEP")

        option = input("\nPlease enter the number of your option: ")
        if option == "":
            return default
        try:
            idx = int(option)
        except ValueError:
            print("Invalid option - Please try again")
            option = "x"
            continue

        if idx < 1 or idx > len(list_input):
            print("Invalid option - Please try again")
            option = "x"

    return list_input[int(idx - 1)]


def update_device_config_file(device_part, device_revision):
    """
    Update the device configuration file with firewall and wounding settings.

    Generates firmware configuration specific to ICV devices and merges it with
    the existing device configuration file. This includes firewall settings from
    the generated fw_cfg.json and wounding information from the device part data.

    Args:
        device_part (dict): Device part information containing:
            - family (str): Device family name
            - mram_size (int/str): MRAM size specification
            - sram_size (int/str): SRAM size specification
            - featureSet (str): Device feature set identifier
            - wounding (dict): Wounding configuration data
        device_revision (str): Device revision identifier (e.g., 'A0', 'A5')

    Args:
       device_part
       device_revision

    Returns:
       None

    Side Effects:
        - Generates temporary file at build/fw_cfg.json
        - Updates the DEVICE_CFG_FILE with merged configuration
        - Skips all operations if running in APP mode
    Note:
        This function only executes for ICV device configurations.
        APP configurations are handled differently and return early.

    """

    if isThisAPP():  # this is logic only for ICV device configuration
        return

    load_global_config()
    # generate the temp file 'build/fw_cfg.json'
    gen_fw_cfg_icv(
        device_part["family"],
        device_part["mram_size"],
        device_part["sram_size"],
        device_revision,
        device_part["featureSet"],
    )

    # open the device config file
    with open(DEVICE_CFG_FILE, "r") as device_config_file:
        device_config_json = json.load(device_config_file)

    # incorporate fw_cfg.json into the device config file
    with open(FW_CFG_FILE, "r") as fw_cfg_file:
        fw_json = json.load(fw_cfg_file)
        device_config_json["firewall"] = fw_json
        # add the wounding information as well
        device_config_json["wounding"] = device_part["wounding"]

    # save the updated device config file
    with open(DEVICE_CFG_FILE, "w") as device_config_file:
        json.dump(device_config_json, device_config_file, indent=4)


def printMenu(cfg):
    """
    Display the current configuration menu.

    Prints a formatted menu showing the current device and MRAM burner
    configuration settings, including device family, part number, revision,
    interface type, and JTAG adapter.

    Args:
        cfg (dict): Configuration dictionary containing:
            - DEVICE (dict): Device configuration with 'Part#' and 'Revision'
            - MRAM-BURNER (dict): MRAM burner settings with 'Interface' and 'Jtag-adapter'

    Returns:
        None

    Side Effects:
        Prints formatted configuration information to stdout.
        Looks up device family from the global devDB using the part number.
    Example Output:
        *           *
        Current configuration
         - DEVICE Family: M4 - Part#: DEVICE123 - Rev: A5
         - MRAM BURNER
         Interface: SWD
         JTAG Adapter: J-Link
        *           *
    """
    print("\n")
    print("* * * * * * * * * * * * * * * * * * * * * *")
    print("Current configuration")

    family = devDB[cfg["DEVICE"]["Part#"]]["family"]
    part_num = cfg["DEVICE"]["Part#"]
    revision = cfg["DEVICE"]["Revision"]
    print(f" - DEVICE Family: {family} - Part#: {part_num} - Rev: {revision}")
    print(" - MRAM BURNER")
    print(f" Interface: {cfg['MRAM-BURNER']['Interface']}")
    print(f" JTAG Adapter: {cfg['MRAM-BURNER']['Jtag-adapter']}")
    print("* * * * * * * * * * * * * * * * * * * * * *")


def loadParts(family):
    """
    Load all device part numbers for a specified device family.

    Searches the device database (devDB) and returns a list of all part numbers
    that belong to the given device family.

    Args:
        family (str): The device family name to filter by (e.g., 'M4', 'M7').

    Returns:
        list: List of part number strings matching the specified family.
              Returns empty list if no matching parts are found.

    Example:
        >>> loadParts('M4')
        ['DEVICE123', 'DEVICE456', 'DEVICE789']

    Note:
        Relies on the global devDB dictionary containing device information
        with 'family' keys.
    """
    parts = []
    for key in devDB:
        if devDB[key]["family"] == family:
            parts.append(key)
    return parts


def validateRevision(dev_revisions, current_revision):
    """
    Validate and return a device revision, defaulting to the first if invalid.

    Checks if the current revision exists in the list of valid revisions.
    If not found, returns the first revision from the valid list as a fallback.

    Args:
        dev_revisions (list): List of valid device revision strings.
        current_revision (str): The revision to validate.

    Returns:
        str: The validated revision, or the first valid revision if invalid.

    Example:
        >>> validateRevision(['A0', 'A1', 'B0'], 'A1')
        'A1'
        >>> validateRevision(['A0', 'A1', 'B0'], 'C0')
        'A0'
    """
    if current_revision not in dev_revisions:
        current_revision = dev_revisions[0]
    return current_revision


def clean_directory_rot():
    """
    Clean RoT (Root of Trust) directories by removing non-OEM files.

    Removes all files from the key and certificate directories except those
    starting with 'oem' (case-insensitive). This prepares the directories
    for a new key environment setup.

    Returns:
        None

    Side Effects:
        - Deletes files from KEY_PATH (except OEM files)
        - Deletes files from CERT_PATH (except OEM files)
        - Preserves subdirectories and OEM-prefixed files

    Note:
        Only removes files, not directories.
    """
    # clean key folder
    path = KEY_PATH
    for file in os.listdir(path):
        if file[0:3].lower() == "oem":
            continue
        f = path + file
        if os.path.isfile(f):
            os.remove(f)

    # clean certs folder
    path = CERT_PATH
    for file in os.listdir(path):
        if file[0:3].lower() == "oem":
            continue
        f = path + file
        if os.path.isfile(f):
            os.remove(f)


def copy_content_rot(rot_dir):
    """
    Copy RoT (Root of Trust) content from a specific directory to working paths.

    Copies key and certificate files from the specified RoT directory to the
    main KEY_PATH and CERT_PATH directories. Only applies to ICV DEV key releases.

    Args:
        rot_dir (str): Name of the RoT subdirectory to copy from.

    Returns:
        None

    Side Effects:
        - Copies non-OEM files from KEY_PATH/rot_dir to KEY_PATH
        - Copies all files from CERT_PATH/rot_dir to CERT_PATH
        - Skips all operations if running in PROD mode

    Note:
        This function returns early without action for production environments.
    """
    # this only applies to ICV DEV key release... (local, no Azure)
    if isThisPROD():
        return

    # copy key env from the selected RoT
    path = KEY_PATH + rot_dir
    for file in os.listdir(path):
        f = path + "/" + file
        if file[0:3].lower() == "oem":
            continue
        shutil.copy(f, KEY_PATH)

    # copy certs env from the selected RoT
    path = CERT_PATH + rot_dir
    for file in os.listdir(path):
        f = path + "/" + file
        # shutil.copy(f, 'cert/')
        shutil.copy(f, CERT_PATH)


def isThisAPP():
    """
    Check if the current environment is APP mode.

    Determines the environment type by checking for the existence of an 'alif/'
    directory, which indicates APP mode configuration.

    Returns:
        bool: True if running in APP mode, False otherwise.

    Note:
        APP and ICV modes have different configuration and key handling logic.
    """
    if os.path.isdir("alif/"):
        return True
    return False


def isThisPROD():
    """
    Check if the current environment is PROD (production) mode.

    Determines if running in production by checking if KEY_PATH contains
    any subdirectories. Production environments have flat key structures
    without subdirectories.

    Returns:
        bool: True if running in PROD mode (no subdirectories in KEY_PATH),
              False if in development mode (subdirectories present).
    """
    for file in os.listdir(KEY_PATH):
        f = KEY_PATH + "/" + file
        if os.path.isdir(f):
            return False
    return True


def setKeyEnvironment(cfg):
    """
    Set the appropriate key environment based on device configuration.

    Determines and applies the correct RoT (Root of Trust) key environment
    based on the device's feature set and revision. Cleans existing keys,
    copies the appropriate key environment, and updates the configuration.

    Args:
        cfg (dict): Configuration dictionary containing:
            - DEVICE['keyEnv']: Current key environment
            - DEVICE['Part#']: Device part number
            - DEVICE['Revision']: Device revision

    Returns:
        None

    Side Effects:
        - Cleans RoT directories via clean_directory_rot()
        - Copies appropriate key files via copy_content_rot()
        - Updates cfg['DEVICE']['keyEnv'] with new environment
        - Saves updated configuration to global config file
        - Exits program if no valid RoT found for device/revision
    Raises:
        SystemExit: If no RoT environment matches the device configuration.

    Key Environment Rules:
        - Fusion B0/B1/B3: FUSION_REV_B0
        - Fusion B4: FUSION_REV_B4
        - Spark A0/A5/A7: SPARK_REV_A0
        - Eagle FPGA_A0/A0: EAGLE_REV_A0
        - Eagle FPGA_A1/A1: EAGLE_REV_A1
    Note:
        Returns early without action for APP mode environments.
    """
    # do not apply for APP tools
    if isThisAPP():
        return

    keyEnvCfg = cfg["DEVICE"]["keyEnv"]
    feature = devDB[cfg["DEVICE"]["Part#"]]["featureSet"]
    revision = cfg["DEVICE"]["Revision"]
    # check key env rules
    keyEnv = ""  # default key env for REV_B4 FUSION
    if feature == "Fusion" and revision != "B4":  # Rev B0, B1, B3...
        keyEnv = FUSION_REV_B0
    if feature == "Fusion" and revision == "B4":  # Rev B4 has a new RoT
        keyEnv = FUSION_REV_B4
    if feature == "Spark" and revision in ["A0", "A5"]:
        keyEnv = SPARK_REV_A0
    if feature == "Spark" and revision in ["FPGA_A7", "A7"]:
        keyEnv = SPARK_REV_A7
    if feature == "Eagle" and revision in ["FPGA_A0", "A0"]:
        keyEnv = EAGLE_REV_A0
    if feature == "Eagle" and revision in ["FPGA_A1", "A1"]:
        keyEnv = EAGLE_REV_A1
    if feature == "Kuma" and revision in ["FPGA_A0", "A0"]:
        keyEnv = KUMA_REV_A0
    # future rules...

    # validate keyEnv is NOT empty
    if keyEnv == "":
        print(
            f"[ERROR] We couldn't find any RoT for this Part/Revision: "
            f"{feature}/{revision}"
        )
        sys.exit(0)

    # set the new key env and save it in global-cfg.json
    print("Setting a new Key Environment")
    clean_directory_rot()
    copy_content_rot(keyEnv)
    cfg["DEVICE"]["keyEnv"] = keyEnv
    save_global_config(cfg)


def processCmdLineOption(args):
    """
    Process and apply command line arguments to update device configuration.
    Validates and applies device part number and revision from command line
    arguments. Updates the global configuration, device config file, and
    key environment accordingly.

    Args:
        args (Namespace): Command line arguments object containing:
            - part (str, optional): Device part number to set
            - rev (str, optional): Device revision to set

    Returns:
        None

    Side Effects:
        - Reads and updates the global configuration file (CONFIG_FILE)
        - Exits program on validation errors

    Raises:
        SystemExit: If invalid part number or revision is provided.
    """
    # read global cfg
    cfg = read_json_file(CONFIG_FILE)
    # print("Reading CONFIG_FILE = " + CONFIG_FILE)
    # validate option and set the Part#
    if args.part is not None:
        try:
            cfg["DEVICE"]["Part#"] = args.part.upper()
        except KeyError:
            print(f"[ERROR] Invalid Part# {args.part}")
            sys.exit(EXIT_WITH_ERROR)

    if args.rev is not None:
        dev_revisions = featDB[devDB[cfg["DEVICE"]["Part#"]]["featureSet"]]["revisions"]
        if args.rev.upper() in dev_revisions:
            cfg["DEVICE"]["Revision"] = args.rev.upper()
        else:
            print(f"[ERROR] Invalid Revision {args.rev}")
            sys.exit(EXIT_WITH_ERROR)

    save_global_config(cfg)
    update_device_config_file(devDB[cfg["DEVICE"]["Part#"]], cfg["DEVICE"]["Revision"])
    setKeyEnvironment(cfg)

    # read global cfg


#    cfg = read_json_file(CONFIG_FILE)
# print("Reading CONFIG_FILE = " + CONFIG_FILE)
# validate options
#    if args.part is not None:
#        part_upper = args.part.upper()
#        if part_upper not in devDB:
#            print(f"ERROR: Invalid Part# '{args.part}'")
#            print(f"Available parts: {', '.join(sorted(devDB.keys()))}")
#            sys.exit(EXIT_WITH_ERROR)
#        cfg['DEVICE']['Part#'] = part_upper

#    if args.rev is not None:
#        feature_set = devDB[cfg['DEVICE']['Part#']]['featureSet']
#        dev_revisions = featDB[feature_set]['revisions']
#        rev_upper = args.rev.upper()

#        if rev_upper in dev_revisions:
#            cfg['DEVICE']['Revision'] = rev_upper
#        else:
#            print(f"ERROR: Invalid Revision '{args.rev}' for part {cfg['DEVICE']['Part#']}")
#            print(f"Valid revisions: {', '.join(dev_revisions)}")
#            sys.exit(EXIT_WITH_ERROR)

#    save_global_config(cfg)
#    update_device_config_file(devDB[cfg['DEVICE']['Part#']], cfg['DEVICE']['Revision'])
#    setKeyEnvironment(cfg)


def load_database_files(
    device_db_path, family_db_path, features_db_path, jtag_adapters_path
):
    """
    Load data from multiple database files.

    Args:
        device_db_path: Path to device database JSON file
        family_db_path: Path to family database JSON file
        features_db_path: Path to features database JSON file
        jtag_adapters_path: Path to JTAG adapters text file

    Returns:
        tuple: (devDB, families, features, dev_revisions, jtag_adapters)
    """
    # Load device database
    devDB = read_json_file(device_db_path)

    # Load and extract family keys
    famDB = read_json_file(family_db_path)
    families = list(famDB.keys())

    # Load and extract feature keys
    featDB = read_json_file(features_db_path)
    features = list(featDB.keys())

    # Initialize device revisions list
    dev_revisions = []

    # Load JTAG adapters from file
    with open(jtag_adapters_path, "r") as f:
        jtag_adapters = f.read().strip().split("\n")

    return devDB, families, features, dev_revisions, jtag_adapters


def main():
    """
    The start of it all...
    Args:

    Returns:
       None
    """
    global devDB
    global featDB
    target_responded = False

    # Deal with Command Line
    parser = argparse.ArgumentParser(description="SETOOLS Selection")
    parser.add_argument(
        "-b",
        "--baudrate",
        type=int,
        help="serial port baud rate",
    )
    parser.add_argument(
        "-c",
        "--comport",
        type=str,
        # default="COM3",
        help="Specify COM port",
    )
    parser.add_argument("-p", "--part", type=str, help="Part#")
    parser.add_argument(
        "-a",
        "--autocfg",
        action="store_true",
        default=False,
        help="auto configure Part# and Revision",
    )
    parser.add_argument(
        "-d",
        "--discover",
        action="store_true",
        default=False,
        help="COM port discovery",
    )
    parser.add_argument("-r", "--rev", type=str, help="Revision")
    parser.add_argument("-v", "--verbose", action="store_true", help="verbosity mode")
    parser.add_argument(
        "-V", "--version", action="store_true", help="Display Version Number"
    )

    # memory defines for Alif/OEM MRAM Addresses and Sizes
    load_global_config()
    DEVICE_REVISION = utils.config.DEVICE_REVISION
    DEVICE_REV_BAUD_RATE = utils.config.DEVICE_REV_BAUD_RATE
    args = parser.parse_args()
    if args.version:
        print(TOOL_VERSION)
        sys.exit()

    baud_rate = DEVICE_REV_BAUD_RATE[DEVICE_REVISION]
    if args.baudrate is not None:
        baud_rate = args.baudrate

    handler = CtrlCHandler()  # [CTRL-C] handling

    os.system("")  # Help MS-DOS window with ESC sequences

    # set autocfg mode if any of associated options were invoked
    if args.discover or args.comport or args.baudrate:
        args.autocfg = True

    # Mode for dynamic discovery is being requested. This requires we  open an
    # ISP session
    if args.autocfg:  # auto configuration if requested
        print("discovering Part# and Revision")
        # restore default COM3
        args.comport = "COM3"
        comm_port_override = False
        if args.discover:
            comm_port_override = True

        # Serial dabbling open up port.
        isp = serialPort(baud_rate)  # Create ISP session
        if args.comport != "COM3":
            isp.setPort(args.comport)
            comm_port_override = False
        isp.setVerbose(args.verbose)  # turn on or off verbose mode for the host
        isp.CTRLCHandler = handler  # CTRL C Handler for this ISP session

        # COM port discovery was requested?
        if comm_port_override:
            print("[INFO] Discover")
            isp.discoverSerialPorts()

        errorCode = isp.openSerial()
        if errorCode is False:
            print(f"[ERROR] isp openSerial failed for {isp.getPort()}")
            sys.exit(EXIT_WITH_ERROR)
        print(f"[INFO] {isp.getPort()} open Serial port success ")

        # adjust baud rate if provided on command line
        if args.baudrate is not None:
            baud_rate = args.baudrate
            isp.setBaudRate(baud_rate)

        # Set up the baud rate ((same calls as in recovery.py))
        print("[INFO] baud rate", isp.getBaudRate())
        target_responded = True

    # load data from DBs
    devDB = read_json_file(DEVICE_DB)

    families = []
    famDB = read_json_file(FAMILY_DB)
    for key in famDB:
        families.append(key)

    features = []
    featDB = read_json_file(FEATURES_DB)
    for key in featDB:
        features.append(key)

    dev_revisions = []

    jtag_adapters = []
    with open(JTAG_ADAPTERS, "r") as f:
        jtag_adapters = f.read().strip().split("\n")

    # New vesion yet to be tried
    #    devDB, families, features, dev_revisions, jtag_adapters = load_database_files(
    #            DEVICE_DB,
    #            FAMILY_DB,
    #            FEATURES_DB,
    #            JTAG_ADAPTERS
    #    )

    # Process command line arguments if provided
    # args = parser.parse_args() @it should be already parsed above
    if args.part is not None or args.rev is not None:
        processCmdLineOption(args)
        sys.exit()

    # Interactive menu loop
    print("SETOOLS OPTIONS CONFIGURATION")

    # Target responded and Discovery mode is requested
    # The '-d' discovey mode will probe the target using ISP and update the
    # default target specifid by tools-config.
    # The file utils/global-cfg.db which contains the defaults, currently
    # this defaults to EAGLE-EAGLE E8
    if target_responded and args.autocfg:
        print("==============================================")
        print("Probing target for Part# and Revision...")
        # Talk to the device to get some data backf
        test_target = isp_test_target(baud_rate, isp)
        print("[INFO] Connecting to target...", end="")
        if test_target == TARGET_NOT_RESPONDED:
            print("[ERROR] Device not responding")
            sys.exit()

        if test_target == TARGET_RESPONDED:
            # be sure device is not in SEROM Recovery Mode
            device = device_probe.device_get_attributes(isp)
            attrs = device.get_attributes()

            if args.verbose:
                print(
                    f"[DBG] Target Device Info:\n"
                    f"  Part Number : {attrs['part_number']}\n"
                    f"  Revision    : {attrs['revision']}\n"
                    f"  Stage       : {attrs['stage']}\n"
                    f"  Environment : {attrs['environment']}"
                )

            if device.is_in_serom():
                print("[INFO] Device connected in Recovery")
            else:
                # target responded and is in SERAM stage
                print("[INFO] Device connected")
            #            all_info = search_device_by_part_number(devDB,device.part_number)
            # only interested in the device_name from this function call

            # print('looking up in devDB')
            # device_name, _ = find_device_by_part_number(devDB,
            #                                                      device.part_number)
            # print(device_name)
            partDescription = getPartDescription(device.part_number)

            if partDescription:
                # if args.verbose:
                #    print(f"[INFO] Found: {device.part_number}")
                #                print(f"  Feature Set: {device_info['featureSet']}")
                #                print(f"  Family: {device_info['family']}")
                config_changed = False

                # Check the Revision and Device Name matches the default set by
                # tools config.
                # If they are different we will default to the newly found target
                cfg = read_json_file(CONFIG_FILE)
                cfg_device_part_num = cfg["DEVICE"]["Part#"]
                cfg_device_revision = cfg["DEVICE"]["Revision"]
                if cfg_device_part_num != partDescription:
                    print(
                        f"[INFO] Updating Part# default from "
                        f"{cfg_device_part_num} to {partDescription}"
                    )
                    cfg["DEVICE"]["Part#"] = partDescription
                    config_changed = True
                else:
                    short_part = cfg["DEVICE"]["Part#"].split("(")[1].split(")")[0]
                    #                    print(f"[INFO] Target part# {cfg_device_part_num} "
                    #                          f" matches default {device_name}")
                    print(
                        f"[INFO] Target part# {short_part} "
                        f" matches default {partDescription}"
                    )

                if cfg_device_revision != attrs["revision"]:
                    print(
                        f"[INFO] Updating Revision default from "
                        f"{cfg_device_revision} to {attrs['revision']}"
                    )
                    cfg["DEVICE"]["Revision"] = attrs["revision"]
                    config_changed = True
                else:
                    print(
                        f"[INFO] Target revision {cfg['DEVICE']['Revision']} "
                        f" matches default {attrs['revision']}"
                    )

                # Only update config files if changes were made
                if config_changed:
                    update_device_config_file(
                        devDB[cfg["DEVICE"]["Part#"]], cfg["DEVICE"]["Revision"]
                    )
                    save_global_config(cfg)
                else:
                    print("[INFO] No selection update made")
            else:
                print(f"[ERROR] Device {device_name} not found")
                sys.exit(EXIT_WITH_ERROR)

    # Enter interactive mode
    option = ""
    while option != "Exit":
        cfg = read_json_file(CONFIG_FILE)
        part_num = cfg["DEVICE"]["Part#"]
        feature_set = devDB[part_num]["featureSet"]
        dev_revisions = featDB[feature_set]["revisions"]

        printMenu(cfg)
        option = showAndSelectOptions(
            ["Part#", "Revision", "Interface", "JTAG Adapter", "SEP", "Exit"], "Exit"
        )
        if option == "Part#":
            current_family = devDB[cfg["DEVICE"]["Part#"]]["family"]
            selected_family = showAndSelectOptions(families, current_family)
            parts = loadParts(selected_family)
            current_part = cfg["DEVICE"]["Part#"]
            cfg["DEVICE"]["Part#"] = showAndSelectOptions(parts, current_part)
            dev_revisions = featDB[devDB[cfg["DEVICE"]["Part#"]]["featureSet"]][
                "revisions"
            ]
            cfg["DEVICE"]["Revision"] = validateRevision(
                dev_revisions, cfg["DEVICE"]["Revision"]
            )
            update_device_config_file(
                devDB[cfg["DEVICE"]["Part#"]], cfg["DEVICE"]["Revision"]
            )
        elif option == "Revision":
            current_revision = cfg["DEVICE"]["Revision"]
            cfg["DEVICE"]["Revision"] = showAndSelectOptions(
                dev_revisions, current_revision
            )
            update_device_config_file(devDB[cfg["DEVICE"]["Part#"]], current_revision)
        elif option == "Interface":
            current_interface = cfg["MRAM-BURNER"]["Interface"]
            cfg["MRAM-BURNER"]["Interface"] = showAndSelectOptions(
                mram_interface, current_interface
            )
        elif option == "JTAG Adapter":
            current_adapter = cfg["MRAM-BURNER"]["Jtag-adapter"]
            cfg["MRAM-BURNER"]["Jtag-adapter"] = showAndSelectOptions(
                jtag_adapters, current_adapter
            )
        elif option == "Revision":
            cfg["DEVICE"]["Revision"] = showAndSelectOptions(
                dev_revisions, cfg["DEVICE"]["Revision"]
            )
            update_device_config_file(
                devDB[cfg["DEVICE"]["Part#"]], cfg["DEVICE"]["Revision"]
            )
        elif option == "Interface":
            cfg["MRAM-BURNER"]["Interface"] = showAndSelectOptions(
                mram_interface, cfg["MRAM-BURNER"]["Interface"]
            )
        elif option == "JTAG Adapter":
            cfg["MRAM-BURNER"]["Jtag-adapter"] = showAndSelectOptions(
                jtag_adapters, cfg["MRAM-BURNER"]["Jtag-adapter"]
            )

        save_global_config(cfg)
        setKeyEnvironment(cfg)


if __name__ == "__main__":
    main()
