"""판정 1회를 '개인을 알아볼 수 없는 요약'으로 바꾼다 (지자체 리포트용 익명 통계).

저장하는 것: 연령대(5세 단위), 구·군(부산만, 그 외는 '부산 외'), 취업상태, 학력, 가구원 수(5인 이상 묶음),
            가구소득 구간(기준중위소득 20%p 단위), 군 복무 여부, 정책별 판정, 정책별 탈락 조건 라벨
저장하지 않는 것: 생년월일, 정확한 소득, 전입일, 현재 받는 지원, 이름·연락처·IP 등 식별 정보

리포트는 같은 묶음이 5명 미만이면 보여주지 않는다 (MIN_GROUP). 소수 집단에서 개인이 드러나는 것을 막는다.
"""

from __future__ import annotations

from engine.dates import full_age
from engine.income import MedianIncomeTable, load_table
from engine.schemas import EvaluationResult, Profile, ReasonNode, Verdict

SCHEMA_VERSION = 1
MIN_GROUP = 5  # 이보다 작은 묶음은 리포트에 표시하지 않는다


def age_band(age: int) -> str:
    if age < 19:
        return "18세 이하"
    if age >= 40:
        return "40세 이상"
    if age < 25:
        return "19~24세"  # 청년 정책 하한(19세)부터 첫 구간
    lo = (age // 5) * 5
    return f"{lo}~{lo + 4}세"


def income_band(pct: float) -> str:
    """기준중위소득 대비 20%p 구간. 200% 이상은 하나로 묶는다."""
    if pct >= 200:
        return "200% 이상"
    lo = int(pct // 20) * 20
    return f"{lo}~{lo + 20}%"


def _fail_labels(node: ReasonNode) -> list[str]:
    if not node.children:
        return [node.label] if node.verdict == Verdict.FAIL else []
    return [x for k in node.children if k.verdict == Verdict.FAIL for x in _fail_labels(k)]


def anonymize(
    profile: Profile, result: EvaluationResult, table: MedianIncomeTable | None = None
) -> dict:
    """저장해도 되는 요약만 남긴 dict. (JSON으로 그대로 저장)"""
    table = table or load_table()
    pct = table.pct(profile.household_income_monthly, profile.household_size)
    return {
        "v": SCHEMA_VERSION,
        "month": result.as_of.strftime("%Y-%m"),  # 날짜는 월 단위까지만
        "age_band": age_band(full_age(profile.birth_date, result.as_of)),
        "area": profile.sigungu if profile.sido == "부산광역시" else "부산 외",
        "employment": profile.employment.value,
        "education": profile.education.value,
        "household": str(profile.household_size) if profile.household_size < 5 else "5인 이상",
        "income_band": income_band(pct),
        "served_military": profile.military_months > 0,
        "verdicts": {r.policy_id: r.verdict.value for r in result.results},
        "fail_reasons": {
            r.policy_id: _fail_labels(r.reason) for r in result.results if r.verdict == Verdict.FAIL
        },
    }
