"""시간축 판정: "언제부터 되는지", "언제까지 되는지", "언제 마감되는지".

평가기는 기준일(as_of)만 바꾸면 다른 날의 판정을 계산할 수 있다.
그래서 날짜를 하루씩 훑지 않고, 판정이 바뀔 수 있는 '후보 날짜'만 골라 다시 판정한다.

후보 날짜
- age(lo..)       : 만 lo세가 되는 생일 → 자격 발생 후보
- age(..hi)       : 만 hi+1세가 되는 생일 → 자격 상실 후보
- residence_months: 거주 N개월을 채우는 날 → 자격 발생 후보
- apply_end       : 신청 마감일 → 마감 임박 알림
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from pydantic import BaseModel

from engine.evaluator import Context, evaluate_node, is_open
from engine.income import MedianIncomeTable, load_table
from engine.nodes import Age, Comp, Residence, iter_predicates
from engine.parser import DSLError, parse
from engine.schemas import Policy, Profile, Verdict

PASS, FAIL, UNKNOWN = Verdict.PASS, Verdict.FAIL, Verdict.UNKNOWN


class TimelineEvent(BaseModel):
    on: date
    kind: str  # "자격 발생" | "자격 상실" | "신청 마감"
    policy_id: str
    policy_name: str
    amount_krw: int | None
    detail: str


def birthday(birth: date, age: int) -> date:
    """만 age세가 되는 날. 2월 29일생은 평년에는 3월 1일로 본다."""
    year = birth.year + age
    try:
        return birth.replace(year=year)
    except ValueError:
        return date(year, 3, 1)


def add_months(d: date, months: int) -> date:
    """d에서 months개월 뒤. 말일을 넘으면 다음 달 1일로 (full_months와 같은 기준)."""
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    try:
        return d.replace(year=year, month=month)
    except ValueError:
        nxt_y, nxt_m = (year + 1, 1) if month == 12 else (year, month + 1)
        return date(nxt_y, nxt_m, 1)


def _candidate_dates(ast, profile: Profile, as_of: date, horizon: date) -> tuple[list, list]:
    """(자격 발생 후보, 자격 상실 후보) 날짜 목록."""
    gain, loss = set(), set()
    for pred in iter_predicates(ast):
        match pred:
            case Age(lo, hi):
                if lo is not None:
                    gain.add(birthday(profile.birth_date, lo))
                if hi is not None:
                    loss.add(birthday(profile.birth_date, hi + 1))
            case Residence(comp, months):
                need = months + 1 if comp == Comp.GT else months
                gain.add(add_months(profile.residence_since, need))
    keep = lambda ds: sorted(d for d in ds if as_of < d <= horizon)  # noqa: E731
    return keep(gain), keep(loss)


def timeline(
    profile: Profile,
    policies: Iterable[Policy],
    as_of: date,
    horizon_days: int = 365 * 3,
    deadline_days: int = 60,
    table: MedianIncomeTable | None = None,
) -> list[TimelineEvent]:
    """앞으로 판정이 바뀌는 날과 마감일을 날짜순으로 돌려준다."""
    table = table or load_table()
    horizon = as_of + timedelta(days=horizon_days)
    events: list[TimelineEvent] = []

    def verdict_on(ast, on: date) -> Verdict:
        return evaluate_node(ast, Context(profile, on, table)).verdict

    for policy in policies:
        if policy.apply_end and policy.apply_end < as_of:
            continue  # 이미 마감된 정책은 자격이 생기거나 사라져도 의미가 없다
        try:
            ast = parse(policy.condition_dsl) if policy.condition_dsl else None
        except DSLError:
            ast = None
        now = verdict_on(ast, as_of) if ast else UNKNOWN

        if ast is not None:
            gain_dates, loss_dates = _candidate_dates(ast, profile, as_of, horizon)
            # 지금 불충족 → 언제부터 불충족이 아니게 되는가
            if now == FAIL:
                for d in gain_dates:
                    v = verdict_on(ast, d)
                    if v != FAIL:
                        events.append(_event(d, "자격 발생", policy, f"이날부터 {v.value}"))
                        break
            # 지금 충족/확인필요 → 언제 불충족이 되는가 (나이 상한)
            else:
                for d in loss_dates:
                    if verdict_on(ast, d) == FAIL:
                        last = d - timedelta(days=1)
                        events.append(
                            _event(d, "자격 상실", policy, f"{last}까지만 대상 (연령 상한)")
                        )
                        break

        # 신청 가능하고 대상일 수 있는 정책의 마감 임박
        end = policy.apply_end
        if end and now != FAIL and is_open(policy, as_of) and (end - as_of).days <= deadline_days:
            events.append(_event(end, "신청 마감", policy, f"D-{(end - as_of).days}"))

    events.sort(key=lambda e: (e.on, e.kind))
    return events


def _event(on: date, kind: str, policy: Policy, detail: str) -> TimelineEvent:
    return TimelineEvent(
        on=on,
        kind=kind,
        policy_id=policy.policy_id,
        policy_name=policy.name,
        amount_krw=policy.amount_krw,
        detail=detail,
    )
