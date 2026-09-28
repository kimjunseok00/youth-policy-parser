"""data/policies/*.json 검증 스크립트.

채팅으로 변환한 정책 파일은 반드시 이 스크립트를 통과해야 저장소에 넣는다.
지금은 스키마(필드·형식)만 검사한다. 4회차에 문법이 확정되면 DSL 파싱 검사를 추가한다.

실행: uv run python scripts/validate.py
"""

import sys
from pathlib import Path

from pydantic import ValidationError

# 저장소 루트를 import 경로에 추가 (scripts/ 안에서 실행해도 engine을 찾을 수 있게)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.schemas import Policy  # noqa: E402

POLICY_DIR = ROOT / "data" / "policies"


def validate_all() -> int:
    """모든 정책 파일을 검사하고 실패 개수를 돌려준다."""
    files = sorted(POLICY_DIR.glob("*.json"))
    failures = 0
    seen_ids: dict[str, Path] = {}

    for path in files:
        try:
            policy = Policy.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as e:
            failures += 1
            print(f"❌ {path.name}\n{e}\n")
            continue

        # 파일 이름과 policy_id를 일치시켜야 중복수혜 관계(exclusive_with)를 추적하기 쉽다.
        if path.stem != policy.policy_id:
            failures += 1
            print(f"❌ {path.name}: 파일 이름과 policy_id({policy.policy_id})가 다릅니다.\n")
            continue
        if policy.policy_id in seen_ids:
            failures += 1
            print(f"❌ {path.name}: policy_id 중복 ({seen_ids[policy.policy_id].name})\n")
            continue
        seen_ids[policy.policy_id] = path
        status = "DSL 있음" if policy.condition_dsl else "DSL 없음 → 확인 필요"
        print(f"✅ {path.name} ({status})")

    # exclusive_with가 존재하지 않는 정책을 가리키면 최적 조합 계산이 틀어진다.
    for path in seen_ids.values():
        policy = Policy.model_validate_json(path.read_text(encoding="utf-8"))
        for other in policy.exclusive_with:
            if other not in seen_ids:
                failures += 1
                print(f"❌ {path.name}: exclusive_with의 '{other}' 정책 파일이 없습니다.")

    print(f"\n총 {len(files)}건 중 실패 {failures}건")
    return failures


if __name__ == "__main__":
    sys.exit(1 if validate_all() else 0)
