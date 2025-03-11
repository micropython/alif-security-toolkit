#!/usr/bin/python3
from isp.isp_core import *
from isp.isp_util import *


class OSPIMemoryHandler:
    def __init__(self, isp, start_address, size, sector_size_mask):
        self.isp = isp
        self.start_address = start_address
        self.size = size
        self.sector_size_mask = sector_size_mask

    def erase_sectors(self):
        """
        Erase OSPI from start address to end of OSPI
        """
        erase_start = self.start_address & 0x0FFFFFFF
        total_size = self.size - erase_start
        OSPI_SECTOR_SIZE = 4 * 1024  # Support for other sector sizes must be added
        num_sectors = total_size // OSPI_SECTOR_SIZE  # self.sector_size
        progress_bar("OSPI Erase", 0, num_sectors, True, unit="sectors")

        offset = erase_start
        for count in range(num_sectors):
            isp_ospi_recovery_sector_erase(self.isp, offset, self.sector_size_mask)

            progress_bar(
                f"OSPI Erase {OSPI_SECTOR_SIZE / 1024}k sectors",
                count + 1,
                num_sectors,
                True,
                unit="sectors",
            )

            offset += OSPI_SECTOR_SIZE

        print()
