"""Convert notebooks/*.ipynb to site/public/notebooks/*.html"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
NOTEBOOKS_SRC = ROOT / "notebooks"
NOTEBOOKS_OUT = ROOT / "site" / "public" / "notebooks"

NOTEBOOKS_OUT.mkdir(parents=True, exist_ok=True)

notebooks = list(NOTEBOOKS_SRC.glob("*.ipynb"))
if not notebooks:
    print("No notebooks found.")
    sys.exit(0)

errors = []
for nb in notebooks:
    result = subprocess.run(
        [
            "jupyter", "nbconvert",
            "--to", "html",
            "--output-dir", str(NOTEBOOKS_OUT),
            str(nb),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        errors.append((nb.name, result.stderr))
        print(f"FAIL  {nb.name}")
    else:
        print(f"OK    {nb.name}")

if errors:
    for name, err in errors:
        print(f"\n--- {name} ---\n{err}", file=sys.stderr)
    sys.exit(1)
