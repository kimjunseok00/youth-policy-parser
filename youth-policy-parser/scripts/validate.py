"""data/policies/*.json 검증 스크립트.

채팅으로 변환한 정책 파일은 반드시 이 스크립트를 통과해야 저장소에 넣는다.
검사 항목: 스키마(필드·형식), 파일 이름 = policy_id, DSL 문법·의미, 중복수혜 참조.

실행: uv run python scripts/validate.py
"""

import sys
from pathlib import Path

from pydantic import ValidationError

# 저장소 루트를 import 경로에 추가 (scripts/ 안에서 실행해도 engine을 찾을 수 있게)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.benefits import BENEFIT_NAMES  # noqa: E402
from engine.nodes import Receiving, iter_predicates  # noqa: E402
from engine.parser import DSLError, parse  # noqa: E402
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
        # DSL이 있으면 파서로 검사한다. 문법 오류가 있는 데이터는 저장소에 들어오면 안 된다.
        if policy.condition_dsl:
            try:
                ast = parse(policy.condition_dsl)
            except DSLError as e:
                failures += 1
                print(f"❌ {path.name}: DSL 오류\n{e}\n")
                continue
            # receiving("이름")은 혜택 이름 사전에 있는 이름만 허용 (화면 선택지와 일치해야 판정됨)
            unknown = [
                n.benefit
                for n in iter_predicates(ast)
                if isinstance(n, Receiving) and n.benefit not in BENEFIT_NAMES
            ]
            if unknown:
                failures += 1
                print(f"❌ {path.name}: 혜택 이름 사전에 없는 receiving 이름 {unknown}")
                print("   → data/reference/benefits.json에 추가하거나 이름을 맞추세요.\n")
                continue
        seen_ids[policy.policy_id] = path
        status = "DSL 통과" if policy.condition_dsl else "DSL 없음 → 확인 필요"
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
