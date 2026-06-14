#!/usr/bin/python3
"""
@brief Manufaturing Data decode and display - Analogue Trim data
This is for the FT fuse bits 4 words, 128-bits
   0x154
   0x158
   0x15c
   0x160
__author__ onyettr
"""

# pylint: disable=unused-argument, line-too-long, invalid-name
# pylint: disable=consider-using-f-string, f-string-without-interpolation
import struct

# import json
from isp_print import isp_print_color


class MfrDataTrimDecoder:
    """Manufactoring decoder, display class"""

    def __init__(
        self, fuse_data_0x154, fuse_data_0x158, fuse_data_0x15C, fuse_data_0x160
    ):
        """
        Initializes the decoder with raw 32-bit fuse data for each address.

        Args:
            fuse_data_0x154 (int): The 32-bit integer value from fuse address 0x154.
            fuse_data_0x158 (int): The 32-bit integer value from fuse address 0x158.
            fuse_data_0x15C (int): The 32-bit integer value from fuse address 0x15C.
            fuse_data_0x160 (int): The 32-bit integer value from fuse address 0x160.
        """
        self.fuse_0x154 = fuse_data_0x154
        self.fuse_0x158 = fuse_data_0x158
        self.fuse_0x15C = fuse_data_0x15C
        self.fuse_0x160 = fuse_data_0x160

    def decode_0x154(self):
        """Decodes the fields from fuse address 0x154."""
        decoded_data = {}
        # 0x154:31 FT_Valid_data (1 bit)
        decoded_data["Valid_data"] = (self.fuse_0x154 >> 31) & 0x1
        # 0x154:30 Trim Validation flag_BOR Abort (1 bit)
        decoded_data["BOR_Abort"] = (self.fuse_0x154 >> 30) & 0x1
        # 0x154:29-24 Temp Sensor (6 bits)
        decoded_data["Temp_Sensor"] = (self.fuse_0x154 >> 24) & 0x3F
        # 0x154:23-16 ADC VREF (8 bits)
        decoded_data["ADC_VREF"] = (self.fuse_0x154 >> 16) & 0xFF
        # 0x154:15-0 ADC24 Offset (16 bits)
        decoded_data["ADC24_Offset"] = self.fuse_0x154 & 0xFFFF
        return decoded_data

    def decode_0x158(self):
        """Decodes the fields from fuse address 0x158."""
        decoded_data = {}
        # 0x158:31-28 AON LDO (4 bits)
        decoded_data["AON_LDO"] = (self.fuse_0x158 >> 28) & 0xF
        decoded_data["RET_LDO"] = (self.fuse_0x158 >> 24) & 0xF

        # 0x158:23-20 PMU BG (4 bits)
        decoded_data["PMU_BG"] = (self.fuse_0x158 >> 20) & 0xF
        # 0x158:19-16 Peripheral BG (4 bits)
        decoded_data["PERIPH_BG"] = (self.fuse_0x158 >> 16) & 0xF
        # 0x158:15-12 AON BG<4:1> (4 bits)
        decoded_data["AON_BG_4_1"] = (self.fuse_0x158 >> 12) & 0xF
        # 0x158:11 AON BG<0> (1 bit)
        decoded_data["AON_BG_0"] = (self.fuse_0x158 >> 11) & 0x1
        # 0x158:10-8 Reserved (3 bits)
        decoded_data["Reserved_0x158"] = (self.fuse_0x158 >> 8) & 0x7
        # 0x158:7-0 DCDC pre-trim (8 bits)
        decoded_data["DCDC_pre_trim"] = self.fuse_0x158 & 0xFF
        return decoded_data

    def decode_0x15C(self):
        """Decodes the fields from fuse address 0x15C."""
        decoded_data = {}
        # 0x15C:31-26 HFRC 76.8 MHz (6 bits)
        decoded_data["HFRC"] = (self.fuse_0x15C >> 26) & 0x3F
        # 0x15C:25-16 ADC120 Offset (10 bits)
        decoded_data["ADC120_Offset"] = (self.fuse_0x15C >> 16) & 0x3FF
        # 0x15C:15-10 LFRC 32.7 kHz (6 bits)
        decoded_data["LFRC"] = (self.fuse_0x15C >> 10) & 0x3F
        # 0x15C:9-0 ADC121 Offset (10 bits)
        decoded_data["ADC121_Offset"] = self.fuse_0x15C & 0x3FF
        return decoded_data

    def decode_0x160(self):
        """Decodes the fields from fuse address 0x160."""
        decoded_data = {}
        # 0x160:31-26 DCDC post-trim control value (6 bits)
        decoded_data["DCDC_post_trim"] = (self.fuse_0x160 >> 26) & 0x3F
        # 0x160:25-16 ADC122 Offset (10 bits)
        decoded_data["ADC122_Offset"] = (self.fuse_0x160 >> 16) & 0x3FF
        # 0x160:15-8 DAC1 Offset (8 bits)
        decoded_data["DAC1_Offset"] = (self.fuse_0x160 >> 8) & 0xFF
        # 0x160:7-0 DAC2 Offset (8 bits)
        decoded_data["DAC2_Offset"] = self.fuse_0x160 & 0xFF
        return decoded_data

    def decode_all(self):
        """Decodes all fields from all provided fuse addresses."""
        all_decoded_data = {}
        all_decoded_data["0x154"] = self.decode_0x154()
        all_decoded_data["0x158"] = self.decode_0x158()
        all_decoded_data["0x15C"] = self.decode_0x15C()
        all_decoded_data["0x160"] = self.decode_0x160()
        return all_decoded_data

    def get_valid_data_state(self):
        """
        Returns the state of the Valid_data field from fuse address 0x154.

        Returns:
            int: 1 if valid data is present, 0 if invalid
        """
        return (self.fuse_0x154 >> 31) & 0x1

    def is_valid_data(self):
        """
        Returns a boolean indicating if the fuse data is valid.

        Returns:
            bool: True if valid data is present, False if invalid
        """
        return bool(self.get_valid_data_state())

    def get_valid_data_description(self):
        """
        Returns a human-readable description of the Valid_data state.

        Returns:
            str: Description of the valid data state
        """
        state = self.get_valid_data_state()
        return "Valid" if state == 1 else "Invalid"

    def _print_0x154_details(self, fields, raw_val=None):
        """Print detailed breakdown for address 0x154"""

        isp_print_color("blue", "\t** Offset 0x154\n")
        isp_print_color(
            "blue",
            f"\t\t+ Valid Data     [31:31] = {fields['Valid_data']:1d}\t(0x{fields['Valid_data']:X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ BOR Abort      [30:30] = {fields['BOR_Abort']:1d}\t(0x{fields['BOR_Abort']:X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ Temp Sensor    [29:24] = {fields['Temp_Sensor']:d}\t(0x{fields['Temp_Sensor']:02X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ ADC VREF       [23:16] = {fields['ADC_VREF']:d}\t(0x{fields['ADC_VREF']:02X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ ADC24 Offset   [15:0 ] = {fields['ADC24_Offset']:d}\t(0x{fields['ADC24_Offset']:04X})\n",
        )

    #        isp_print_color('blue',
    #                        f"\t\tBit Visualization:\n")
    #        isp_print_color('blue',
    #                        f"\t\t  31 30 29-24   23-16     15-0\n")
    #        isp_print_color('blue',
    #                        f"\t\t  |  |  |       |         |\n")
    #        isp_print_color('blue',
    #                        f"\t\t  {fields['Valid_data']:1d}  {fields['BOR_Abort']:1d}  {fields['Temp_Sensor']:02X}      {fields['ADC_VREF']:02X}        {fields['ADC24_Offset']:04X}\n")

    def _print_0x158_details(self, fields, raw_val=None):
        """Print detailed breakdown for address 0x158"""
        #        print(f"\nField Breakdown:")
        isp_print_color("blue", "\t** Offset 0x158\n")
        isp_print_color(
            "blue",
            f"\t\t+ AON LDO        [31:28] = {fields['AON_LDO']:d}\t(0x{fields['AON_LDO']:X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ RET LDO        [27:24] = {fields['RET_LDO']:d}\t(0x{fields['RET_LDO']:X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ PMU BG         [23:20] = {fields['PMU_BG']:d}\t(0x{fields['PMU_BG']:X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ PERIPH BG      [19:16] = {fields['PERIPH_BG']:d}\t(0x{fields['PERIPH_BG']:X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ AON BG<4:1>    [15:12] = {fields['AON_BG_4_1']:d}\t(0x{fields['AON_BG_4_1']:X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ AON BG<0>      [11:11] = {fields['AON_BG_0']:d}\t(0x{fields['AON_BG_0']:X})\n",
        )
        # Combine AON BG fields
        aon_bg_full = (fields["AON_BG_4_1"] << 1) | fields["AON_BG_0"]
        #        print(f"\nCombined Fields:")
        isp_print_color(
            "blue",
            f"\t\t+ AON BG (full)  [15:11] = {aon_bg_full:d}\t(0x{aon_bg_full:02X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ Reserved       [10: 8] = {fields['Reserved_0x158']:d}\t(0x{fields['Reserved_0x158']:X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ DCDC Pre-trim  [ 7: 0] = {fields['DCDC_pre_trim']:d}\t(0x{fields['DCDC_pre_trim']:02X})\n",
        )

    def _print_0x15C_details(self, fields, raw_val=None):
        """Print detailed breakdown for address 0x15C"""
        #        print(f"\nField Breakdown:")
        isp_print_color("blue", "\t** Offset 0x15C\n")
        isp_print_color(
            "blue",
            f"\t\t+ HFRC 76.8MHz   [31:26] = {fields['HFRC']:d}\t(0x{fields['HFRC']:02X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ ADC120 Offset  [25:16] = {fields['ADC120_Offset']:d}\t(0x{fields['ADC120_Offset']:03X}\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ LFRC 32.7kHz   [15:10] = {fields['LFRC']:d}\t(0x{fields['LFRC']:02X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ ADC121 Offset  [ 9: 0] = {fields['ADC121_Offset']:d}\t(0x{fields['ADC121_Offset']:03X})\n",
        )

    def _print_0x160_details(self, fields, raw_val=None):
        """Print detailed breakdown for address 0x160"""
        #        print(f"\nField Breakdown:")
        isp_print_color("blue", "\t** Offset 0x160\n")
        isp_print_color(
            "blue",
            f"\t\t+ DCDC Post-trim [31:26] = {fields['DCDC_post_trim']:d}\t(0x{fields['DCDC_post_trim']:02X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ ADC122 Offset  [25:16] = {fields['ADC122_Offset']:d}\t(0x{fields['ADC122_Offset']:03X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ DAC1 Offset    [15: 8] = {fields['DAC1_Offset']:d}\t(0x{fields['DAC1_Offset']:02X})\n",
        )
        isp_print_color(
            "blue",
            f"\t\t+ DAC2 Offset    [ 7: 0] = {fields['DAC2_Offset']:d}\t(0x{fields['DAC2_Offset']:02X})\n",
        )

    def print_detailed_decode(self, decoded_data, raw_values=None):
        """Print detailed decode with register values and bit positions"""


