#!/usr/bin/python3

"""
@brief OTP Integrity check
Checks the following fields
- part number
- hbk0
- hbk1       test for zeros
- hbk_fw     test for zeros
- dcu        test for zeros
__author__ onyettr
"""

# pylint: disable=unused-argument, invalid-name
# from isp_print import isp_print_color
from typing import Optional, List

# All known Device part numbers
KNOWN_PARTS = {
    # ── Blank Part
    "",
    # ── Ensemble / Eagle
    "AE822FA0E5597BS0",
    "AE822FA0E5597LS0",
    "AE612FA0E5597LS0",
    "AE612FA0E5597BS0",
    "AE402FA0E5597LE0",
    "AE402FA0E5597BE0",
    "AE402FA0D5597BE0",
    # ── Ensemble / Fusion
    "AE722F80F55D5LS",
    "AE722F80F55D5AS",
    "AE512F80F55D5LS",
    "AE512F80F55D5AS",
    "AE512F80F5582AS",
    "AE512F80F5582LS",
    "AE302F80F55D5LE",
    "AE302F80F5582LE",
    "AE302F80F55D5AE",
    "AE302F80F5582AE",
    "AE302F80C1557LE",
    "AE302F40C1537LE",
    "AE101F4071542LH",
    # ── Ensemble / Spark
    "AE1C1F4051920PH",
    "AE1C1F4051920PH0",
    "AE1C1F4051920HH0",
    "AE1C1F1041010PH0",
    "AE1C1F1041010HH0",
    "AE1C1F1040505PH0",
    "AE1C1F1040505HH0",
    # ── Balletto / Spark
    "AB1C1F4M51820PH",
    "AB1C1F4M51820PH0",
    "AB1C1F4M51820HH0",
    "AB1C1F1M41820PH0",
    "AB1C1F1M41820HH0",
    "AB1C1F1M41010PH0",
    "AB1C1F1M41010HH0",
}

# Valid HBK0 Public Hash keys
KNOWN_HBK0 = {
    "00000000000000000000000000000000",  # BLANK
    "7715fe1a57f193ef2a856f052aa24779",  # REV_A0     DEV
    "c879a64b28100754b462589ae1f34d3b",  # REV_B0/2/3 DEV
    "14a83ae9e20b233a5c3dd23dd5176f40",  # REV_B0/2/3 PROD
    "f049442ecc7900a838d34c31d71e62e6",  # REV_B4     DEV
    "4ca48f28d3267e1e520706995f1fa338",  # REV_B4     PROD
    "af9771e6f171ee6de39106bd812babf0",  # SPARK_A0   DEV
    "903afc081cf3015864fef36b159de342",  # SPARK_A0   PROD
    "99B897B47A2C177F9D525E9553337F6F",  # SPARK_A7   DEV
    "83B8E69193169DCB03AE8A268B205D4F",  # SPARK_A7   PROD
    "cd74ac7009072c3e27b8b8f73af34ede",  # EAGLE_A0   DEV
    "cb2e696be08c4cb4481de20895b94d56",  # EAGLE_A0   PROD
    "e8adcbf502403d608cac47e04c624987",  # EAGLE_A1   DEV
    "1eed607490c56d207168fa63dbb51ced",  # EAGLE_A1   PROD
}

KNOWN_HBK1 = {
    "00000000000000000000000000000000",  # BLANK
}

# Column width for value field (HBK_FW is widest at 40 hex chars)
_VALUE_COL = 40

# ANSI escape sequences
ANSI_BOLD_RED = "\033[1;31m"
ANSI_RESET = "\033[0m"
NOT_OK = f"{ANSI_BOLD_RED}NOT OK{ANSI_RESET}"

# Colour codes matched to isp_print_color fg keys
_ANSI_FG = {
    "red": "\033[1;31m",
    "blue": "\033[1;34m",
    "green": "\033[1;32m",
    "yellow": "\033[1;33m",
    "white": "\033[1;37m",
    "reset": "\033[0m",
}


def check_part_number(part_number: bytes) -> bool:
    """
    Validate a device Part# against the known-good part table.

    The raw bytes are decoded as ASCII and stripped of null bytes and spaces
    before lookup. An all-zero buffer (unprovisioned device) decodes to ""
    which is a valid entry in KNOWN_PARTS.

    Parameters
    ----------
    part_number : bytes
        Raw Part# field from the device message (e.g. message[x:y]).

    Returns
    -------
    bool
        True if the part number is in KNOWN_PARTS, False otherwise.
    """
    pn = part_number.decode("ascii").strip("\x00")

    if pn in KNOWN_PARTS:
        return True
    return False


