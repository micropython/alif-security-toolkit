#!/usr/bin/python3
from operator import index

from operator import index

from isp_core import *
from isp_util import *
import time


class OSPIMemoryHandler:
    # Supported sector sizes (bytes)
    SECTOR_4K = 4 * 1024
    SECTOR_32K = 32 * 1024
    SECTOR_128K = 128 * 1024

    def __init__(
        self,
        isp,
        start_address,
        size,
        enable_4k=True,
        enable_32k=True,
        enable_128k=True,
    ):

        # At least one sector size must be enabled
        if not (enable_4k or enable_32k or enable_128k):
            raise ValueError("At least one sector size must be enabled")

        self.isp = isp
        self.original_start_address = start_address
        self.original_size = size

        # Store enabled sector sizes (prioritized: largest first)
        self.enabled_sectors = []
        if enable_128k:
            self.enabled_sectors.append(self.SECTOR_128K)
        if enable_32k:
            self.enabled_sectors.append(self.SECTOR_32K)
        if enable_4k:
            self.enabled_sectors.append(self.SECTOR_4K)

        # Sort descending (priority: larger sectors first)
        self.enabled_sectors.sort(reverse=True)

        # ---- SIZE NORMALIZATION ----
        MIN_SIZE = self.SECTOR_4K

        # Ensure minimum size is 4K
        if size < MIN_SIZE:
            adjustment = MIN_SIZE - size
            start_address -= adjustment
            size = MIN_SIZE

        # Align size to 4K (round up)
        remainder = size % MIN_SIZE
        if remainder != 0:
            adjustment = MIN_SIZE - remainder
            size += adjustment
            start_address -= adjustment

        # Prevent negative address (lower bound protection)
        if start_address < 0:
            start_address = 0

        self.start_address = start_address
        self.size = size

    def erase_sectors(self):
        """
        Erase OSPI from start address using optimal sector combination
        """

        erase_start = self.start_address & 0x0FFFFFFF
        total_size = self.size

        remaining_size = total_size
        sectors_plan = []

        # Build erase plan using enabled sector sizes
        for sector_size in self.enabled_sectors:
            count = remaining_size // sector_size
            if count > 0:
                sectors_plan.append((sector_size, count))
                remaining_size -= count * sector_size

        # Safety fallback (should not happen if 4K is enabled)
        if remaining_size > 0:
            if self.SECTOR_4K not in self.enabled_sectors:
                raise RuntimeError("Cannot cover remaining size without 4K sectors")
            count = remaining_size // self.SECTOR_4K
            if count > 0:
                sectors_plan.append((self.SECTOR_4K, count))
                remaining_size -= count * self.SECTOR_4K

        total_sectors = sum(count for _, count in sectors_plan)

        if self.original_start_address != self.start_address:
            print(f"Original Start : {hex(self.original_start_address)}")
            print(f"Adjusted Start : {hex(self.start_address)}")
        else:
            print(f"Start Address  : {hex(self.start_address)}")

        if self.original_size != self.size:
            print(f"Original Size : {format_bytes(self.original_size)}")
            print(f"Adjusted Size : {format_bytes(self.size)}")
        else:
            print(f"Size           : {format_bytes(self.size)}")

        print(f"Erase Plan:")
        for each in sectors_plan:
            print(f"  - {each[1]} sectors of size {format_bytes(each[0])}\n")

        progress_bar("OSPI Erase", 0, total_sectors, True, unit="sectors")

        start_time = time.time()
        offset = erase_start
        progress_count = 0

        for sector_size, count in sectors_plan:
            for _ in range(count):
                # Select mask dynamically based on sector size
                if sector_size == self.SECTOR_4K:
                    sector_mask = ERASE_SECTOR_SIZE_4K
                elif sector_size == self.SECTOR_32K:
                    sector_mask = ERASE_SECTOR_SIZE_32K
                elif sector_size == self.SECTOR_128K:
                    sector_mask = ERASE_SECTOR_SIZE_128K
                else:
                    raise ValueError("Unsupported sector size")
                # print(f"Erasing sector at offset {hex(offset)} with size {sector_size} bytes (mask {hex(sector_mask)})")
                isp_ospi_recovery_sector_erase(self.isp, offset, sector_mask)

                progress_count += 1

                progress_bar(
                    f"OSPI Erase ({sector_size // 1024}K)",
                    progress_count,
                    total_sectors,
                    True,
                    unit="sectors",
                )
                offset += sector_size

        end_time = time.time()
        print()
        print("Done in {:10.2f} seconds\n".format(end_time - start_time))


def format_bytes(size):
    """
    Convert a size in bytes to a human-readable string.

    Args:
        size (int or float): Size in bytes

    Returns:
        str: Formatted size string
    """
    if size < 0:
        raise ValueError("Size must be non-negative")

    units = ["B", "KB", "MB", "GB"]
    index = 0

    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1

    if size.is_integer():
        formatted = f"{int(size)} {units[index]}"
    else:
        formatted = f"{size:.2f} {units[index]}"
    return formatted
