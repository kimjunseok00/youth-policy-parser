"""지자체(B2G) 리포트: "청년이 어떤 조건 때문에 정책을 못 받는가".

세 가지를 계산한다.
1. 정책별 판정 분포 (충족 / 확인 필요 / 불충족 비율)
2. 정책별 탈락 원인 순위 (어떤 조건에서 가장 많이 떨어지는가)
3. 조건 완화 시뮬레이터 ("연령 상한을 39세로 올리면 몇 명이 새로 대상이 되고 예산이 얼마 드는가")

입력 인구는 두 종류다.
- 가상 인구: 아래 가정으로 만든 시연용 프로필.
  실제 분포가 아니므로 화면에 반드시 '가상'이라고 표시한다.
- 익명 통계: 동의한 실제 사용자의 익명 요약 (app/telemetry.py).
  개인 프로필이 아니라 집계용 요약만 있다.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date

from engine.evaluator import OR_LABEL, evaluate
from engine.income import MedianIncomeTable, load_table
from engine.nodes import Age, And, IncomePct, Node, Not, Or, iter_predicates
from engine.parser import parse
from engine.regions import BUSAN_SIGUNGU
from engine.schemas import EvaluationResult, Policy, Profile, ReasonNode, Verdict

PASS, FAIL, UNKNOWN = Verdict.PASS, Verdict.FAIL, Verdict.UNKNOWN

# ---------------------------------------------------------------------------
# 가상 인구 가정 (시연용. 실측 통계가 아니다)
# ---------------------------------------------------------------------------
SYNTHETIC_ASSUMPTIONS = {
    "지역": "부산광역시 16개 구·군 균등",
    "나이": "만 19~39세 균등",
    "취업상태": "재직 50% · 구직중 20% · 미취업 15% · 프리랜서 10% · 자영업 5%",
    "학력": "대학졸업 45% · 고졸 20% · 대학재학 20% · 대학휴학·졸업예정·대학원 각 5%",
    "가구원 수": "1인 35% · 2인 25% · 3인 25% · 4인 15%",
    "가구소득": "기준중위소득의 30~200% 사이 (100% 근처가 가장 많음)",
    "군 복무": "40%가 18~21개월",
}

EMPLOYMENT_W = [("재직", 50), ("구직중", 20), ("미취업", 15), ("프리랜서", 10), ("자영업", 5)]
EDUCATION_W = [
    ("대학졸업", 45),
    ("고졸", 20),
    ("대학재학", 20),
    ("대학휴학", 5),
    ("졸업예정", 5),
    ("대학원", 5),
]
HOUSEHOLD_W = [(1, 35), (2, 25), (3, 25), (4, 15)]


def _pick(rng: random.Random, weighted: Sequence[tuple]) -> object:
    values, weights = zip(*weighted, strict=True)
    return rng.choices(values, weights=weights)[0]


def synthetic_population(
    n: int = 500,
    as_of: date | None = None,
    seed: int = 2026,
    table: MedianIncomeTable | None = None,
) -> list[Profile]:
    """시연용 가상 청년 n명. seed가 같으면 항상 같은 인구가 나온다 (발표 재현성)."""
    as_of = as_of or date(2026, 10, 1)
    table = table or load_table()
    rng = random.Random(seed)
    people = []
    for _ in range(n):
        age_days = rng.randint(19 * 365 + 5, 39 * 365 + 360)
        birth = date.fromordinal(as_of.toordinal() - age_days)
        employment = _pick(rng, EMPLOYMENT_W)
        size = _pick(rng, HOUSEHOLD_W)
        pct = min(max(rng.triangular(30, 200, 100), 30), 200)
        household = int(table.monthly(size) * pct / 100)
        if employment in ("미취업", "구직중"):
            personal = 0
        else:
            personal = min(household, int(rng.uniform(1_500_000, 4_000_000)))
        if size == 1:
            household = max(household, personal)
        months_here = rng.randint(1, 120)
        residence = max(birth, date.fromordinal(as_of.toordinal() - months_here * 30))
        people.append(
            Profile(
                birth_date=birth,
                sido="부산광역시",
                sigungu=rng.choice(BUSAN_SIGUNGU),
                residence_since=residence,
                education=_pick(rng, EDUCATION_W),
                employment=employment,
                personal_income_monthly=personal,
                household_size=size,
                household_income_monthly=household,
                military_months=rng.randint(18, 21) if rng.random() < 0.4 else 0,
            )
        )
    return people


# ---------------------------------------------------------------------------
# 집계
# ---------------------------------------------------------------------------
@dataclass
class PolicyStats:
    policy_id: str
    policy_name: str
    amount_krw: int | None
    n: int
    passed: int
    unknown: int
    failed: int
    fail_reasons: Counter  # 탈락 조건 라벨 → 인원
    pass_by_sigungu: dict[str, tuple[int, int]]  # 구·군 → (충족, 전체)

    def rate(self, k: int) -> float:
        return k / self.n if self.n else 0.0


def _fail_leaves(node: ReasonNode) -> list[ReasonNode]:
    """불충족을 만든 말단 조건들 (사유 트리에서)."""
    if not node.children:
        return [node] if node.verdict == FAIL else []
    # OR가 불충족이면 모든 자식이 원인, AND면 불충족인 자식만 원인
    kids = node.children
    if node.label == OR_LABEL:
        return [x for k in kids for x in _fail_leaves(k)]
    return [x for k in kids if k.verdict == FAIL for x in _fail_leaves(k)]


def aggregate(
    people: Sequence[Profile], results: Sequence[EvaluationResult], policies: Iterable[Policy]
) -> list[PolicyStats]:
    """프로필별 판정 결과를 정책별 통계로 묶는다."""
    stats = {
        p.policy_id: PolicyStats(p.policy_id, p.name, p.amount_krw, 0, 0, 0, 0, Counter(), {})
        for p in policies
    }
    by_area: dict[str, dict[str, list[int]]] = {pid: {} for pid in stats}
    for person, result in zip(people, results, strict=True):
        for r in result.results:
            s = stats[r.policy_id]
            s.n += 1
            area = by_area[r.policy_id].setdefault(person.sigungu, [0, 0])
            area[1] += 1
            if r.verdict == PASS:
                s.passed += 1
                area[0] += 1
            elif r.verdict == UNKNOWN:
                s.unknown += 1
            else:
                s.failed += 1
                for leaf in _fail_leaves(r.reason):
                    s.fail_reasons[leaf.label] += 1
    for pid, s in stats.items():
        s.pass_by_sigungu = {k: (v[0], v[1]) for k, v in sorted(by_area[pid].items())}
    return sorted(stats.values(), key=lambda s: -s.failed)


def evaluate_population(
    people: Sequence[Profile], policies: Sequence[Policy], as_of: date
) -> list[EvaluationResult]:
    table = load_table()
    return [evaluate(p, policies, as_of, table) for p in people]


# ---------------------------------------------------------------------------
# 조건 완화 시뮬레이터
# ---------------------------------------------------------------------------
def relax(node: Node, age_max_delta: int = 0, income_pct_delta: int = 0) -> Node:
    """조건식의 숫자 기준만 바꾼 새 조건식. (연령 상한 +N세, 소득 기준 +N%p)"""
    match node:
        case And(children):
            return And(tuple(relax(c, age_max_delta, income_pct_delta) for c in children))
        case Or(children):
            return Or(tuple(relax(c, age_max_delta, income_pct_delta) for c in children))
        case Not(child):
            return Not(relax(child, age_max_delta, income_pct_delta))
        case Age(lo, hi, mil) if hi is not None:
            return Age(lo, hi + age_max_delta, mil)
        case IncomePct() if node.comp.value in ("<=", "<"):
            return replace(node, pct=node.pct + income_pct_delta)
    return node


@dataclass
class Simulation:
    policy_name: str
    before_pass: int
    after_pass: int
    before_possible: int  # 충족 + 확인 필요
    after_possible: int
    n: int
    new_dsl: str

    @property
    def added(self) -> int:
        return self.after_pass - self.before_pass


def simulate(
    policy: Policy,
    people: Sequence[Profile],
    as_of: date,
    age_max_delta: int = 0,
    income_pct_delta: int = 0,
) -> Simulation:
    """기준을 완화했을 때 새로 대상이 되는 인원. 예산 추정은 added × 1인당 금액."""
    table = load_table()
    relaxed = policy.model_copy(
        update={
            "condition_dsl": relax(
                parse(policy.condition_dsl or ""), age_max_delta, income_pct_delta
            ).to_dsl()
        }
    )

    def count(p: Policy) -> tuple[int, int]:
        rs = [evaluate(x, [p], as_of, table).results[0] for x in people]
        return sum(r.verdict == PASS for r in rs), sum(r.verdict != FAIL for r in rs)

    b_pass, b_pos = count(policy)
    a_pass, a_pos = count(relaxed)
    return Simulation(
        policy.name, b_pass, a_pass, b_pos, a_pos, len(people), relaxed.condition_dsl or ""
    )


def adjustable(policy: Policy) -> tuple[bool, bool]:
    """(연령 상한이 있는가, 소득 % 상한이 있는가) → 시뮬레이터에서 조절할 수 있는 항목."""
    preds = list(iter_predicates(parse(policy.condition_dsl or "")))
    has_age = any(isinstance(p, Age) and p.max_age is not None for p in preds)
    has_income = any(isinstance(p, IncomePct) and p.comp.value in ("<=", "<") for p in preds)
    return has_age, has_income


def aggregate_rows(rows: Sequence[dict], policies: Iterable[Policy]) -> list[PolicyStats]:
    """익명 통계(anonymize() 결과 목록)를 정책별 통계로 묶는다. 실사용 데이터용."""
    stats = {
        p.policy_id: PolicyStats(p.policy_id, p.name, p.amount_krw, 0, 0, 0, 0, Counter(), {})
        for p in policies
    }
    areas: dict[str, dict[str, list[int]]] = {pid: {} for pid in stats}
    for row in rows:
        for pid, verdict in row.get("verdicts", {}).items():
            if pid not in stats:  # 그사이 삭제된 정책
                continue
            s = stats[pid]
            s.n += 1
            area = areas[pid].setdefault(row.get("area", "알 수 없음"), [0, 0])
            area[1] += 1
            if verdict == PASS.value:
                s.passed += 1
                area[0] += 1
            elif verdict == UNKNOWN.value:
                s.unknown += 1
            else:
                s.failed += 1
                s.fail_reasons.update(row.get("fail_reasons", {}).get(pid, []))
    for pid, s in stats.items():
        s.pass_by_sigungu = {k: (v[0], v[1]) for k, v in sorted(areas[pid].items())}
    return sorted(stats.values(), key=lambda s: -s.failed)
