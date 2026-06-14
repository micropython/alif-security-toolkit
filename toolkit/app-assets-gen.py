#!/usr/bin/env python3
import sys
import os
import struct
import argparse
from utils.config import *
from utils.toc_common import *
import json
from json.decoder import JSONDecodeError
from utils.app_assets_encrypt import *

# Define Version constant for each separate tool
# 0.01.000   Initial version
# 0.02.000   added checksum for integrity
# 0.03.000   added encrypted assets option
TOOL_VERSION = "0.03.000"

EXIT_WITH_ERROR = 1
EXIT_NO_ERROR = 0

# OUTPUT_FILE = 'build/assets-rev-b0.bin'
ASSET_ID = "APPASSET"
ASSET_VER = 1
CHECK_SUM = 0x00

HBK0_KEY = "utils/key/hbk1.bin"
PROV_KEY = "utils/key/oem_prov_asset.bin"
PROV_PKG = "utils/key/oem_prov_asset_pkg.bin"
ENC_KEY = "utils/key/oem_enc_asset.bin"
ENC_PKG = "utils/key/oem_enc_asset_pkg.bin"
REQ_PKG = "utils/key/oem_request_pkg.bin"
RSP_PKG = "utils/key/icv_response_pkg.bin"

OEM_ROT_KEY_PAIR = "utils/key/OEMRoT_key_pair.pem"
OEM_ENC_KEY = "utils/key/oem_tmp_enc_key.pem"
OEM_ENC_PUBLIC = "utils/key/oem_tmp_enc_pub_key.pem"

# DO NOT Alter the sequence of the following items in the list as it determines
# the bit position in the final value
OPTIONS = ["ENCRYPTED_ASSETS", "TEST_MODE"]

OPTION_FLAGS = 0x00


def read_asset_config(cfgFile):
    f = open(cfgFile, "r")
    try:
        cfg = json.load(f)

    except JSONDecodeError as e:
        print("ERROR in JSON file.")
        print(str(e))
        sys.exit(EXIT_WITH_ERROR)

    except ValueError as v:
        print("ERROR in JSON file:")
        print(str(v))
        sys.exit(EXIT_WITH_ERROR)

    except:
        print("ERROR: Unknown error loading JSON file")
        sys.exit(EXIT_WITH_ERROR)

    f.close()
    return cfg


def create_package(outFile):
    print("Creating Assets Package...")
    with open(outFile, "wb") as f:
        f.write(ASSET_ID.encode("utf8"))
        f.write(struct.pack("H", ASSET_VER))
        f.write(struct.pack("H", CHECK_SUM))
        f.write(struct.pack("I", OPTION_FLAGS))
        with open(HBK0_KEY, "rb") as i:
            f.write(i.read())
        if OPTION_FLAGS & (1 << 0):
            # encrypted assets
            with open(PROV_PKG, "rb") as i:
                f.write(i.read())
            with open(ENC_PKG, "rb") as i:
                f.write(i.read())
        else:
            with open(PROV_KEY, "rb") as i:
                f.write(i.read())
            f.write(("\0" * 48).encode("utf8"))
            with open(ENC_KEY, "rb") as i:
                f.write(i.read())
            f.write(("\0" * 48).encode("utf8"))


def decodeFlags(assetFlags):
    print("")
    print("Provisioning Options:")
    for option in OPTIONS:
        fill = 20 - len(option)
        label = option + (fill * " ")
        if assetFlags & (1 << OPTIONS.index(option)):
            print(label + "ON")
        else:
            print(label + "\tOFF")


def check_package(outFile):
    print("Checking Assets Package...")
    # check integrity
    total = getChecksum(outFile)
    if total != 0:
        print("ERROR: Package integrity")
        sys.exit(EXIT_WITH_ERROR)
    else:
        print("Package integrity Ok!")

    with open(outFile, "rb") as f:
        assetID = f.read(8).decode("utf-8").rstrip("\0")
        assetVer = int.from_bytes(f.read(2), "little", signed=False)
        assetType = int.from_bytes(f.read(2), "little", signed=False)
        assetFlags = int.from_bytes(f.read(4), "little", signed=False)
        print("AssetID: " + assetID)
        print("Asset Version: " + str(assetVer))
        decodeFlags(assetFlags)
        print("")


