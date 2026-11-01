"""engine/service.py: 웹(Streamlit)과 앱(PWA)이 같이 쓰는 입구.

앱은 브라우저 안의 Python(Pyodide)에서 judge_json()을 부른다. 여기서는 일반 Python으로
같은 함수를 검사한다. (Pyodide에서 결과가 같다는 것은 docs/app.md의 수동 점검 절차로 확인)
"""

import json
import zipfile
from datetime import date

from engine import service
from engine.evaluator import evaluate
from engine.schemas import Profile

AS_OF = "2026-10-10"


def test_meta_has_everything_the_app_draws():
    meta = json.loads(service.meta_json())
    assert {"as_of", "options", "personas", "policies", "median_income"} <= meta.keys()
    assert "부산광역시" in meta["options"]["sido"]
    assert len(meta["personas"]) == len(service.personas())
    assert meta["median_income"]["monthly"]["1"] == 2_564_238  # 2026년 1인 가구


def test_judge_json_matches_engine_for_every_persona():
    for per in service.personas():
        out = json.loads(
            service.judge_json(json.dumps({"profile": per["profile"], "as_of": AS_OF}))
        )
        expected = evaluate(
            Profile.model_validate(per["profile"]), service.policies(), date.fromisoformat(AS_OF)
        )
        got = {r["policy_id"]: r["verdict"] for r in out["result"]["results"]}
        assert got == {r.policy_id: r.verdict.value for r in expected.results}
        assert {"questions", "suggestions", "near_misses", "timeline", "plan"} <= out.keys()


def test_judge_json_answers_resolve_questions():
    per = service.personas()[0]["profile"]
    first = json.loads(service.judge_json(json.dumps({"profile": per, "as_of": AS_OF})))
    q = first["questions"][0]["text"]
    again = json.loads(
        service.judge_json(json.dumps({"profile": per, "answers": {q: True}, "as_of": AS_OF}))
    )
    assert q not in [x["text"] for x in again["questions"]]


def test_judge_json_returns_readable_error_instead_of_raising():
    bad = dict(service.personas()[0]["profile"], personal_income_monthly=9_000_000_000)
    out = json.loads(service.judge_json(json.dumps({"profile": bad})))
    assert out["error"].startswith("본인 월소득이 가구 월소득보다")
    assert "Traceback" not in out["error"]


def test_engine_zip_contains_engine_data_and_lark(tmp_path):
    """앱에 실을 엔진 묶음: Pyodide 없이도 만들 수 있는 부분만 검사 (CI에서 330MB를 받지 않게)."""
    from scripts.build_app import build_engine_zip

    build_engine_zip(tmp_path)
    names = set(zipfile.ZipFile(tmp_path / "engine.zip").namelist())
    assert {"engine/service.py", "engine/grammar.lark", "data/personas.json"} <= names
    assert any(n.startswith("data/policies/") for n in names)
    assert "lark/__init__.py" in names
    assert not any("streamlit" in n for n in names)  # 앱에는 Streamlit이 필요 없다
