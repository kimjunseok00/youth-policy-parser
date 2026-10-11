"""반사실 가이드: "이것만 바꾸면 N건 추가".

두 가지를 계산한다.

1. 근접 정책 (near miss)
   불충족 정책 중 '탈락 원인 조건이 딱 하나'인 정책. 그 조건과 내 값의 차이를 보여준다.
   기획서의 "조건 하나만 어긋난 정책 추천"이 이것이다.

2. 행동 제안 (suggestion)
   사용자가 실제로 바꿀 수 있는 것(전입, 구직 등록, 기존 지원 종료)만 골라
   프로필을 바꿔 '전체 정책을 다시 판정'한다. 그래서 얻는 정책뿐 아니라 잃는 정책도 보인다.
   (예: 서울로 전입하면 부산 정책을 잃는다) → 순효과(net)로 정렬한다.

나이·학력·소득처럼 당장 바꿀 수 없는 조건은 제안하지 않는다.
나이·거주기간처럼 '시간이 지나면' 풀리는 조건은 timeline 모듈이 다룬다.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel

from engine.evaluator import (
    COMP_WORD,
    Context,
    evaluate,
    evaluate_node,
    full_age,
    full_months,
    is_open,
    negate,
)
from engine.income import MedianIncomeTable, load_table
from engine.nodes import (
    Age,
    And,
    Born,
    IncomeAbs,
    IncomePct,
    InSet,
    Node,
    Not,
    Or,
    Predicate,
    Receiving,
    Region,
    Residence,
)
from engine.parser import DSLError, parse
from engine.schemas import EvaluationResult, Policy, Profile, Verdict

PASS, FAIL, UNKNOWN = Verdict.PASS, Verdict.FAIL, Verdict.UNKNOWN

# 사용자가 '행동'으로 바꿀 수 있는 취업상태 전환만 허용 (퇴사를 권하지는 않는다)
EMPLOYMENT_ACTIONS = {
    ("미취업", "구직중"): "고용24에서 구직 등록",
    ("구직중", "미취업"): "구직 등록 해제",
}


class NearMiss(BaseModel):
    """조건 하나만 어긋난 정책."""

    policy_id: str
    policy_name: str
    amount_krw: int | None
    condition: str  # 어긋난 조건 (정책이 요구하는 것)
    gap: str  # 내 상황과의 차이
    category: str
    fixable_by: str  # "행동" | "시간" | "변경 어려움"


class Suggestion(BaseModel):
    """프로필 하나를 바꿨을 때 전체 판정이 어떻게 달라지는지."""

    action: str
    category: str
    gained: list[str]  # 불충족 → 충족/확인 필요가 된 정책 이름
    lost: list[str]  # 충족/확인 필요 → 불충족이 된 정책 이름
    gained_amount_krw: int
    lost_amount_krw: int

    @property
    def net_amount_krw(self) -> int:
        return self.gained_amount_krw - self.lost_amount_krw


# ---------------------------------------------------------------------------
# 탈락 원인 찾기: 어떤 '조건 노드'가 불충족을 만들었는가
# ---------------------------------------------------------------------------
def culprits(node: Node, ctx: Context, negated: bool = False) -> list[tuple[Predicate, bool]]:
    """불충족의 원인이 된 조건들을 (조건, NOT 아래인지) 쌍으로 돌려준다.

    - AND: 불충족인 자식들이 원인
    - OR : (불충족이면) 모든 자식이 원인
    - NOT: 안쪽 조건이 '충족'이라서 탈락한 것이므로 극성을 뒤집어 찾는다
    """

    def eff(n: Node, neg: bool) -> Verdict:
        v = evaluate_node(n, ctx).verdict
        return negate(v) if neg else v

    match node:
        case And(children):
            return [
                c for ch in children if eff(ch, negated) == FAIL for c in culprits(ch, ctx, negated)
            ]
        case Or(children):
            # NOT 아래의 OR는 드모르간에 의해 AND처럼 동작한다
            picked = [ch for ch in children if eff(ch, negated) == FAIL] if negated else children
            return [c for ch in picked for c in culprits(ch, ctx, negated)]
        case Not(child):
            return culprits(child, ctx, not negated)
        case _:
            return [(node, negated)] if eff(node, negated) == FAIL else []


def _open_only(policies: Iterable[Policy], as_of: date) -> list[Policy]:
    return [p for p in policies if is_open(p, as_of)]


def _parse_or_none(policy: Policy) -> Node | None:
    if not policy.condition_dsl:
        return None
    try:
        return parse(policy.condition_dsl)
    except DSLError:
        return None


# ---------------------------------------------------------------------------
# 1. 근접 정책
# ---------------------------------------------------------------------------
def _gap(pred: Predicate, negated: bool, ctx: Context) -> tuple[str, str, str]:
    """(조건 설명, 차이 설명, 해결 방법 분류)"""
    p = ctx.profile
    match pred:
        case Age(lo, hi):
            age = full_age(p.birth_date, ctx.as_of)
            if lo is not None and age < lo:
                return f"만 {lo}세 이상", f"지금 만 {age}세 → {lo - age}년 뒤 충족", "시간"
            return f"만 {hi}세 이하", f"지금 만 {age}세 → 상한 초과", "변경 어려움"
        case Born(start, end):
            return f"{start or ''}~{end or ''} 출생", f"{p.birth_date} 출생", "변경 어려움"
        case Region(sido, sigungu):
            where = f"{sido} {sigungu}" if sigungu else sido
            return f"{where} 거주", f"지금 {p.sido} {p.sigungu}", "행동"
        case Residence(comp, months):
            mine = full_months(p.residence_since, ctx.as_of)
            return (
                f"현 주소 거주 {months}개월 {COMP_WORD[comp]}",
                f"지금 {mine}개월 → {max(months - mine, 0)}개월 뒤 충족",
                "시간",
            )
        case IncomePct(scope, comp, pct):
            income = (
                p.personal_income_monthly if scope == "personal" else p.household_income_monthly
            )
            size = 1 if scope == "personal" else p.household_size
            limit = int(ctx.income_table.monthly(size) * pct / 100)
            mine = ctx.income_table.pct(income, size)
            who = "본인" if scope == "personal" else "가구"
            return (
                f"{who}소득 기준중위소득 {pct}% {COMP_WORD[comp]}",
                f"지금 {mine:.1f}% (기준선 월 {limit:,}원, 차이 월 {abs(income - limit):,}원)",
                "변경 어려움",
            )
        case IncomeAbs(scope, comp, won):
            income = (
                p.personal_income_monthly if scope == "personal" else p.household_income_monthly
            )
            return f"월소득 {won:,}원 {COMP_WORD[comp]}", f"지금 월 {income:,}원", "변경 어려움"
        case InSet(field, values):
            mine = (p.education if field == "education" else p.employment).value
            fixable = (
                "행동" if any((mine, v) in EMPLOYMENT_ACTIONS for v in values) else "변경 어려움"
            )
            want = f"{pred.CATEGORY.value}: {' / '.join(values)}"
            if negated:
                return f"{want}에 해당하지 않음", f"지금 {mine}", fixable
            return want, f"지금 {mine}", fixable
        case Receiving(benefit):
            if negated:
                return f"'{benefit}' 미수혜", "지금 수혜 중 → 종료 후 신청 가능", "행동"
            return f"'{benefit}' 수혜", "지금 수혜 중 아님", "변경 어려움"
    return str(pred), "", "변경 어려움"


def near_misses(
    profile: Profile,
    policies: Iterable[Policy],
    as_of: date,
    table: MedianIncomeTable | None = None,
) -> list[NearMiss]:
    """불충족 정책 중 탈락 원인이 하나뿐인 정책. 금액이 큰 순."""
    ctx = Context(profile, as_of, table or load_table())
    out: list[NearMiss] = []
    for policy in _open_only(policies, as_of):
        ast = _parse_or_none(policy)
        if ast is None or evaluate_node(ast, ctx).verdict != FAIL:
            continue
        causes = culprits(ast, ctx)
        if len(causes) != 1:
            continue
        pred, neg = causes[0]
        condition, gap, fixable = _gap(pred, neg, ctx)
        out.append(
            NearMiss(
                policy_id=policy.policy_id,
                policy_name=policy.name,
                amount_krw=policy.amount_krw,
                condition=condition,
                gap=gap,
                category=pred.CATEGORY.value,
                fixable_by=fixable,
            )
        )
    out.sort(key=lambda m: -(m.amount_krw or 0))
    return out


# ---------------------------------------------------------------------------
# 2. 행동 제안
# ---------------------------------------------------------------------------
def _candidate_changes(
    profile: Profile, policies: list[Policy], ctx: Context
) -> dict[str, tuple[str, dict]]:
    """불충족 원인 중 '행동으로 바꿀 수 있는 것'에서 프로필 변경안을 만든다.

    반환: {변경 키: (행동 설명, 프로필에 덮어쓸 값)}  ← 같은 변경은 한 번만 시도
    """
    changes: dict[str, tuple[str, dict]] = {}
    for policy in policies:
        ast = _parse_or_none(policy)
        if ast is None or evaluate_node(ast, ctx).verdict != FAIL:
            continue
        for pred, neg in culprits(ast, ctx):
            match pred:
                case Region(sido, sigungu) if not neg:
                    where = f"{sido} {sigungu}" if sigungu else sido
                    if sigungu:
                        new_sigungu = sigungu
                    elif sido == profile.sido:
                        new_sigungu = profile.sigungu
                    else:
                        new_sigungu = ""  # 시·도만 요구하면 구·군은 정하지 않는다
                    # 전입하면 거주 기간은 0부터 다시 센다
                    changes[f"region:{where}"] = (
                        f"{where}(으)로 전입",
                        {"sido": sido, "sigungu": new_sigungu, "residence_since": ctx.as_of},
                    )
                case InSet("employment", values) if not neg:
                    for v in values:
                        key = (profile.employment.value, v)
                        if key in EMPLOYMENT_ACTIONS:
                            changes[f"employment:{v}"] = (
                                EMPLOYMENT_ACTIONS[key],
                                {"employment": v},
                            )
                case Receiving(benefit) if neg:
                    remaining = [b for b in profile.current_benefits if b.strip() != benefit]
                    changes[f"benefit:{benefit}"] = (
                        f"'{benefit}' 수혜 종료",
                        {"current_benefits": remaining},
                    )
    return changes


def suggestions(
    profile: Profile,
    policies: Iterable[Policy],
    as_of: date,
    table: MedianIncomeTable | None = None,
) -> list[Suggestion]:
    """행동 하나씩을 적용해 전체를 다시 판정하고, 순효과가 큰 순으로 돌려준다."""
    policies = _open_only(policies, as_of)  # 마감된 정책은 바꿔도 받을 수 없다
    table = table or load_table()
    ctx = Context(profile, as_of, table)
    before = evaluate(profile, policies, as_of, table)
    out: list[Suggestion] = []

    for key, (action, patch) in _candidate_changes(profile, policies, ctx).items():
        changed = profile.model_copy(update=patch)
        after = evaluate(changed, policies, as_of, table)
        gained, lost = _diff(before, after)
        if not gained:
            continue
        out.append(
            Suggestion(
                action=action,
                category=key.split(":")[0],
                gained=[r.policy_name for r in gained],
                lost=[r.policy_name for r in lost],
                gained_amount_krw=sum(r.amount_krw or 0 for r in gained),
                lost_amount_krw=sum(r.amount_krw or 0 for r in lost),
            )
        )
    out.sort(key=lambda s: (-s.net_amount_krw, -len(s.gained)))
    return out


def _diff(before: EvaluationResult, after: EvaluationResult):
    prev = {r.policy_id: r for r in before.results}
    gained = [r for r in after.results if prev[r.policy_id].verdict == FAIL and r.verdict != FAIL]
    lost = [r for r in after.results if prev[r.policy_id].verdict != FAIL and r.verdict == FAIL]
    return gained, lost
