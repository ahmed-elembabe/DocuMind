"""
بيكتب وصف الواجهة في ملف عشان أنواع التايب سكريبت تتولد منه
ومن غير ما نحتاج السيرفر يبقى شغال
uv run python -m scripts.export_openapi
"""

import json
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "clients" / "typescript" / "openapi.json"


def render() -> str:
    # الحروف العربي بتتكتب زي ما هي مش بالأكواد بتاعتها عشان الملف يتقري
    # ensure_ascii=False
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
