"""Messages for the GUI when a native DSP library of a universal driver cannot be used.

The libraries in the repository are built on an x86-64 PC. On other processors
(e.g. ARM64 of a Raspberry Pi) they are present but cannot be loaded; the setup tool
then builds them with 'make' (cohi_setup.py, ensure_native_libs). Before, the drivers
reported such a library as 'not found'.
"""
import ctypes
import os
import platform
import struct

ELF_MACHINES = {0x03: "x86 (32 bit)", 0x3E: "x86-64", 0x28: "ARM (32 bit)", 0xB7: "ARM64"}
THIS_MACHINE = {"x86_64": 0x3E, "amd64": 0x3E, "i386": 0x03, "i686": 0x03,
                "aarch64": 0xB7, "arm64": 0xB7, "armv7l": 0x28, "armv6l": 0x28}


def elf_machine(path):
    """processor of an ELF shared library (e_machine), None if not an ELF file"""
    try:
        with open(path, "rb") as fh:
            head = fh.read(20)
    except OSError:
        return None
    if len(head) < 20 or head[:4] != b"\x7fELF":
        return None
    return struct.unpack("<H" if head[5] == 1 else ">H", head[18:20])[0]


def wrong_processor(path):
    """(processor of the library, processor of this computer) if they differ, else None"""
    lib = elf_machine(path)
    here = THIS_MACHINE.get(platform.machine().lower())
    if lib is None or here is None or lib == here:
        return None
    return ELF_MACHINES.get(lib, hex(lib)), platform.machine()


def lib_problem(basename, dirs, build_dir):
    """text for the GUI why the library <basename>.so / .dll in one of dirs cannot be used"""
    windows = platform.system() == "Windows"
    name = basename + (".dll" if windows else ".so")
    remedy = ("Please run the COHIWizard setup again." if windows else
              f"Please run the COHIWizard setup again (it builds the library for this computer) "
              f"or build it with:  cd {build_dir} && make")
    paths = [os.path.join(d, name) for d in dirs if os.path.isfile(os.path.join(d, name))]
    if not paths:
        return f"{name} not found.\n{remedy}"
    wrong = wrong_processor(paths[0])
    if wrong:
        return (f"{name} is present, but was built for another processor "
                f"({wrong[0]}; this computer: {wrong[1]}).\n{remedy}")
    try:
        ctypes.CDLL(paths[0])
    except OSError as exc:
        return (f"{name} cannot be loaded: {exc}\n"
                f"Usually a system library is missing (e.g. libosmo-fl2k). {remedy}")
    return f"{name} could not be loaded when COHIWizard was started. Please restart COHIWizard."
