"""앱 레이어 공개 인터페이스.

화면(streamlit_app.py, app/page_*.py)은 이 모듈의 함수만 호출한다. 판정 로직은 전부 engine/에 있다.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

from engine.benefits import BENEFIT_NAMES
from engine.counterfactual import NearMiss, Suggestion, near_misses, suggestions
from engine.evaluator import evaluate, is_notice, load_policies, today_kst
from engine.optimizer import OptimalPlan, optimize
from engine.regions import BUSAN_SIGUNGU, SIDO
from engine.schemas import EvaluationResult, Policy, Profile, ReasonNode, Verdict
from engine.timeline import TimelineEvent, timeline

ROOT = Path(__file__).resolve().parent.parent
PERSONAS_PATH = ROOT / "data" / "personas.json"

__all__ = [
    "BENEFIT_NAMES",
    "BUSAN_SIGUNGU",
    "SIDO",
    "Insights",
    "as_of",
    "get_insights",
    "get_results",
    "manual_questions",
    "personas",
    "policies",
]


def as_of() -> date:
    """판정 기준일 = 오늘(한국 기준). 테스트·데모에서 바꾸려면 이 함수만 고치면 된다."""
    return today_kst()


@cache
def policies() -> tuple[Policy, ...]:
    """data/policies/*.json. 서버가 떠 있는 동안 한 번만 읽는다."""
    return tuple(load_policies())


@cache
def personas() -> tuple[dict, ...]:
    """예시 인물 (data/personas.json). 각 항목: label, scenario, profile."""
    return tuple(json.loads(PERSONAS_PATH.read_text(encoding="utf-8")))


def get_results(profile: Profile, answers: Mapping[str, bool] | None = None) -> EvaluationResult:
    """프로필(+확인 질문 답변)을 받아 전체 정책 판정 결과를 반환한다."""
    return evaluate(profile, policies(), as_of(), answers=answers)


@dataclass(frozen=True)
class Insights:
    """판정 결과 위에 얹는 차별 기능 묶음."""

    suggestions: list[Suggestion]  # 이것만 바꾸면 (행동 제안)
    near_misses: list[NearMiss]  # 조건 하나만 어긋난 정책
    timeline: list[TimelineEvent]  # 자격 발생·상실·마감 일정
    plan: OptimalPlan  # 충족 정책만으로 만든 최적 조합
    plan_with_unknown: OptimalPlan  # 확인 필요까지 포함한 최적 조합


def get_insights(
    profile: Profile, result: EvaluationResult, answers: Mapping[str, bool] | None = None
) -> Insights:
    pols, today = list(policies()), as_of()
    return Insights(
        suggestions=suggestions(profile, pols, today, answers=answers),
        near_misses=near_misses(profile, pols, today, answers=answers),
        timeline=timeline(profile, pols, today, answers=answers),
        plan=optimize(result, pols, include_unknown=False),
        plan_with_unknown=optimize(result, pols, include_unknown=True),
    )


def _unknown_manual_leaves(node: ReasonNode) -> list[str]:
    if not node.children:
        text = node.source_quote or node.label
        askable = (
            node.category == "기타" and node.verdict == Verdict.UNKNOWN and not is_notice(text)
        )
        return [text] if askable else []
    return [q for c in node.children for q in _unknown_manual_leaves(c)]


def manual_questions(result: EvaluationResult) -> list[tuple[str, list[str]]]:
    """'확인 필요' 정책을 확정하려면 답해야 하는 질문 목록.

    반환: [(질문 원문, [이 질문에 걸린 정책 이름들])], 걸린 정책이 많은 질문부터.
    묻지 않는 경우: 불충족이 이미 확정된 정책(답해도 안 바뀜), 신청 기간이 지난 정책,
    '※' 안내문(예: '세부 자격은 공고문 확인' — 예/아니오로 답할 조건이 아님).
    """
    asked: dict[str, list[str]] = {}
    for r in result.results:
        if r.verdict != Verdict.UNKNOWN or not r.is_open:
            continue
        for q in dict.fromkeys(_unknown_manual_leaves(r.reason)):
            asked.setdefault(q, []).append(r.policy_name)
    return sorted(asked.items(), key=lambda kv: -len(kv[1]))
