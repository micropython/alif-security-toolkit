#!/usr/bin/python3

"""
@brief Secure Key decode

__author__ onyettr
"""
# pylint: disable=unused-argument, invalid-name
# from isp_print import isp_print_color

SE_NUM_KEY_SLOTS = 8  # Max slots
SE_KEY_TYPE_NONE = 0x0000  # No key
SE_KEY_TYPE_AES_128 = 0x0001  # 128-bit AES key
SE_KEY_TYPE_AES_256 = 0x0002  # 256-bit AES key
SE_KEY_TYPE_ECC_P256_ECDSA = 0x0010  # NIST P-256 for ECDSA
SE_KEY_TYPE_ECC_P384_ECDSA = 0x0011  # NIST P-384 for ECDSA
SE_KEY_TYPE_ECC_P256_ECDH = 0x0020  # NIST P-256 for ECDH
SE_KEY_TYPE_ECC_P384_ECDH = 0x0021  # NIST P-384 for ECDH

key_type_lut = {
    SE_KEY_TYPE_NONE: "No Key",
    SE_KEY_TYPE_AES_128: "AES-128",
    SE_KEY_TYPE_AES_256: "AES-256",
    SE_KEY_TYPE_ECC_P256_ECDSA: "ECC P-256 ECDSA",
    SE_KEY_TYPE_ECC_P384_ECDSA: "ECC P-384 ECDSA",
    SE_KEY_TYPE_ECC_P256_ECDH: "ECC P-256 ECDH",
    SE_KEY_TYPE_ECC_P384_ECDH: "ECC P-384 ECDH",
}


def display_key_storage(message):
    """
    display_key_storage
        Display SE Secure key storage details
    """
    for key_slot in range(SE_NUM_KEY_SLOTS):
        key_type = message[key_slot]
        label = key_type_lut.get(key_type, f"Unknown (0x{key_type:04X})")
        print(f"  Slot {key_slot:2d}: [0x{key_type:04X}] {label}")