def sum_list(l):
    sum = 0
    for x in l:
        sum += x
    return sum


def getChecksum(outFile):
    with open(outFile, "rb") as f:
        data = f.read()
        # convert byte array to list of shorts (16-bit)
        bList = [
            int.from_bytes(data[i : i + 2], "little") for i in range(0, len(data), 2)
        ]
        # calculate sum
        total = sum_list(bList) & 0xFFFF
        # calculate complement
        total = 0x10000 - total
        return total & 0xFFFF


def addChecksum(outFile):
    total = getChecksum(outFile)
    with open(outFile, "r+b") as f:
        f.seek(10)
        f.write(struct.pack("H", total))


def cleanup():
    # remove temporary files
    if os.path.exists(OEM_ROT_KEY_PAIR):
        os.remove(OEM_ROT_KEY_PAIR)
    if os.path.exists(OEM_ENC_KEY):
        os.remove(OEM_ENC_KEY)
    if os.path.exists(OEM_ENC_PUBLIC):
        os.remove(OEM_ENC_PUBLIC)


def main():
    global OPTION_FLAGS

    if sys.version_info.major == 2:
        print("You need Python 3 for this application!")
        return 0

    parser = argparse.ArgumentParser(
        description="Generate ICV External Assets",
        epilog="\N{COPYRIGHT SIGN} ALIF Semiconductor, 2023",
    )
    parser.add_argument(
        "-v", "--version", help="Display Version Number", action="store_true"
    )
    parser.add_argument(
        "-f",
        "--filename",
        type=str,
        help="input file  (default: build/config/assets-app-cfg.json",
    )
    parser.add_argument(
        "-c",
        "--check",
        help="Check asset package (skip generation)",
        action="store_true",
    )

    args = parser.parse_args()
    if args.version:
        print(TOOL_VERSION)
        sys.exit()

    # memory defines for Alif/OEM MRAM Addresses and Sizes
    load_global_config()
    DEVICE_PART_NUMBER = utils.config.DEVICE_PART_NUMBER
    DEVICE_REVISION = utils.config.DEVICE_REVISION

    print("Generating APP assets with:")
    print("- Device Part# " + DEVICE_PART_NUMBER + " - Rev: " + DEVICE_REVISION)
    configFile = args.filename
    if configFile == None:
        configFile = "build/config/assets-app-cfg.json"

    fileToCheck = configFile
    outFile = "build/" + os.path.basename(configFile)[:-4] + "bin"
    if args.check:
        # check binary file (check build options - NO Generation)
        if args.filename:
            outFile = args.filename
            fileToCheck = outFile
    else:
        print("- Configuration file: " + configFile)

    print("- Output file: " + outFile)
    print("")

    # verify the input file (config or binary) exists
    if not os.path.isfile(fileToCheck):
        print("File " + fileToCheck + " does not exist!")
        sys.exit()

    if args.check == False:
        cfg = read_asset_config(configFile)
        for option in cfg:
            if option not in OPTIONS:
                print("ERROR: option " + option + " not supported!")
                sys.exit()
            else:
                if cfg[option].upper() == "ON":
                    OPTION_FLAGS |= 1 << OPTIONS.index(option)
                    if option == "ENCRYPTED_ASSETS":
                        if not os.path.exists(REQ_PKG):
                            generate_request()
                            cleanup()
                            print(
                                "\n*******************************************************************************"
                            )
                            print("The request package has been generated: " + REQ_PKG)
                            print("Please send it to Alif to get the response package")
                            print(
                                "*******************************************************************************"
                            )
                            sys.exit(EXIT_NO_ERROR)
                        if not os.path.exists(RSP_PKG):
                            print(
                                "\n*******************************************************************************"
                            )
                            print("The request package exists: " + REQ_PKG)
                            print(
                                "It should be sent to Alif to get the response package"
                            )
                            print(
                                "If you want to generate a new request package, please delete the existing one"
                            )
                            print(
                                "*******************************************************************************"
                            )
                            sys.exit(EXIT_NO_ERROR)
                        encrypt_package()

        create_package(outFile)
        addChecksum(outFile)

    check_package(outFile)
    print("Done!")
    return 0


if __name__ == "__main__":
    main()
