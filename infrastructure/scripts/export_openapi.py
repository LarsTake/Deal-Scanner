import json
from pathlib import Path

from deal_scanner_api.main import app

target = Path("schemas/openapi.json")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False), encoding="utf-8")
print(target)
