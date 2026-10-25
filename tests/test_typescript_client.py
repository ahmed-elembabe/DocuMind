import json

from scripts.export_openapi import OUTPUT, render


def test_typescript_types_are_up_to_date():
    # لو شكل أي طلب أو رد اتغير في الباك إند لازم الأنواع تتولد تاني
    # وإلا الواجهة الأمامية هتشتغل على شكل قديم من غير ما حد يحس
    # cd clients/typescript && npm run generate
    saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
    current = json.loads(render())

    # الاسم والنسخة بيتقروا من ملف الإعدادات فممكن يختلفوا من جهاز للتاني
    # info.title, info.version
    saved.pop("info")
    current.pop("info")

    assert saved == current, "الأنواع قديمة، شغّل: cd clients/typescript && npm run generate"
