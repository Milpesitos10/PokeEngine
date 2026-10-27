"""Synchronize the Gen. IV type-effectiveness chart into SQL Server."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
PACKAGE_NAME = "pokeengine_project"
spec = importlib.util.spec_from_file_location(
    PACKAGE_NAME,
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
if spec is None or spec.loader is None:
    raise RuntimeError("No se pudo preparar el paquete del motor.")
package = importlib.util.module_from_spec(spec)
sys.modules[PACKAGE_NAME] = package
spec.loader.exec_module(package)

from pokeengine_project import pokeapi


if __name__ == "__main__":
    count = pokeapi.synchronize_gen4_type_chart()
    print(f"Sincronización completada: {count} combinaciones de tipos Gen. IV.")
