"""엔진 보완 기능 테스트: 입력 검증 · 군 복무 연장 · 확인 질문 답변 · 통과 가능성."""

from datetime import date

import pytest
from pydantic import ValidationError

from engine.dates import add_months, age_for_cap, birthday
from engine.evaluator import Context, evaluate, evaluate_node, likelihood
from engine.income import load_table
from engine.nodes import Age
from engine.parser import DSLSemanticError, parse
from engine.schemas import Policy, Profile, ReasonNode, Verdict
from engine.timeline import timeline

P, F, U = Verdict.PASS, Verdict.FAIL, Verdict.UNKNOWN
AS_OF = date(2026, 10, 10)


def profile(**kw) -> Profile:
    base = dict(
        birth_date="1990-05-01",  # 2026-10-10 기준 만 36세
        sido="부산광역시",
        sigungu="북구",
        residence_since="2020-08-01",
        education="대학졸업",
        employment="구직중",
        personal_income_monthly=0,
        household_size=2,
        household_income_monthly=3_000_000,
    )
    base.update(kw)
    return Profile.model_validate(base)


def policy(pid: str, dsl: str, amount: int = 1_000_000) -> Policy:
    return Policy(
        policy_id=pid,
        name=pid,
        agency="-",
        region="부산광역시",
        amount_krw=amount,
        amount_text="-",
        source_url="https://example.com",
        eligibility_text="-",
        condition_dsl=dsl,
    )


def verdict(dsl: str, answers=None, **kw) -> Verdict:
    ctx = Context(profile(**kw), AS_OF, load_table(), answers or {})
    return evaluate_node(parse(dsl), ctx).verdict


# ---------------------------------------------------------------------------
# 입력 검증
# ---------------------------------------------------------------------------
def test_personal_income_cannot_exceed_household():
    with pytest.raises(ValidationError, match="가구 월소득"):
        profile(personal_income_monthly=3_000_000, household_income_monthly=500_000)


def test_equal_personal_and_household_is_ok():
    profile(household_size=1, personal_income_monthly=2_000_000, household_income_monthly=2_000_000)


def test_military_months_range():
    with pytest.raises(ValidationError):
        profile(military_months=-1)


# ---------------------------------------------------------------------------
# 군 복무 연장
# ---------------------------------------------------------------------------
def test_age_for_cap_subtracts_service_up_to_limit():
    birth = date(1990, 5, 1)
    assert age_for_cap(birth, AS_OF, 0, 72) == 36
    assert age_for_cap(birth, AS_OF, 21, 72) == 34  # 생일이 21개월 늦춰진 것과 같다
    assert age_for_cap(birth, AS_OF, 100, 36) == 33  # 연장은 최대 36개월까지만


def test_military_extension_only_applies_to_upper_bound():
    assert verdict("age(..34)", military_months=21) == F  # 연장 규칙이 없는 정책
    assert verdict("age(..34, military=72)", military_months=21) == P
    assert verdict("age(..34, military=72)", military_months=0) == F
    assert verdict("age(37..)", military_months=24) == F  # 하한에는 적용 안 함


def test_military_parse_and_round_trip():
    node = parse("age(18..34, military=72)")
    assert node == Age(18, 34, 72)
    assert parse(node.to_dsl()) == node


def test_military_needs_upper_bound():
    with pytest.raises(DSLSemanticError):
        parse("age(19.., military=24)")


def test_timeline_loss_date_shifts_with_service():
    # 1990-05-01생, 복무 21개월 → 상한 판정 생일은 1992-02-01 → 만 35세가 되는 날 2027-02-01
    pol = [policy("p", "age(..34, military=72)")]
    ev = timeline(profile(military_months=21), pol, AS_OF)
    assert [(e.kind, e.on) for e in ev] == [("자격 상실", date(2027, 2, 1))]
    assert birthday(add_months(date(1990, 5, 1), 21), 35) == date(2027, 2, 1)


# ---------------------------------------------------------------------------
# 확인 질문 답변
# ---------------------------------------------------------------------------
def test_manual_answer_resolves_unknown():
    assert verdict('manual("무주택")') == U
    assert verdict('manual("무주택")', answers={"무주택": True}) == P
    assert verdict('manual("무주택")', answers={"무주택": False}) == F


def test_answer_under_not_means_excluded():
    # "군복무자에 해당한다"고 답하면 제외 조건에 걸려 불충족
    assert verdict('NOT manual("군복무자")', answers={"군복무자": True}) == F
    assert verdict('NOT manual("군복무자")', answers={"군복무자": False}) == P


def test_answers_flow_through_evaluate():
    pols = [policy("rent", 'age(19..) AND manual("무주택")')]
    assert evaluate(profile(), pols, AS_OF).results[0].verdict == U
    assert evaluate(profile(), pols, AS_OF, answers={"무주택": True}).results[0].verdict == P


# ---------------------------------------------------------------------------
# 통과 가능성 · 기대 수령액
# ---------------------------------------------------------------------------
def leaf(v: Verdict) -> ReasonNode:
    return ReasonNode(label="x", verdict=v)


def test_likelihood_values():
    assert likelihood(ReasonNode(label="", verdict=P, children=[leaf(P)])) == 1.0
    assert likelihood(ReasonNode(label="", verdict=F, children=[leaf(F)])) == 0.0
    two_unknown = ReasonNode(label="", verdict=U, children=[leaf(P), leaf(U), leaf(U)])
    assert likelihood(two_unknown) == 0.25


def test_unknown_sorted_by_expected_amount():
    pols = [
        policy(
            "big-but-uncertain", 'manual("a") AND manual("b") AND manual("c")', 4_000_000
        ),  # 50만
        policy("small-but-likely", 'manual("a")', 2_000_000),  # 100만
    ]
    r = evaluate(profile(), pols, AS_OF)
    assert [x.policy_id for x in r.results] == ["small-but-likely", "big-but-uncertain"]
    assert r.results[0].expected_krw == 1_000_000


def test_notice_manual_is_neutral_and_never_asked():
    # 안내문은 조건이 아니므로 판정에 영향을 주지 않는다 (붙어 있어도 '충족'이 될 수 있어야 함)
    text = "※ 세부 자격은 공고문 확인"
    assert verdict(f'manual("{text}")') == Verdict.PASS
    assert verdict(f'manual("{text}")', answers={text: False}) == Verdict.PASS
    assert verdict(f'age(19..39) AND manual("{text}")') == Verdict.PASS
    node = evaluate(profile(), [policy("n", f'manual("{text}")')], AS_OF).results[0].reason
    node = node.children[0] if node.children else node  # 루트는 정책 요약 노드
    assert node.notice and node.label == "세부 자격은 공고문 확인"


def test_manual_questions_skip_notices_and_closed_policies():
    from app import manual_questions

    pols = [
        policy("open-q", 'manual("무주택") AND manual("※ 공고문 확인")'),
        policy("closed-q", 'manual("청약통장")').model_copy(update={"apply_end": date(2026, 1, 1)}),
    ]
    qs = manual_questions(evaluate(profile(), pols, AS_OF))
    assert [q for q, _ in qs] == ["무주택"]
