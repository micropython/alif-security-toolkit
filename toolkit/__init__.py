"""
Expose toolkit command modules through importable entry points.
Note that 'app-write-mram.py' includes hyphens and is
therefor not a valid python package.
"""

import sys
from importlib import import_module
from pathlib import Path

# The path insertions are compensating for legacy
# imports that treated isp/ and utils/common/ as top-level folders.
_PACKAGE_DIR = Path(__file__).parent
for _module_dir in (
    _PACKAGE_DIR / "utils",
    _PACKAGE_DIR / "isp",
    _PACKAGE_DIR.parent / "utils",
    _PACKAGE_DIR.parent / "isp",
):
    if _module_dir.is_dir():
        sys.path.insert(0, str(_module_dir))


def _entrypoint(module_name):
    def run():
        import_module(f".{module_name}", __name__).main()

    return run


app_assets_gen = _entrypoint("app-assets-gen")
app_gen_rot = _entrypoint("app-gen-rot")
app_gen_toc = _entrypoint("app-gen-toc")
app_provision = _entrypoint("app-provision")
app_secure_debug = _entrypoint("app-secure-debug")
app_sign_image = _entrypoint("app-sign-image")
app_write_mram = _entrypoint("app-write-mram")
maintenance = _entrypoint("maintenance")
tools_config = _entrypoint("tools-config")
update_system_package = _entrypoint("updateSystemPackage")
