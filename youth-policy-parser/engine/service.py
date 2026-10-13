"""엔진 서비스 계층: 화면(웹·앱)이 부르는 '판정 한 번'의 입구.

두 화면이 같은 함수를 쓴다.
- 지자체용 웹(Streamlit): app/__init__.py가 이 모듈의 함수를 그대로 다시 내보낸다.
- 청년용 앱(PWA): 브라우저 안의 Python(Pyodide)이 judge_json()/meta_json()을 호출한다.
  문자열(JSON)만 주고받으므로 자바스크립트 쪽에서 Python 객체를 다룰 필요가 없다.

이 모듈은 Streamlit을 import하지 않는다 (브라우저에서도 돌아야 하므로).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

from engine.benefits import BENEFIT_NAMES
from engine.counterfactual import NearMiss, Suggestion, near_misses, suggestions
from engine.evaluator import evaluate, is_notice, load_policies, today_kst
from engine.income import load_table
from engine.optimizer import OptimalPlan, optimize
from engine.regions import BUSAN_SIGUNGU, SIDO
from engine.schemas import (
    Education,
    Employment,
    EvaluationResult,
    Policy,
    Profile,
    ReasonNode,
    Verdict,
)
from engine.timeline import TimelineEvent, timeline

ROOT = Path(__file__).resolve().parent.parent
PERSONAS_PATH = ROOT / "data" / "personas.json"


@cache
def policies() -> tuple[Policy, ...]:
    """data/policies/*.json. 프로그램이 떠 있는 동안 한 번만 읽는다."""
    return tuple(load_policies())


@cache
def personas() -> tuple[dict, ...]:
    """예시 인물 (data/personas.json). 각 항목: label, scenario, profile."""
    return tuple(json.loads(PERSONAS_PATH.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# 차별 기능 묶음
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Insights:
    """판정 결과 위에 얹는 차별 기능 묶음."""

    suggestions: list[Suggestion]  # 이것만 바꾸면 (행동 제안)
    near_misses: list[NearMiss]  # 조건 하나만 어긋난 정책
    timeline: list[TimelineEvent]  # 자격 발생·상실·마감 일정
    plan: OptimalPlan  # 충족 정책만으로 만든 최적 조합
    plan_with_unknown: OptimalPlan  # 확인 필요까지 포함한 최적 조합


def insights(
    profile: Profile,
    result: EvaluationResult,
    pols: Iterable[Policy],
    as_of: date,
    answers: Mapping[str, bool] | None = None,
) -> Insights:
    pols = list(pols)
    return Insights(
        suggestions=suggestions(profile, pols, as_of, answers=answers),
        near_misses=near_misses(profile, pols, as_of, answers=answers),
        timeline=timeline(profile, pols, as_of, answers=answers),
        plan=optimize(result, pols, include_unknown=False),
        plan_with_unknown=optimize(result, pols, include_unknown=True),
    )


# ---------------------------------------------------------------------------
# 확인 질문
# ---------------------------------------------------------------------------
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
    '※' 안내문(조건이 아니라 참고 문구).
    """
    asked: dict[str, list[str]] = {}
    for r in result.results:
        if r.verdict != Verdict.UNKNOWN or not r.is_open:
            continue
        for q in dict.fromkeys(_unknown_manual_leaves(r.reason)):
            asked.setdefault(q, []).append(r.policy_name)
    return sorted(asked.items(), key=lambda kv: -len(kv[1]))


# ---------------------------------------------------------------------------
# 앱(PWA)용 JSON 입구
# ---------------------------------------------------------------------------
def meta_json() -> str:
    """앱이 처음 켜질 때 한 번 받는 정보: 선택지, 예시 인물, 정책 목록."""
    day = today_kst()
    return json.dumps(
        {
            "as_of": day.isoformat(),
            "options": {
                "sido": list(SIDO),
                "busan_sigungu": list(BUSAN_SIGUNGU),
                "education": [e.value for e in Education],
                "employment": [e.value for e in Employment],
                "benefits": list(BENEFIT_NAMES),
            },
            "personas": list(personas()),
            # 소득 입력란 옆에 '기준중위소득 몇 %'를 바로 보여주기 위한 표 (가구원 수 1~8명)
            "median_income": {
                "year": (table := load_table()).year,
                "monthly": {str(n): table.monthly(n) for n in range(1, 9)},
            },
            "policies": [
                {
                    "policy_id": p.policy_id,
                    "name": p.name,
                    "agency": p.agency,
                    "amount_krw": p.amount_krw,
                    "source_url": p.source_url,
                    "is_open": not p.apply_end or p.apply_end >= day,
                }
                for p in policies()
            ],
        },
        ensure_ascii=False,
    )


def judge(
    profile: Profile, answers: Mapping[str, bool] | None = None, as_of: date | None = None
) -> dict:
    """판정 + 확인 질문 + 차별 기능을 한 번에 계산해 JSON으로 바꿀 수 있는 dict로 반환."""
    day = as_of or today_kst()
    pols = policies()
    result = evaluate(profile, pols, day, answers=answers)
    ins = insights(profile, result, pols, day, answers)
    return {
        "as_of": day.isoformat(),
        "result": result.model_dump(mode="json"),
        "questions": [{"text": q, "policies": names} for q, names in manual_questions(result)],
        "suggestions": [s.model_dump(mode="json") for s in ins.suggestions],
        "near_misses": [m.model_dump(mode="json") for m in ins.near_misses],
        "timeline": [e.model_dump(mode="json") for e in ins.timeline],
        "plan": ins.plan.model_dump(mode="json"),
        "plan_with_unknown": ins.plan_with_unknown.model_dump(mode="json"),
    }


def judge_json(payload: str) -> str:
    """앱 → 엔진. 입력: {"profile": {...}, "answers": {...}, "as_of": "YYYY-MM-DD"(선택)}.

    입력이 잘못되면 예외 대신 {"error": "사람이 읽을 수 있는 메시지"}를 돌려준다.
    (브라우저 쪽에서 Python 예외를 그대로 보여주지 않기 위해)
    """
    try:
        data = json.loads(payload)
        profile = Profile.model_validate(data["profile"])
        answers = {str(k): bool(v) for k, v in (data.get("answers") or {}).items()}
        as_of = date.fromisoformat(data["as_of"]) if data.get("as_of") else None
    except Exception as e:  # 입력 검증 실패 → 화면에 그대로 보여줄 문장만 추린다
        msg = str(e).split("Value error, ")[-1].split("[type=")[0].strip()
        return json.dumps({"error": msg}, ensure_ascii=False)
    return json.dumps(judge(profile, answers, as_of), ensure_ascii=False)
