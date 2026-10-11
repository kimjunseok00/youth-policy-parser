"""저장소에 들어 있는 실제 데이터 검사 + 페르소나 회귀 테스트.

- 정책 파일: 스키마·DSL·혜택 이름·중복수혜 참조가 모두 유효해야 한다.
- 페르소나: 화면의 '예시 인물'이 Profile 스키마와 맞아야 한다.
- 회귀: 문법·평가기·데이터를 고쳤을 때 판정이 '의도치 않게' 바뀌면 여기서 걸린다.
  판정이 바뀌는 게 맞다면 원문을 다시 확인한 뒤 persona_expected.json을 갱신한다.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from engine.benefits import BENEFIT_NAMES
from engine.evaluator import evaluate, load_policies
from engine.nodes import Receiving, iter_predicates
from engine.parser import parse
from engine.schemas import Profile

ROOT = Path(__file__).resolve().parent.parent
POLICIES = load_policies()
PERSONAS = json.loads((ROOT / "data" / "personas.json").read_text("utf-8"))
SNAPSHOT = json.loads((ROOT / "tests" / "regression" / "persona_expected.json").read_text("utf-8"))


def test_policies_exist():
    assert len(POLICIES) >= 9


@pytest.mark.parametrize("p", POLICIES, ids=[p.policy_id for p in POLICIES])
def test_policy_is_complete(p):
    assert p.condition_dsl, "판정하려면 DSL이 있어야 한다"
    ast = parse(p.condition_dsl)
    for n in iter_predicates(ast):
        if isinstance(n, Receiving):
            assert n.benefit in BENEFIT_NAMES
    assert p.source_url.startswith("https://")
    ids = {q.policy_id for q in POLICIES}
    assert set(p.exclusive_with) <= ids


def test_personas_match_schema():
    assert len(PERSONAS) == 5
    for per in PERSONAS:
        Profile.model_validate(per["profile"])
        assert set(per["profile"]["current_benefits"]) <= set(BENEFIT_NAMES)


@pytest.mark.parametrize("per", PERSONAS, ids=[p["label"] for p in PERSONAS])
def test_persona_regression(per):
    result = evaluate(
        Profile.model_validate(per["profile"]), POLICIES, date.fromisoformat(SNAPSHOT["as_of"])
    )
    got = {r.policy_id: r.verdict.value for r in result.results}
    assert got == SNAPSHOT["expected"][per["label"]]
