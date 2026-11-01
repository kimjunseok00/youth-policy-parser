"""페르소나 회귀 스냅샷(tests/regression/persona_expected.json)을 현재 판정으로 다시 만든다.

    uv run python scripts/update_snapshot.py

정책을 추가·승격하거나 조건식을 고친 뒤, 바뀐 판정을 눈으로 확인하고 나서 실행한다.
스냅샷은 '의도하지 않은 판정 변화'를 잡는 안전망이라, 확인 없이 갱신하면 그 역할을 잃는다.
기준일(as_of)은 기존 값을 유지한다.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.evaluator import evaluate, load_policies  # noqa: E402
from engine.schemas import Profile  # noqa: E402

SNAP = ROOT / "tests" / "regression" / "persona_expected.json"


def main() -> int:
    old = json.loads(SNAP.read_text("utf-8"))
    personas = json.loads((ROOT / "data" / "personas.json").read_text("utf-8"))
    policies = load_policies()
    new = {"as_of": old["as_of"], "note": old["note"], "expected": {}}
    for per in personas:
        res = evaluate(
            Profile.model_validate(per["profile"]), policies, date.fromisoformat(old["as_of"])
        )
        new["expected"][per["label"]] = {r.policy_id: r.verdict.value for r in res.results}
        before = old["expected"].get(per["label"], {})
        changed = [
            f"{pid}: {before.get(pid, '(없음)')} → {v}"
            for pid, v in new["expected"][per["label"]].items()
            if before.get(pid) != v
        ]
        print(f"[{per['label']}] 정책 {len(policies)}건, 바뀐 판정 {len(changed)}건")
        for line in changed:
            print("   ", line)
    SNAP.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"\n저장: {SNAP.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
