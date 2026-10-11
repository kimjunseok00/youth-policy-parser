"""반사실 가이드 · 시간축 · 최적 조합 테스트.

실제 정책 데이터에 의존하지 않도록 테스트용 정책을 직접 만든다.
(데이터가 바뀌어도 기능 테스트는 깨지지 않게)
"""

from datetime import date

import pytest

from engine.counterfactual import culprits, near_misses, suggestions
from engine.evaluator import Context, evaluate
from engine.income import load_table
from engine.nodes import Age, InSet, Receiving, Region
from engine.optimizer import _solve_brute, _solve_pulp, conflict_pairs, optimize
from engine.parser import parse
from engine.schemas import Policy, Profile, Verdict
from engine.timeline import add_months, birthday, timeline

AS_OF = date(2026, 10, 10)


def profile(**kw) -> Profile:
    base = dict(
        birth_date="2001-03-15",
        sido="부산광역시",
        sigungu="부산진구",
        residence_since="2026-02-01",
        education="대학졸업",
        employment="미취업",
        personal_income_monthly=0,
        household_size=1,
        household_income_monthly=1_000_000,
        current_benefits=[],
    )
    base.update(kw)
    return Profile.model_validate(base)


def policy(pid: str, dsl: str, amount: int = 1_000_000, **kw) -> Policy:
    return Policy(
        policy_id=pid,
        name=pid,
        agency="테스트",
        region="부산광역시",
        amount_krw=amount,
        amount_text="-",
        source_url="https://example.com",
        eligibility_text="-",
        condition_dsl=dsl,
        **kw,
    )


def ctx(p: Profile, on: date = AS_OF) -> Context:
    return Context(p, on, load_table())


# ---------------------------------------------------------------------------
# 탈락 원인 찾기
# ---------------------------------------------------------------------------
def test_culprits_and_picks_only_failing_children():
    ast = parse('age(..20) AND region("부산광역시")')
    assert culprits(ast, ctx(profile())) == [(Age(None, 20), False)]


def test_culprits_or_blames_all_children():
    ast = parse('region("서울특별시") OR employment in ["재직"]')
    found = [pred for pred, _ in culprits(ast, ctx(profile()))]
    assert found == [Region("서울특별시"), InSet("employment", ("재직",))]


def test_culprits_under_not_flips_polarity():
    ast = parse('NOT receiving("국민취업지원제도")')
    p = profile(current_benefits=["국민취업지원제도"])
    assert culprits(ast, ctx(p)) == [(Receiving("국민취업지원제도"), True)]


# ---------------------------------------------------------------------------
# 근접 정책
# ---------------------------------------------------------------------------
def test_near_miss_only_single_cause():
    pols = [
        policy("one-cause", 'age(19..34) AND region("서울특별시")'),
        policy("two-causes", 'age(..20) AND region("서울특별시")'),
        policy("passes", "age(19..34)"),
    ]
    misses = near_misses(profile(), pols, AS_OF)
    assert [m.policy_id for m in misses] == ["one-cause"]
    assert misses[0].fixable_by == "행동"


def test_near_miss_income_shows_gap_in_won():
    # 1인 가구 기준중위소득 2,564,238원의 50% = 1,282,119원
    misses = near_misses(profile(), [policy("p", "income_pct(household) <= 30")], AS_OF)
    assert "%" in misses[0].gap and "원" in misses[0].gap


def test_near_miss_skips_closed_policy():
    closed = policy("closed", 'region("서울특별시")', apply_end=date(2026, 3, 1))
    assert near_misses(profile(), [closed], AS_OF) == []


# ---------------------------------------------------------------------------
# 행동 제안: 얻는 것과 잃는 것을 함께 계산한다
# ---------------------------------------------------------------------------
def test_suggestion_counts_gains_and_losses():
    pols = [
        policy("seoul-a", 'region("서울특별시")', 3_000_000),
        policy("seoul-b", 'region("서울특별시") AND age(19..34)', 1_000_000),
        policy("busan", 'region("부산광역시")', 500_000),
    ]
    s = suggestions(profile(), pols, AS_OF)
    move = next(x for x in s if "서울특별시" in x.action)
    assert set(move.gained) == {"seoul-a", "seoul-b"}
    assert move.lost == ["busan"]
    assert move.net_amount_krw == 3_500_000


def test_suggestion_benefit_exit():
    p = profile(current_benefits=["국민취업지원제도"])
    s = suggestions(p, [policy("challenge", 'NOT receiving("국민취업지원제도")')], AS_OF)
    assert s[0].action == "'국민취업지원제도' 수혜 종료"


def test_no_suggestion_for_unchangeable_conditions():
    # 나이·학력은 행동으로 바꿀 수 없으니 제안하지 않는다
    pols = [policy("old", "age(40..)"), policy("grad", 'education in ["대학원"]')]
    assert suggestions(profile(), pols, AS_OF) == []


