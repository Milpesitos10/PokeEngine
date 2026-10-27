"""Start the API despite the project's current folder name containing a hyphen."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
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
api_module = importlib.import_module(f"{PACKAGE_NAME}.api")

if __name__ == "__main__":
    uvicorn.run(api_module.app, host="127.0.0.1", port=8000)