def check_hbk0(hbk0: List[int]) -> bool:
    """
    Validate the HBK0 (Hardware Boot Key 0) against the known-good key table.

    The list of integers is converted to bytes then compared as a lowercase
    hex string against KNOWN_HBK0. The comparison is case-insensitive so
    keys may be stored in any case in the table.

    Parameters
    ----------
    hbk0 : List[int]
        HBK0 field from the device message as a list of byte values.

    Returns
    -------
    bool
        True if the HBK0 value is in KNOWN_HBK0, False otherwise.
    """
    hbk0_bytes = bytes(hbk0)

    #    if hk == b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00':
    #        return True
    if hbk0_bytes.hex().lower() in {k.lower() for k in KNOWN_HBK0}:
        return True

    return False


def check_hbk1(hbk1: List[int]) -> bool:
    """
    Validate the HBK1 (Hardware Boot Key 1) against the known-good key table.

    For unprovisioned devices HBK1 must be all zeros. For customer-provisioned
    devices the expected key value should be added to KNOWN_HBK1. The
    comparison is case-insensitive.

    TODO: Should check the LCS State as Customer may have provisioned the part

    Parameters
    ----------
    hbk1 : List[int]
        HBK1 field from the device message as a list of byte values.

    Returns
    -------
    bool
        True if the HBK1 value is in KNOWN_HBK1, False otherwise.
    """
    hbk1_bytes = bytes(hbk1)
    if hbk1_bytes.hex() in KNOWN_HBK1:
        return True

    return False


def check_hbk_fw(hbk_fw: List[int]) -> bool:
    """
    Validate the HBK_FW (Firmware Boot Key) field.

    HBK_FW must be all zero bytes for a valid unprovisioned device.
    Derived from message[54:74] (20 bytes).

    Parameters
    ----------
    hbk_fw : List[int]
        HBK_FW field from the device message as a list of byte values.

    Returns
    -------
    bool
        True if all bytes are 0x00, False otherwise.
    """
    if bytes(hbk_fw) == b"\x00" * len(hbk_fw):
        return True
    return False


def check_dcu(dcu: List[int]) -> bool:
    """
    Validate the DCU (Device Configuration Unit) field.

    DCU must equal zero for a valid unprovisioned device. The field is
    interpreted as a little-endian integer. Derived from message[78:94].

    Parameters
    ----------
    dcu : List[int]
        DCU field from the device message as a list of byte values.

    Returns
    -------
    bool
        True if the DCU value is 0x00000000, False otherwise.
    """
    dcu_int = int.from_bytes(dcu, "little")
    if dcu_int == 0x0:
        return True
    return False


def closest_part_match(part_number: bytes) -> Optional[str]:
    """
    Return the known part number that differs by exactly 1 character
    substitution, or None if no match or ambiguous.
    """
    pn = part_number.decode("ascii").strip("\x00")
    candidates = [
        known
        for known in KNOWN_PARTS
        if len(known) == len(pn) and sum(a != b for a, b in zip(pn, known)) == 1
    ]
    return candidates[0] if len(candidates) == 1 else None


def closest_nearest_part_match(part_number: bytes) -> Optional[str]:
    """
    Return the known part number with the fewest character substitutions.
    Same-length candidates are scored by substitution count; different-length
    candidates are scored by absolute length difference as a tiebreaker.
    Returns None if KNOWN_PARTS is empty or the input decodes to empty.
    """
    pn = part_number.decode("ascii").strip("\x00 ")
    if not pn or not KNOWN_PARTS:
        return None

    def score(known: str) -> tuple[int, int]:
        if len(known) == len(pn):
            return sum(a != b for a, b in zip(pn, known)), 0
        # different length: count mismatches on the overlap + length penalty
        overlap = sum(a != b for a, b in zip(pn, known))
        return overlap + abs(len(pn) - len(known)), abs(len(pn) - len(known))

    best = min(KNOWN_PARTS, key=score)
    return best


