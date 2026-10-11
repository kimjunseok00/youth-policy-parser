"""평가기 테스트.

자격 판정 버그는 거의 항상 '경계'에서 난다 (생일 당일, 정확히 150%, 정확히 12개월).
그래서 경계값을 집중적으로 검사한다.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from engine.evaluator import (
    Context,
    combine_and,
    combine_or,
    evaluate,
    evaluate_node,
    full_age,
    full_months,
    negate,
)
from engine.income import load_table
from engine.parser import parse
from engine.schemas import Policy, Profile, Verdict

ROOT = Path(__file__).resolve().parent.parent
P, F, U = Verdict.PASS, Verdict.FAIL, Verdict.UNKNOWN
AS_OF = date(2026, 10, 1)


def make_profile(**overrides) -> Profile:
    data = {
        "birth_date": "2001-03-15",
        "sido": "부산광역시",
        "sigungu": "부산진구",
        "residence_since": "2024-02-01",
        "education": "대학졸업",
        "employment": "구직중",
        "personal_income_monthly": 0,
        "household_size": 3,
        "household_income_monthly": 4_500_000,
        "current_benefits": [],
    }
    data.update(overrides)
    return Profile.model_validate(data)


def verdict(dsl: str, as_of: date = AS_OF, **profile) -> Verdict:
    """DSL 한 줄을 프로필로 판정한 결과만 돌려주는 도우미."""
    ctx = Context(make_profile(**profile), as_of, load_table())
    return evaluate_node(parse(dsl), ctx).verdict


# ---------------------------------------------------------------------------
# 날짜 계산
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("birth", "on", "expected"),
    [
        (date(2001, 3, 15), date(2026, 3, 14), 24),  # 생일 전날
        (date(2001, 3, 15), date(2026, 3, 15), 25),  # 생일 당일
        (date(2000, 12, 31), date(2026, 1, 1), 25),
    ],
)
def test_full_age(birth, on, expected):
    assert full_age(birth, on) == expected


@pytest.mark.parametrize(
    ("start", "on", "expected"),
    [
        (date(2024, 2, 1), date(2025, 2, 1), 12),  # 정확히 12개월
        (date(2024, 2, 1), date(2025, 1, 31), 11),  # 하루 모자람
        (date(2026, 9, 15), date(2026, 10, 1), 0),
    ],
)
def test_full_months(start, on, expected):
    assert full_months(start, on) == expected


# ---------------------------------------------------------------------------
# 3값 논리 (진리표 그대로)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("inputs", "and_result", "or_result"),
    [
        ([P, P], P, P),
        ([P, F], F, P),
        ([P, U], U, P),
        ([F, U], F, U),  # 하나라도 불충족이면 AND는 불충족 (확인필요가 있어도)
        ([U, U], U, U),
        ([F, F], F, F),
    ],
)
def test_three_valued_logic(inputs, and_result, or_result):
    assert combine_and(inputs) == and_result
    assert combine_or(inputs) == or_result


def test_negate():
    assert (negate(P), negate(F), negate(U)) == (F, P, U)


# ---------------------------------------------------------------------------
# 조건 8종 판정 + 경계값
# ---------------------------------------------------------------------------
def test_age_boundary_on_birthday():
    # 2026-03-15에 만 25세가 된다
    assert verdict("age(..24)", as_of=date(2026, 3, 14)) == P
    assert verdict("age(..24)", as_of=date(2026, 3, 15)) == F


def test_age_open_ranges():
    assert verdict("age(19..)") == P
    assert verdict("age(..39)") == P
    assert verdict("age(30..)") == F


def test_born_range_inclusive():
    assert verdict("born(2001-03-15..2008-12-31)") == P  # 시작일 당일 포함
    assert verdict("born(2001-03-16..)") == F


def test_region_and_sigungu():
    assert verdict('region("부산광역시")') == P
    assert verdict('region("부산광역시", "부산진구")') == P
    assert verdict('region("부산광역시", "해운대구")') == F
    assert verdict('region("서울특별시")') == F


def test_residence_months_boundary():
    # 2024-02-01 전입 → 2025-02-01에 정확히 12개월
    assert verdict("residence_months >= 12", as_of=date(2025, 2, 1)) == P
    assert verdict("residence_months >= 12", as_of=date(2025, 1, 31)) == F


def test_income_pct_household():
    # 3인 가구 기준중위소득 5,359,036원. 450만 원 ≈ 84.0%
    assert verdict("income_pct(household) <= 100") == P
    assert verdict("income_pct(household) <= 60") == F


def test_income_pct_exact_boundary():
    # 1인 가구 기준중위소득 2,564,238원 → 정확히 100%
    assert verdict("income_pct(personal) <= 100", personal_income_monthly=2_564_238) == P
    assert verdict("income_pct(personal) < 100", personal_income_monthly=2_564_238) == F


def test_income_abs():
    assert verdict("income(household) <= 4500000") == P
    assert verdict("income(household) < 4500000") == F


def test_education_and_employment():
    assert verdict('education in ["대학졸업", "대학원"]') == P
    assert verdict('employment in ["재직"]') == F


def test_receiving_and_exclusion():
    assert verdict('receiving("국민취업지원제도")') == F
    assert verdict('NOT receiving("국민취업지원제도")') == P
    assert verdict('NOT receiving("국민취업지원제도")', current_benefits=["국민취업지원제도"]) == F


def test_manual_is_always_unknown():
    assert verdict('manual("무주택")') == U
    assert verdict('NOT manual("군복무자")') == U


def test_fail_overrides_unknown():
    """확인 필요 조건이 있어도 다른 조건에서 떨어지면 불충족으로 확정."""
    assert verdict('age(..20) AND manual("무주택")') == F


# ---------------------------------------------------------------------------
# 정책 단위 판정 (앱이 받는 결과)
# ---------------------------------------------------------------------------
def make_policy(pid: str, dsl: str | None, amount: int | None = 1_000_000) -> Policy:
    return Policy(
        policy_id=pid,
        name=pid,
        agency="부산광역시",
        region="부산광역시",
        amount_krw=amount,
        amount_text="-",
        source_url="https://example.com",
        eligibility_text="원문",
        condition_dsl=dsl,
    )


def test_evaluate_sorting_and_total():
    policies = [
        make_policy("fail", "age(..20)", 9_000_000),
        make_policy("pass-small", 'region("부산광역시")', 200_000),
        make_policy("unknown", 'manual("무주택")', 5_000_000),
        make_policy("pass-big", "age(19..34)", 4_500_000),
    ]
    result = evaluate(make_profile(), policies, as_of=AS_OF)
    assert [r.policy_id for r in result.results] == ["pass-big", "pass-small", "unknown", "fail"]
    assert result.total_expected_krw == 4_700_000  # 충족 정책만 합산


def test_policy_without_dsl_is_unknown():
    result = evaluate(make_profile(), [make_policy("no-dsl", None)], as_of=AS_OF)
    assert result.results[0].verdict == U


def test_reason_tree_explains_failure():
    result = evaluate(
        make_profile(), [make_policy("rent", "age(19..34) AND income_pct(household) <= 60")], AS_OF
    )
    tree = result.results[0].reason
    assert tree.verdict == F
    assert "불충족 조건 1개" in tree.label
    failed = [c for c in tree.children if c.verdict == F]
    assert failed[0].category == "소득"
    assert "84.0%" in failed[0].detail


def test_real_examples_evaluate_without_error():
    """실제 부산 정책 예시가 전부 판정되는지 (오류 없이 3값 중 하나가 나오는지)."""
    examples = json.loads((ROOT / "data" / "examples" / "dsl_examples.json").read_text("utf-8"))
    policies = [make_policy(f"ex-{i}", e["dsl"]) for i, e in enumerate(examples)]
    result = evaluate(make_profile(), policies, as_of=AS_OF)
    assert len(result.results) == len(examples)
    assert all(r.verdict in (P, F, U) for r in result.results)


# ---------------------------------------------------------------------------
# 소득 기준표
# ---------------------------------------------------------------------------
def test_median_income_table():
    t = load_table()
    assert t.monthly(1) == 2_564_238
    assert t.monthly(4) == 6_494_738
    assert t.monthly(8) == 10_474_348  # 7인 + 959,198원 (고시 기준 8인 금액과 일치)
    assert round(t.pct(2_564_238, 1), 1) == 100.0
