"""Independent, manually specified answers for the simulated workbook."""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "demo"
DEMO = DATA / "demo_arg_data.xlsx"
EXPECTED = json.loads((DATA / "expected.json").read_text(encoding="utf-8"))
