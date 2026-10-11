"""Ladowanie modulow z czysta logika bez importu custom_components.librus_apix.__init__ (i bez Home Assistant)."""

import importlib
import importlib.util
import sys
import types
from pathlib import Path

_PKG = "librus_pure"
_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "librus_apix"


def load(name: str):
    if _PKG not in sys.modules:
        pkg = types.ModuleType(_PKG)
        pkg.__path__ = [str(_DIR)]
        sys.modules[_PKG] = pkg
    return importlib.import_module(f"{_PKG}.{name}")


def load_package():
    """Zaladuj caly pakiet (z __init__.py) pod nazwa librus_full - wymaga HA albo atrap z _ha_stub."""
    import _ha_stub  # noqa: F401 - instaluje atrapy, gdy HA nie ma

    nazwa = "librus_full"
    if nazwa not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            nazwa, _DIR / "__init__.py", submodule_search_locations=[str(_DIR)]
        )
        modul = importlib.util.module_from_spec(spec)
        sys.modules[nazwa] = modul
        spec.loader.exec_module(modul)
    return sys.modules[nazwa]


def load_full(name: str):
    load_package()
    return importlib.import_module(f"librus_full.{name}")
