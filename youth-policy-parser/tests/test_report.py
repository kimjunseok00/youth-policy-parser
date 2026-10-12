"""지자체 리포트 · 익명화 · 통계 저장 테스트."""

import json
import urllib.error
from datetime import date

from app.telemetry import TelemetryConfig, fetch_rows, load_config, record
from engine.anonymize import MIN_GROUP, age_band, anonymize, income_band
from engine.evaluator import evaluate, load_policies
from engine.nodes import Age, IncomePct
from engine.parser import parse
from engine.report import (
    adjustable,
    aggregate,
    aggregate_rows,
    evaluate_population,
    relax,
    simulate,
    synthetic_population,
)
from engine.schemas import Policy, Profile

AS_OF = date(2026, 10, 12)
POLICIES = load_policies()


def test_synthetic_population_is_reproducible_and_valid():
    a = synthetic_population(50, AS_OF, seed=1)
    b = synthetic_population(50, AS_OF, seed=1)
    assert a == b
    assert all(p.personal_income_monthly <= p.household_income_monthly for p in a)
    assert all(19 <= (AS_OF - p.birth_date).days // 365 <= 40 for p in a)


def test_aggregate_counts_add_up():
    people = synthetic_population(80, AS_OF)
    stats = aggregate(people, evaluate_population(people, POLICIES, AS_OF), POLICIES)
    for s in stats:
        assert s.passed + s.unknown + s.failed == s.n == 80
        assert sum(total for _, total in s.pass_by_sigungu.values()) == 80
        if s.failed:
            assert s.fail_reasons, "불충족이 있으면 원인도 있어야 한다"


def test_relax_changes_only_thresholds():
    node = parse('age(19..34, military=72) AND income_pct(household) <= 60 AND manual("x")')
    relaxed = relax(node, age_max_delta=5, income_pct_delta=40)
    assert relaxed.children[0] == Age(19, 39, 72)
    assert relaxed.children[1].pct == 100 and isinstance(relaxed.children[1], IncomePct)
    assert relaxed.children[2] == node.children[2]


def test_simulation_never_reduces_eligibility():
    policy = next(p for p in POLICIES if p.policy_id == "busan-youth-rent-support")
    people = synthetic_population(120, AS_OF)
    sim = simulate(policy, people, AS_OF, age_max_delta=5, income_pct_delta=20)
    assert sim.after_possible >= sim.before_possible
    assert sim.after_pass >= sim.before_pass
    assert "age(19..39)" in sim.new_dsl


def test_adjustable_flags():
    pol = Policy(
        policy_id="x",
        name="x",
        agency="-",
        region="-",
        amount_text="-",
        source_url="https://e.com",
        eligibility_text="-",
        condition_dsl='region("부산광역시")',
    )
    assert adjustable(pol) == (False, False)


# ---------------------------------------------------------------------------
# 익명화
# ---------------------------------------------------------------------------
def test_bands():
    assert age_band(19) == "19~24세" and age_band(25) == "25~29세" and age_band(41) == "40세 이상"
    assert income_band(84.0) == "80~100%" and income_band(250) == "200% 이상"
    assert MIN_GROUP >= 5


def test_anonymize_drops_identifying_values():
    p = Profile(
        birth_date="2001-03-15",
        sido="서울특별시",
        sigungu="마포구",
        residence_since="2023-02-01",
        education="대학졸업",
        employment="구직중",
        personal_income_monthly=0,
        household_size=7,
        household_income_monthly=4_512_345,
        current_benefits=["국민취업지원제도"],
    )
    row = anonymize(p, evaluate(p, POLICIES, AS_OF))
    blob = json.dumps(row, ensure_ascii=False)
    for secret in ("2001-03-15", "2023-02-01", "4512345", "마포구", '국민취업지원제도"'):
        assert secret not in blob
    assert row["area"] == "부산 외" and row["household"] == "5인 이상"
    assert row["month"] == "2026-10"


def test_aggregate_rows_matches_aggregate():
    people = synthetic_population(30, AS_OF)
    results = evaluate_population(people, POLICIES, AS_OF)
    direct = {
        s.policy_id: (s.passed, s.unknown, s.failed) for s in aggregate(people, results, POLICIES)
    }
    rows = [anonymize(p, r) for p, r in zip(people, results, strict=True)]
    via_rows = {
        s.policy_id: (s.passed, s.unknown, s.failed) for s in aggregate_rows(rows, POLICIES)
    }
    assert direct == via_rows


# ---------------------------------------------------------------------------
# 저장소 연동 (네트워크 없이 요청 내용만 검사)
# ---------------------------------------------------------------------------
CFG = TelemetryConfig("https://abc.supabase.co/", "sb_publishable_x", "sb_secret_y")


def test_record_disabled_without_config():
    assert record(None, {"a": 1}) is False
    assert load_config({}) is None


def test_record_sends_apikey_header_and_payload():
    sent = {}

    def fake(req):
        sent["url"], sent["headers"], sent["body"] = (
            req.full_url,
            dict(req.header_items()),
            req.data,
        )
        return b""

    assert record(CFG, {"age_band": "25~29세"}, send=fake) is True
    assert sent["url"] == "https://abc.supabase.co/rest/v1/events"
    assert sent["headers"]["Apikey"] == "sb_publishable_x"
    assert "Authorization" not in sent["headers"]
    assert json.loads(sent["body"]) == {"payload": {"age_band": "25~29세"}}


def test_record_failure_does_not_raise():
    def boom(req):
        raise urllib.error.URLError("down")

    assert record(CFG, {}, send=boom) is False


def test_fetch_rows_uses_read_key():
    seen = {}

    def fake(req):
        seen["key"] = dict(req.header_items())["Apikey"]
        return json.dumps([{"payload": {"v": 1}}]).encode()

    assert fetch_rows(CFG, send=fake) == [{"v": 1}]
    assert seen["key"] == "sb_secret_y"
    assert fetch_rows(TelemetryConfig("https://a", "k", None)) == []


# ---------------------------------------------------------------------------
# 사유 트리 그림 (DOT)
# ---------------------------------------------------------------------------
def test_reason_to_dot_structure():
    from app.viz import reason_to_dot
    from engine.schemas import ReasonNode, Verdict

    tree = ReasonNode(
        label="요약",
        verdict=Verdict.FAIL,
        children=[
            ReasonNode(label="만 19~34세", verdict=Verdict.PASS, detail="만 25세"),
            ReasonNode(label='따옴표 "포함" 조건', verdict=Verdict.FAIL, detail="x"),
        ],
    )
    dot = reason_to_dot(tree, "청년 월세 지원")
    assert dot.startswith("digraph G {") and dot.rstrip().endswith("}")
    assert dot.count("->") == 2
    assert '\\"포함\\"' in dot  # 따옴표가 DOT 문법을 깨지 않게 이스케이프
    assert "청년 월세 지원" in dot
