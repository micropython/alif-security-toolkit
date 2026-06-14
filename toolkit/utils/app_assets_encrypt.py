from utils import rsa_keygen
from utils import dmpu_oem_key_request_util
from utils import dmpu_oem_asset_pkg_util


OEM_ROT = "utils/key/OEMRoT.pem"
OEM_ROT_PUBLIC = "utils/key/OEMRoTPublic.pem"
OEM_ROT_KEY_PAIR = "utils/key/OEMRoT_key_pair.pem"

OEM_ENC_KEY = "utils/key/oem_tmp_enc_key.pem"
OEM_ENC_PUBLIC = "utils/key/oem_tmp_enc_pub_key.pem"
OEM_ENC_KEY_PAIR = "utils/key/oem_tmp_enc_key_pair.pem"


def merge_files(inFile1, inFile2, outFile):
    print("Generating " + outFile + " file...")
    with open(outFile, "wb") as f:
        with open(inFile1, "rb") as i:
            f.write(i.read())
        with open(inFile2, "rb") as i:
            f.write(i.read())


def generate_request():
    print("Generating Temporary key pair (to generate ICV Request package)")
    rsa_keygen.main(
        [
            "utils/key/oem_tmp_enc_key.pem",
            "-p",
            "utils/key/oem_keys_pass.pwd",
            "-k",
            "utils/key/oem_tmp_enc_pub_key.pem",
            "-l",
            "build/logs/key_gen_log.log",
        ]
    )

    print("Merging key pairs...")
    merge_files(OEM_ROT, OEM_ROT_PUBLIC, OEM_ROT_KEY_PAIR)
    merge_files(OEM_ENC_KEY, OEM_ENC_PUBLIC, OEM_ENC_KEY_PAIR)
    print("Generating Request package...")
    dmpu_oem_key_request_util.main(
        ["utils/cfg/dmpu_oem_key_request.cfg", "build/logs/key_request_cert.log"]
    )


def encrypt_package():
    print("Processing ICV Response package...")
    dmpu_oem_asset_pkg_util.main(
        ["utils/cfg/asset_oem_ce.cfg", "build/logs/oem_asset_pkg.log"]
    )
    dmpu_oem_asset_pkg_util.main(
        ["utils/cfg/asset_oem_cp.cfg", "build/logs/oem_asset_pkg.log"]
    )