def _highlight_nonzero(data: List[int], restore: str = "") -> str:
    """
    Return a hex string with non-zero bytes wrapped in ANSI red so they
    stand out visually against the zero bytes.

    Parameters
    ----------
    data : List[int]
        List of byte values to format.

    Returns
    -------
    str
        Hex string with non-zero byte pairs highlighted in red.
    """
    parts = []
    for b in data:
        hi = (b >> 4) & 0xF  # high nibble
        lo = b & 0xF  # low nibble
        hi_char = f"{hi:x}"
        lo_char = f"{lo:x}"
        hi_str = f"{ANSI_BOLD_RED}{hi_char}{ANSI_RESET}{restore}" if hi else hi_char
        lo_str = f"{ANSI_BOLD_RED}{lo_char}{ANSI_RESET}{restore}" if lo else lo_char
        parts.append(hi_str + lo_str)
    # Below prints the BYTE, just comment out above
    #        hex_byte = f"{b:02x}"
    #        if b != 0x00:
    #            parts.append(f"{ANSI_BOLD_RED}{hex_byte}{ANSI_RESET}{restore}")
    #        else:
    #            parts.append(hex_byte)
    visible_len = len(data) * 2  # 2 hex chars per byte, no ANSI
    padding = max(0, _VALUE_COL - visible_len)
    return "".join(parts) + " " * padding


def _print_color(fg: str, message: str) -> None:
    """
    Print a coloured message as a single write so that ANSI codes and
    text are not split across separate print() calls, which would cause
    misalignment when the terminal processes the escape sequences.

    Parameters
    ----------
    fg : str
        Foreground colour key matching isp_print_color (e.g. 'red', 'blue').
    message : str
        Message string to print.
    """
    print(f"{_ANSI_FG.get(fg, '')}{message}{_ANSI_FG['reset']}", end="")


def check_otp_integrity(
    part_number: bytes,
    hbk0: List[int],
    hbk1: List[int],
    hbk_fw: List[int],
    dcu: List[int],
) -> bool:
    """
    Validate all OTP (One-Time Programmable) fields for a device record.

    Runs each field through its dedicated check function and reports any
    failures via isp_print_color(). All fields are checked regardless of
    earlier failures so a single call surfaces every problem at once.

    Fields checked
    --------------
    Part#   : Must exist in KNOWN_PARTS. On failure the nearest known part
              (single character substitution) is suggested if unambiguous.
    HBK0    : Must exist in KNOWN_HBK0 (case-insensitive hex comparison).
    HBK1    : Must exist in KNOWN_HBK1 (case-insensitive hex comparison).
    HBK_FW  : All bytes must be 0x00.
    DCU     : Little-endian integer value must be 0x00000000.

    Parameters
    ----------
    part_number : bytes
        Raw Part# field from the device message.
    hbk0 : List[int]
        HBK0 field as a list of byte values.
    hbk1 : List[int]
        HBK1 field as a list of byte values.
    hbk_fw : List[int]
        HBK_FW field as a list of byte values (message[54:74]).
    dcu : List[int]
        DCU field as a list of byte values (message[78:94]).

    Returns
    -------
    bool
        True if all fields pass, False if any field fails.
    """
    tests_ok = True

    if not check_part_number(part_number):
        pn = part_number.decode("ascii").strip(chr(0) + " ")
        _print_color("blue", f" Part#  {pn:<{_VALUE_COL}} {NOT_OK}\n")
        #        suggestion = closest_nearest_part_match(part_number)
        #        hint = f"  did you mean: {suggestion}" if suggestion else "  no close match"
        tests_ok = False
    if not check_hbk0(hbk0):
        _print_color("blue", f" HBK0   {bytes(hbk0).hex():<{_VALUE_COL}} {NOT_OK}\n")
        tests_ok = False

    if not check_hbk1(hbk1):
        _print_color(
            "blue", f" HBK1   {_highlight_nonzero(hbk1, _ANSI_FG['blue'])} {NOT_OK}\n"
        )
        tests_ok = False

    if not check_hbk_fw(hbk_fw):
        _print_color(
            "blue", f" HBK_FW {_highlight_nonzero(hbk_fw, _ANSI_FG['blue'])} {NOT_OK}\n"
        )
        tests_ok = False

    if not check_dcu(dcu):
        _print_color(
            "blue", f" DCU    {_highlight_nonzero(dcu, _ANSI_FG['blue'])} {NOT_OK}\n"
        )
        tests_ok = False

    return tests_ok