#        for addr_str, fields in decoded_data.items():
#            addr_int = int(addr_str, 16)
#            raw_val = raw_values.get(addr_int, 0) if raw_values else 0
#            self._print_0x154_details(fields, 0)
#           print(f"\n{'='*60}")
#           print(f"ADDRESS {addr_str} (Raw Value: 0x{raw_val:08X} = {raw_val})")
#            print(f"{'='*60}")
#            print(f"Binary: {raw_val:032b}")
#            print(f"        31  27  23  19  15  11   7   3")
#            print(f"         |   |   |   |   |   |   |   |")

# Print each field with bit positions
#            if addr_str == '0x154':
#                self._print_0x154_details(fields, raw_val)
#            elif addr_str == '0x158':
#                self._print_0x158_details(fields, raw_val)
#            elif addr_str == '0x15C':
#                self._print_0x15C_details(fields, raw_val)
#            elif addr_str == '0x160':
#                self._print_0x160_details(fields, raw_val)


def trim_decoder(device_data):
    """
    trim_decoder interface to ISP

    Returns:
        None
    """
    start_address = 0x144

    # Convert hex string to bytes
    # Each hex character is 4 bits, so 2 hex characters make 1 byte.
    # The string needs to be an even length.
    bytes_data = bytes(device_data)

    # Calculate the byte offsets from the start_address
    offset_0x154 = 0x154 - start_address
    offset_0x158 = 0x158 - start_address
    offset_0x15C = 0x15C - start_address
    offset_0x160 = 0x160 - start_address

    # Extract 4-byte (32-bit) chunks and convert to integers
    # Use struct.unpack('>I', ...) for big-endian (network byte order) unsigned integer
    fuse_data_0x154 = struct.unpack("<I", bytes_data[offset_0x154 : offset_0x154 + 4])[
        0
    ]
    fuse_data_0x158 = struct.unpack("<I", bytes_data[offset_0x158 : offset_0x158 + 4])[
        0
    ]
    fuse_data_0x15C = struct.unpack("<I", bytes_data[offset_0x15C : offset_0x15C + 4])[
        0
    ]
    fuse_data_0x160 = struct.unpack("<I", bytes_data[offset_0x160 : offset_0x160 + 4])[
        0
    ]

    # Initialize the decoder with the extracted fuse data
    decoder = MfrDataTrimDecoder(
        fuse_data_0x154, fuse_data_0x158, fuse_data_0x15C, fuse_data_0x160
    )

    # Check if device is Analogue Trimmed or not
    if decoder.is_valid_data() is False:
        return

    # Decode all fields
    # decoded_results = decoder.decode_all()
    # decoded_results = decoder.decode_0x154()
    # print(json.dumps(decoded_results, indent=4))

    decoded_0x154 = decoder.decode_0x154()
    decoded_0x158 = decoder.decode_0x158()
    decoded_0x15C = decoder.decode_0x15C()
    decoded_0x160 = decoder.decode_0x160()

    decoder._print_0x154_details(decoded_0x154)
    decoder._print_0x158_details(decoded_0x158)
    decoder._print_0x15C_details(decoded_0x15C)
    decoder._print_0x160_details(decoded_0x160)


if __name__ == "__main__":
    # Play area to try out decode of Mfr Data
    actual_data = "04210771000000180000011600000000000015806100F983003C00B00000008C"
    # actual_data = "1519016E0000020E1000016A0000000000000000000000000000000010000040"

    # This is from 1st EAGLE Analouge trimmed parts
    actual_data = "050501060000020E0000012300000000000014803A5008A40000007000000080"
    actual_data_bytes = bytes.fromhex(actual_data)

    trim_decoder(actual_data_bytes)
