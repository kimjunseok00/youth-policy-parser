"""검수 결과(data/curation/*.json)를 초안(data/drafts/)에 반영한다.

    uv run python scripts/curate.py data/curation/batch1.json

curation 파일 형식: { "<plcyNo>": {"amount_krw", "amount_text", "condition_dsl", "eligibility_text"?,
                                  "exclusion_text"?, "name"?, "review": [공고문 대조 항목...]} }
- 초안의 policy 부분을 덮어쓰고, 스키마·DSL 문법을 통과하는지 검사한다.
- review에는 '사람이 공식 페이지에서 확인할 항목'만 남긴다. 확인을 끝내면 비우고 promote.py로 승격한다.
- API 본문(온통청년)을 읽고 옮긴 값이므로 확인 전까지는 2차 출처다 (docs/data_sources.md).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.parser import DSLError, parse  # noqa: E402
from engine.schemas import Policy  # noqa: E402

OVERRIDABLE = (
    "name", "amount_krw", "amount_text", "condition_dsl", "eligibility_text",
    "exclusion_text", "exclusive_with", "apply_start", "apply_end",
)  # fmt: skip


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    edits = json.loads(Path(sys.argv[1]).read_text("utf-8"))
    bad = 0
    for plcy_no, e in edits.items():
        path = ROOT / "data" / "drafts" / f"ontong-{plcy_no}.json"
        if not path.exists():
            print(f"[없음] {path.name}")
            bad += 1
            continue
        d = json.loads(path.read_text("utf-8"))
        for k in OVERRIDABLE:
            if k in e:
                d["policy"][k] = e[k]
        d["review"] = e.get("review", d["review"])
        try:
            pol = Policy.model_validate(d["policy"])
            parse(pol.condition_dsl or "")
        except (DSLError, ValueError) as err:
            print(f"[오류] {path.name} {d['policy']['name']}: {err}")
            bad += 1
            continue
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print(f"[반영] {pol.name}  (확인할 항목 {len(d['review'])}개)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
