"""최적 조합: 중복수혜 제약을 지키면서 받을 수 있는 금액이 가장 큰 정책 묶음.

정수계획법(0-1 배낭 + 충돌 제약)
    최대화   Σ 금액_i · x_i
    제약     x_i + x_j ≤ 1   (i, j가 중복수혜 불가인 모든 쌍)
             x_i ∈ {0, 1}

정책 수가 적으면(≤ 20) 전수 탐색으로도 정확한 답이 나오므로,
PuLP(솔버)를 쓸 수 없는 환경에서는 자동으로 전수 탐색으로 바꾼다. 두 방법의 답은 같다.
"""

from __future__ import annotations

from itertools import combinations

from pydantic import BaseModel

from engine.schemas import EvaluationResult, Policy, PolicyResult, Verdict

BRUTE_FORCE_LIMIT = 20


class Excluded(BaseModel):
    policy_name: str
    amount_krw: int
    because_of: str  # 이 정책 대신 고른 정책 이름


class OptimalPlan(BaseModel):
    selected: list[PolicyResult]
    excluded: list[Excluded]  # 조건은 되지만 중복수혜 때문에 빠진 정책
    total_krw: int
    simple_sum_krw: int  # 중복수혜를 무시한 단순 합계 (비교용)
    method: str  # "PuLP" | "전수 탐색" | "충돌 없음"


def conflict_pairs(policies: list[Policy]) -> set[frozenset[str]]:
    """exclusive_with를 양방향 쌍으로 만든다. (한쪽에만 적혀 있어도 충돌로 본다)"""
    pairs = set()
    for p in policies:
        for other in p.exclusive_with:
            if other != p.policy_id:
                pairs.add(frozenset((p.policy_id, other)))
    return pairs


def _feasible(ids: tuple[str, ...], pairs: set[frozenset[str]]) -> bool:
    return not any(frozenset(c) in pairs for c in combinations(ids, 2))


def _solve_brute(cands: list[PolicyResult], pairs) -> list[str]:
    best, best_total = (), -1
    ids = [c.policy_id for c in cands]
    amount = {c.policy_id: c.amount_krw or 0 for c in cands}
    for r in range(len(ids), 0, -1):
        for combo in combinations(ids, r):
            if _feasible(combo, pairs):
                total = sum(amount[i] for i in combo)
                if total > best_total:
                    best, best_total = combo, total
    return list(best)


def _solve_pulp(cands: list[PolicyResult], pairs) -> list[str]:
    import pulp  # 지연 import: 설치되지 않은 환경에서도 모듈 자체는 불러올 수 있게

    prob = pulp.LpProblem("policy_combo", pulp.LpMaximize)
    x = {c.policy_id: pulp.LpVariable(f"x{i}", cat="Binary") for i, c in enumerate(cands)}
    prob += pulp.lpSum((c.amount_krw or 0) * x[c.policy_id] for c in cands)
    for pair in pairs:
        a, b = tuple(pair)
        if a in x and b in x:
            prob += x[a] + x[b] <= 1
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    return [pid for pid, var in x.items() if (var.value() or 0) > 0.5]


def optimize(
    result: EvaluationResult, policies: list[Policy], include_unknown: bool = False
) -> OptimalPlan:
    """판정 결과에서 '지금 신청 가능한 충족 정책'으로 최적 조합을 만든다.

    include_unknown=True면 '확인 필요' 정책도 후보에 넣는다 (확인 후 받을 수 있는 최대치).
    """
    ok = {Verdict.PASS, Verdict.UNKNOWN} if include_unknown else {Verdict.PASS}
    cands = [r for r in result.results if r.verdict in ok and r.is_open and r.amount_krw]
    pairs = {
        p for p in conflict_pairs(policies) if p <= {c.policy_id for c in cands}
    }  # 후보끼리의 충돌만 의미가 있다

    if not pairs:
        chosen, method = [c.policy_id for c in cands], "충돌 없음"
    else:
        try:
            chosen, method = _solve_pulp(cands, pairs), "PuLP"
        except Exception:  # 솔버가 없거나 실행 실패 → 정확한 전수 탐색으로 대체
            if len(cands) > BRUTE_FORCE_LIMIT:
                raise
            chosen, method = _solve_brute(cands, pairs), "전수 탐색"

    by_id = {c.policy_id: c for c in cands}
    selected = sorted((by_id[i] for i in chosen), key=lambda r: -(r.amount_krw or 0))
    chosen_set = set(chosen)
    excluded = []
    for c in cands:
        if c.policy_id in chosen_set:
            continue
        rival = next(
            (
                by_id[o]
                for pair in pairs
                if c.policy_id in pair
                for o in pair - {c.policy_id}
                if o in chosen_set
            ),
            None,
        )
        if rival:
            excluded.append(
                Excluded(
                    policy_name=c.policy_name,
                    amount_krw=c.amount_krw or 0,
                    because_of=rival.policy_name,
                )
            )

    return OptimalPlan(
        selected=selected,
        excluded=excluded,
        total_krw=sum(r.amount_krw or 0 for r in selected),
        simple_sum_krw=sum(c.amount_krw or 0 for c in cands),
        method=method,
    )
