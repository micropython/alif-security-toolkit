# Global control of input and output paths.

import os.path
from pathlib import Path

TOOLKIT_DIR = None
CERT_INPUT_DIR = None
CONFIG_INPUT_DIR = None
FIRMWARE_INPUT_DIR = None
OUTPUT_DIR = None


def configure(config_dir=None, firmware_dir=None, output_dir=None):
    global TOOLKIT_DIR
    global CERT_INPUT_DIR
    global CONFIG_INPUT_DIR
    global FIRMWARE_INPUT_DIR
    global OUTPUT_DIR

    TOOLKIT_DIR = Path(os.path.dirname(os.path.dirname(__file__)))
    CERT_INPUT_DIR = TOOLKIT_DIR / "cert"

    if config_dir is None:
        # Use Toolkit directory as the default.
        CONFIG_INPUT_DIR = TOOLKIT_DIR / "build/config"
    else:
        CONFIG_INPUT_DIR = Path(config_dir)

    # If no directory specified, FIRMWARE_INPUT_DIR should not be used.
    if firmware_dir is not None:
        FIRMWARE_INPUT_DIR = Path(firmware_dir)

    # If no directory specified, OUTPUT_DIR should not be used.
    if output_dir is not None:
        OUTPUT_DIR = Path(output_dir)
