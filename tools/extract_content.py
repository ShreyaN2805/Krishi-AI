"""Collect the agronomic advice the ML service returns, for translation.

The interface chrome is translated through frontend/i18n/<lang>.json. This
covers the other half: the crop tips, irrigation notes, fertilizer schedules
and rainfall advisories that come back inside API responses. They are the
sentences a farmer actually acts on, so leaving them in English would make a
"translated" app that still needs English to use.

Writes frontend/i18n/content.en.json, keyed by a slug of the English text.
translate_ui.py then produces content.<lang>.json from it, and the frontend
looks a returned string up by its English form, falling back to English.

    python tools/extract_content.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ml-service"))

OUT = ROOT / "frontend" / "i18n" / "content.en.json"


def slug(text: str) -> str:
    """Stable short key for a sentence, so files diff sensibly."""
    return "c_" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def collect() -> dict[str, str]:
    from app import knowledge, season

    strings: set[str] = set()

    for info in knowledge.CROP_INFO.values():
        if info.get("tip"):
            strings.add(info["tip"])
        if info.get("season"):
            strings.add(info["season"])

    strings.update(knowledge.SOIL_LABELS.values())
    strings.update(knowledge.IRRIGATION_LABELS.values())
    strings.update(knowledge.PREV_CROP_LABELS.values())
    strings.update(knowledge.GROWTH_STAGE_LABELS.values())
    strings.update(knowledge.FERTILIZER_TIPS.values())
    strings.update(knowledge.WATER_CROP_TIPS.values())

    for steps in knowledge.FERTILIZER_SCHEDULES.values():
        for stage, action in steps:
            strings.add(stage)
            strings.add(action)

    for by_season in knowledge.RAINFALL_ADVICE.values():
        strings.update(by_season.values())

    strings.update(season.SEASON_LABELS.values())
    strings.update(season.SEASON_NOTES.values())
    strings.update(season.REGION_LABELS.values())

    # Water-stress notes live in the router rather than the knowledge tables.
    from app.routers.water import _risk

    for value in (1.0, 3.0, 8.0):
        strings.update(_risk(value))

    # Names the API sends as data rather than prose: crops, states, months,
    # disease labels and the SHAP driver labels. A farmer who cannot read
    # "Wheat" cannot use a dropdown of English crop names, however well the
    # label beside it is translated. tc() matches case-insensitively, so one
    # entry per name is enough whatever casing each endpoint uses.
    from app import explain
    from app.config import ARTIFACT_DIR

    strings.update(knowledge.MONTHS)
    strings.update(explain.FEATURE_LABELS.values())
    strings.update(_encoder_classes())
    classes = json.loads((ARTIFACT_DIR / "disease" / "class_indices.json").read_text())
    for label in classes.values():
        crop, condition, _ = knowledge.prettify_disease_label(label)
        strings.update((crop, condition))

    return {slug(s): s for s in sorted(strings)}


def _encoder_classes() -> set[str]:
    """Crop and state names, read off the trained label encoders.

    The same source the /options endpoints use, so the catalogue can never
    drift from what the dropdowns actually offer. Needs the ML venv.
    """
    import joblib
    from app.config import ARTIFACT_DIR

    names: set[str] = set()
    for path in ("crop/label_encoder.pkl", "fertilizer/le_crop.pkl",
                 "water/le_crop.pkl", "rainfall/le_state.pkl"):
        try:
            names.update(str(c).title() for c in joblib.load(ARTIFACT_DIR / path).classes_)
        except Exception as exc:  # noqa: BLE001
            print(f"  {path} skipped: {exc}")
    return names


def main() -> None:
    content = collect()
    OUT.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    words = sum(len(v.split()) for v in content.values())
    print(f"{len(content)} strings ({words} words) -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
