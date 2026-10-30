"""검수를 마친 초안을 정식 정책으로 옮긴다: data/drafts/<id>.json → data/policies/<id>.json

    uv run python scripts/promote.py data/drafts/ontong-xxxx.json

하는 일
1. 초안의 'policy' 부분이 스키마와 DSL 문법을 통과하는지 검사
2. 금액(amount_krw)이 비어 있거나 review 항목이 남아 있으면 경고하고 멈춘다 (--force로 무시)
3. data/policies/에 저장하고 초안 파일에 promoted 표시
반영 후에는 scripts/validate.py와 pytest를 다시 돌린다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.parser import DSLError, parse  # noqa: E402
from engine.schemas import Policy  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("draft", type=Path)
    ap.add_argument("--force", action="store_true", help="남은 review 항목이 있어도 옮김")
    args = ap.parse_args()

    d = json.loads(args.draft.read_text("utf-8"))
    policy = Policy.model_validate(d["policy"])
    try:
        parse(policy.condition_dsl or "")
    except DSLError as e:
        print(f"[오류] 조건식 오류: {e}")
        return 1
    problems = list(d.get("review", []))
    if policy.amount_krw is None:
        problems.append("amount_krw가 비어 있음")
    if problems and not args.force:
        print("[멈춤] 아직 확인할 항목이 있습니다. 확인을 마쳤으면 review 목록을 비우세요:")
        for p in problems:
            print(f"  - {p}")
        return 1
    out = ROOT / "data" / "policies" / f"{policy.policy_id}.json"
    out.write_text(policy.model_dump_json(indent=2) + "\n", "utf-8")
    d["status"] = "promoted"
    args.draft.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"[통과] {out.relative_to(ROOT)} 저장. 이어서 validate.py와 pytest를 실행하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