def test_no_suggestion_to_quit_job():
    # 재직자에게 '퇴사'를 권하지 않는다
    pols = [policy("jobless", 'employment in ["미취업"]')]
    assert suggestions(profile(employment="재직"), pols, AS_OF) == []


# ---------------------------------------------------------------------------
# 시간축
# ---------------------------------------------------------------------------
def test_birthday_and_add_months():
    assert birthday(date(2001, 3, 15), 25) == date(2026, 3, 15)
    assert birthday(date(2004, 2, 29), 21) == date(2025, 3, 1)  # 평년 2/29생
    assert add_months(date(2026, 2, 1), 12) == date(2027, 2, 1)
    assert add_months(date(2026, 1, 31), 1) == date(2026, 3, 1)


def test_timeline_gain_by_residence():
    # 2026-02-01 전입 → 12개월은 2027-02-01
    ev = timeline(profile(), [policy("stay", "residence_months >= 12")], AS_OF)
    assert [(e.on, e.kind) for e in ev] == [(date(2027, 2, 1), "자격 발생")]


def test_timeline_loss_by_age_cap():
    # 2001-03-15생은 2036-03-15에 만 35세 → 34세 상한 정책은 그날부터 불충족
    ev = timeline(profile(), [policy("cap", "age(..34)")], AS_OF, horizon_days=365 * 10)
    assert ev[0].kind == "자격 상실" and ev[0].on == date(2036, 3, 15)


def test_timeline_deadline_only_when_soon_and_possible():
    soon = policy("soon", "age(19..)", apply_end=date(2026, 10, 30))
    later = policy("later", "age(19..)", apply_end=date(2027, 6, 30))
    failing = policy("fail", "age(..20)", apply_end=date(2026, 10, 30))
    kinds = [(e.policy_id, e.kind) for e in timeline(profile(), [soon, later, failing], AS_OF)]
    assert kinds == [("soon", "신청 마감")]


# ---------------------------------------------------------------------------
# 최적 조합
# ---------------------------------------------------------------------------
def test_conflict_pairs_are_symmetric():
    a = policy("a", "age(19..)", exclusive_with=["b"])
    b = policy("b", "age(19..)")
    assert conflict_pairs([a, b]) == {frozenset({"a", "b"})}


def test_optimizer_picks_larger_of_conflicting_pair():
    pols = [
        policy("a", "age(19..)", 3_600_000, exclusive_with=["b"]),
        policy("b", "age(19..)", 2_500_000),
        policy("c", "age(19..)", 200_000),
    ]
    plan = optimize(evaluate(profile(), pols, AS_OF), pols)
    assert [r.policy_id for r in plan.selected] == ["a", "c"]
    assert plan.total_krw == 3_800_000 and plan.simple_sum_krw == 6_300_000
    assert plan.excluded[0].policy_name == "b" and plan.excluded[0].because_of == "a"


def test_optimizer_prefers_two_small_over_one_big():
    # a(5) vs b(3)+c(3): a가 b, c와 각각 충돌 → b+c(6)가 정답 (탐욕법이면 틀리는 경우)
    pols = [
        policy("a", "age(19..)", 5, exclusive_with=["b", "c"]),
        policy("b", "age(19..)", 3),
        policy("c", "age(19..)", 3),
    ]
    plan = optimize(evaluate(profile(), pols, AS_OF), pols)
    assert {r.policy_id for r in plan.selected} == {"b", "c"}


def test_pulp_and_brute_force_agree():
    pols = [policy(f"p{i}", "age(19..)", 100 * (i + 1)) for i in range(8)]
    pairs = {frozenset({"p0", "p1"}), frozenset({"p1", "p2"}), frozenset({"p5", "p7"})}
    cands = evaluate(profile(), pols, AS_OF).results
    pulp_total = sum(
        int(c.policy_id[1:]) + 1 for c in cands if c.policy_id in _solve_pulp(cands, pairs)
    )
    brute_total = sum(
        int(c.policy_id[1:]) + 1 for c in cands if c.policy_id in _solve_brute(cands, pairs)
    )
    assert pulp_total == brute_total


@pytest.mark.parametrize("include_unknown", [False, True])
def test_optimizer_skips_closed_and_respects_unknown_option(include_unknown):
    pols = [
        policy("open", "age(19..)", 100),
        policy("closed", "age(19..)", 999, apply_end=date(2026, 1, 1)),
        policy("unknown", 'manual("무주택")', 50),
    ]
    plan = optimize(evaluate(profile(), pols, AS_OF), pols, include_unknown=include_unknown)
    ids = {r.policy_id for r in plan.selected}
    assert "closed" not in ids
    assert ("unknown" in ids) == include_unknown


def test_total_excludes_closed_policies():
    pols = [
        policy("open", "age(19..)", 100),
        policy("closed", "age(19..)", 999, apply_end=date(2026, 1, 1)),
    ]
    result = evaluate(profile(), pols, AS_OF)
    assert result.total_expected_krw == 100
    assert {r.policy_id: r.is_open for r in result.results} == {"open": True, "closed": False}
    assert all(r.verdict == Verdict.PASS for r in result.results)
