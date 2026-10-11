"""평가기: (DSL 조건식 + 프로필 + 기준일) → 판정 + 탈락 사유 트리.

설계 원칙
1. 3값 논리(Kleene): 충족 / 불충족 / 확인필요.
   - AND: 하나라도 불충족 → 불충족, 전부 충족 → 충족, 나머지 → 확인필요
   - OR : 하나라도 충족 → 충족, 전부 불충족 → 불충족, 나머지 → 확인필요
   - NOT: 충족 ↔ 불충족, 확인필요는 그대로
   → manual() 조건이 섞여 있어도, 다른 조건에서 이미 탈락하면 '불충족'으로 확정된다.
2. 모든 판정은 기준일(as_of)에 대해 계산한다. 기준일만 바꾸면 "언제부터 되는지"를 알 수 있다.
3. 노드마다 '왜'를 남긴다(label = 조건, detail = 내 값). 화면은 이 트리를 그대로 그린다.

앱에서 쓰는 진입점:
    from engine.evaluator import evaluate, load_policies
    result = evaluate(profile, load_policies(), as_of=date(2026, 10, 1))
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from engine.income import MedianIncomeTable, load_table
from engine.nodes import (
    Age,
    And,
    Born,
    Comp,
    IncomeAbs,
    IncomePct,
    InSet,
    Manual,
    Node,
    Not,
    Or,
    Receiving,
    Region,
    Residence,
)
from engine.parser import DSLError, parse
from engine.schemas import EvaluationResult, Policy, PolicyResult, Profile, ReasonNode, Verdict

POLICY_DIR = Path(__file__).resolve().parent.parent / "data" / "policies"

PASS, FAIL, UNKNOWN = Verdict.PASS, Verdict.FAIL, Verdict.UNKNOWN

# 한국 표준시. 서머타임이 없어 고정 오프셋이면 충분하다 (tzdata 패키지 없이도 동작)
KST = timezone(timedelta(hours=9), "KST")


def today_kst() -> date:
    """오늘 날짜(한국 기준). 배포 서버는 해외에 있어 date.today()를 쓰면 하루 어긋날 수 있다."""
    return datetime.now(KST).date()


# 비교 연산자를 한국어 조건 문구로 (예: "<=" → "이하")
COMP_WORD = {Comp.LE: "이하", Comp.GE: "이상", Comp.LT: "미만", Comp.GT: "초과", Comp.EQ: ""}
SCOPE_WORD = {"personal": "본인", "household": "가구"}


# ---------------------------------------------------------------------------
# 날짜 계산 (기준일 기준)
# ---------------------------------------------------------------------------
def full_age(birth: date, on: date) -> int:
    """만 나이. 생일 당일에 한 살 늘어난다."""
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def full_months(start: date, on: date) -> int:
    """start부터 on까지 꽉 찬 개월 수. 2024-02-01 → 2025-02-01 = 12개월."""
    months = (on.year - start.year) * 12 + (on.month - start.month)
    return months - (on.day < start.day)


# ---------------------------------------------------------------------------
# 3값 논리 조합
# ---------------------------------------------------------------------------
def combine_and(verdicts: Iterable[Verdict]) -> Verdict:
    vs = list(verdicts)
    if FAIL in vs:
        return FAIL
    return PASS if all(v == PASS for v in vs) else UNKNOWN


def combine_or(verdicts: Iterable[Verdict]) -> Verdict:
    vs = list(verdicts)
    if PASS in vs:
        return PASS
    return FAIL if all(v == FAIL for v in vs) else UNKNOWN


def negate(v: Verdict) -> Verdict:
    return {PASS: FAIL, FAIL: PASS, UNKNOWN: UNKNOWN}[v]


def _bool(ok: bool) -> Verdict:
    return PASS if ok else FAIL


# ---------------------------------------------------------------------------
# 노드 평가
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Context:
    """평가에 필요한 모든 입력. 평가 함수는 이 밖의 상태를 읽지 않는다 (테스트가 쉬워진다)."""

    profile: Profile
    as_of: date
    income_table: MedianIncomeTable


def evaluate_node(node: Node, ctx: Context) -> ReasonNode:
    """AST 노드 하나를 평가해 사유 트리 노드를 만든다. (재귀)"""
    match node:
        case And(children):
            kids = [evaluate_node(c, ctx) for c in children]
            return ReasonNode(
                label="다음 조건을 모두 충족",
                verdict=combine_and(k.verdict for k in kids),
                children=kids,
            )
        case Or(children):
            kids = [evaluate_node(c, ctx) for c in children]
            return ReasonNode(
                label="다음 중 하나 이상 충족",
                verdict=combine_or(k.verdict for k in kids),
                children=kids,
            )
        case Not(child):
            # 제외 조건: "X에 해당하면 탈락"을 "X에 해당하지 않음"이라는 하나의 조건으로 보여준다.
            inner = evaluate_node(child, ctx)
            return inner.model_copy(
                update={"label": f"제외 대상 아님: {inner.label}", "verdict": negate(inner.verdict)}
            )
        case _:
            return _evaluate_predicate(node, ctx)


def _evaluate_predicate(node: Node, ctx: Context) -> ReasonNode:
    """조건 8종 각각의 판정. label은 '정책이 요구하는 것', detail은 '내 값'."""
    p = ctx.profile
    category = node.CATEGORY.value

    def leaf(label: str, verdict: Verdict, detail: str) -> ReasonNode:
        return ReasonNode(label=label, verdict=verdict, detail=detail, category=category)

    match node:
        case Age(lo, hi):
            age = full_age(p.birth_date, ctx.as_of)
            ok = (lo is None or age >= lo) and (hi is None or age <= hi)
            if lo is not None and hi is not None:
                label = f"만 {lo}~{hi}세"
            elif hi is not None:
                label = f"만 {hi}세 이하"
            else:
                label = f"만 {lo}세 이상"
            return leaf(label, _bool(ok), f"만 {age}세")

        case Born(start, end):
            b = p.birth_date
            ok = (start is None or b >= start) and (end is None or b <= end)
            label = f"{start or ''} ~ {end or ''} 출생".strip()
            return leaf(label, _bool(ok), f"{b} 출생")

        case Region(sido, sigungu):
            ok = p.sido == sido and (sigungu is None or p.sigungu == sigungu)
            label = f"{sido} {sigungu} 거주" if sigungu else f"{sido} 거주"
            return leaf(label, _bool(ok), f"{p.sido} {p.sigungu} 거주")

        case Residence(comp, months):
            mine = full_months(p.residence_since, ctx.as_of)
            label = f"현 주소 거주 {months}개월 {COMP_WORD[comp]}".strip()
            return leaf(label, _bool(comp.check(mine, months)), f"현 주소 {mine}개월 거주")

        case IncomePct(scope, comp, pct):
            income, size = _income_of(p, scope)
            mine = ctx.income_table.pct(income, size)
            who = SCOPE_WORD[scope]
            label = f"{who}소득 기준중위소득 {pct}% {COMP_WORD[comp]}".strip()
            detail = f"{who}소득 월 {income:,}원 = 기준중위소득 {mine:.1f}% ({size}인 가구 기준)"
            return leaf(label, _bool(comp.check(mine, pct)), detail)

        case IncomeAbs(scope, comp, won):
            income, _ = _income_of(p, scope)
            who = SCOPE_WORD[scope]
            label = f"{who} 월소득 {won:,}원 {COMP_WORD[comp]}".strip()
            return leaf(label, _bool(comp.check(income, won)), f"{who} 월소득 {income:,}원")

        case InSet(field, values):
            mine = (p.education if field == "education" else p.employment).value
            label = f"{category}: {' / '.join(values)}"
            return leaf(label, _bool(mine in values), f"현재 {mine}")

        case Receiving(benefit):
            receiving = benefit in {b.strip() for b in p.current_benefits}
            detail = "현재 수혜 중" if receiving else "현재 수혜 중 아님"
            return leaf(f"'{benefit}' 수혜", _bool(receiving), detail)

        case Manual(text):
            return ReasonNode(
                label=text,
                verdict=UNKNOWN,
                detail="자동 판정할 수 없는 조건입니다. 공고문이나 담당 기관에서 확인하세요.",
                source_quote=text,
                category=category,
            )

    raise TypeError(f"평가할 수 없는 노드: {node!r}")


def _income_of(p: Profile, scope: str) -> tuple[int, int]:
    """(월소득, 기준 가구원 수). 본인 소득은 1인 가구 기준으로 환산한다."""
    if scope == "personal":
        return p.personal_income_monthly, 1
    return p.household_income_monthly, p.household_size


# ---------------------------------------------------------------------------
# 정책 단위 판정
# ---------------------------------------------------------------------------
def _leaves(node: ReasonNode) -> list[ReasonNode]:
    if not node.children:
        return [node]
    return [leaf for c in node.children for leaf in _leaves(c)]


def _summary(tree: ReasonNode) -> str:
    """정책 카드 맨 위에 보일 한 줄 요약."""
    leaves = _leaves(tree)
    if tree.verdict == PASS:
        return "모든 조건 충족"
    if tree.verdict == FAIL:
        failed = [x.label for x in leaves if x.verdict == FAIL]
        return f"불충족 조건 {len(failed)}개: {', '.join(failed[:2])}" + (
            " 외" if len(failed) > 2 else ""
        )
    unknown = [x.label for x in leaves if x.verdict == UNKNOWN]
    return f"확인 필요 조건 {len(unknown)}개: {', '.join(unknown[:2])}" + (
        " 외" if len(unknown) > 2 else ""
    )


def evaluate_policy(policy: Policy, ctx: Context) -> PolicyResult:
    """정책 1건 판정. DSL이 없거나 깨져 있으면 억지로 판정하지 않고 '확인 필요'로 둔다."""
    if not policy.condition_dsl:
        tree = ReasonNode(
            label="자격요건이 아직 조건식으로 변환되지 않았습니다",
            verdict=UNKNOWN,
            detail="원문을 직접 확인하세요.",
            source_quote=policy.eligibility_text,
        )
    else:
        try:
            ast = parse(policy.condition_dsl)
            body = evaluate_node(ast, ctx)
            # 최상위가 AND면 그 자식들을 바로 보여주는 편이 읽기 쉽다.
            children = body.children if isinstance(ast, And) else [body]
        except DSLError as e:
            body = ReasonNode(
                label="조건식 오류로 판정하지 못했습니다", verdict=UNKNOWN, detail=str(e)
            )
            children = [body]
        tree = ReasonNode(
            label="", verdict=body.verdict, source_quote=policy.eligibility_text, children=children
        )
    tree = tree.model_copy(update={"label": tree.label or _summary(tree)})

    return PolicyResult(
        policy_id=policy.policy_id,
        policy_name=policy.name,
        agency=policy.agency,
        verdict=tree.verdict,
        amount_krw=policy.amount_krw,
        amount_text=policy.amount_text,
        apply_start=policy.apply_start,
        apply_end=policy.apply_end,
        is_open=is_open(policy, ctx.as_of),
        source_url=policy.source_url,
        reason=tree,
    )


def is_open(policy: Policy, on: date) -> bool:
    """기준일에 신청 기간 안인지. 기간이 비어 있으면(상시) 열려 있는 것으로 본다."""
    if policy.apply_start and on < policy.apply_start:
        return False
    return not (policy.apply_end and on > policy.apply_end)


ORDER = {PASS: 0, UNKNOWN: 1, FAIL: 2}


def evaluate(
    profile: Profile,
    policies: Iterable[Policy],
    as_of: date | None = None,
    income_table: MedianIncomeTable | None = None,
) -> EvaluationResult:
    """프로필 1개에 대해 모든 정책을 판정한다. (앱이 부르는 유일한 함수)

    정렬: 충족 → 확인 필요 → 불충족. 같은 판정 안에서는 신청 가능한 것 먼저, 그다음 금액 큰 순.
    """
    ctx = Context(profile, as_of or today_kst(), income_table or load_table())
    results = [evaluate_policy(p, ctx) for p in policies]
    results.sort(key=lambda r: (ORDER[r.verdict], not r.is_open, -(r.amount_krw or 0)))
    return EvaluationResult(as_of=ctx.as_of, results=results)


def load_policies(directory: Path = POLICY_DIR) -> list[Policy]:
    """data/policies/*.json 전체를 읽는다. (validate.py를 통과한 파일만 저장소에 있다는 전제)"""
    return [
        Policy.model_validate_json(f.read_text(encoding="utf-8"))
        for f in sorted(directory.glob("*.json"))
    ]
