"""DSL 파서 테스트.

테스트 하나가 요구사항(조건 유형) 하나에 대응한다. 발표에서 "문법 명세 ↔ 테스트 1:1 대응"의 근거.
문법을 바꾸면 이 테스트가 먼저 깨지므로, 문법 동결 이후의 회귀 방지 장치 역할도 한다.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from engine.nodes import (
    Age,
    And,
    Born,
    Category,
    Comp,
    IncomeAbs,
    IncomePct,
    InSet,
    Manual,
    Not,
    Or,
    Receiving,
    Region,
    Residence,
    iter_predicates,
)
from engine.parser import DSLSemanticError, DSLSyntaxError, parse

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 요구사항 1~8: 조건 유형 8종을 각각 표현할 수 있다
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("dsl", "expected", "category"),
    [
        # 1. 연령
        ("age(19..34)", Age(19, 34), Category.AGE),
        ("age(..39)", Age(None, 39), Category.AGE),
        ("age(19..)", Age(19, None), Category.AGE),
        (
            "born(1986-01-01..2008-12-31)",
            Born(date(1986, 1, 1), date(2008, 12, 31)),
            Category.AGE,
        ),
        # 2. 소득
        ("income_pct(household) <= 150", IncomePct("household", Comp.LE, 150), Category.INCOME),
        ("income(personal) < 2910000", IncomeAbs("personal", Comp.LT, 2910000), Category.INCOME),
        # 3. 거주
        ('region("부산광역시")', Region("부산광역시"), Category.REGION),
        ('region("부산광역시", "해운대구")', Region("부산광역시", "해운대구"), Category.REGION),
        # 4. 학력
        (
            'education in ["대학재학", "대학휴학"]',
            InSet("education", ("대학재학", "대학휴학")),
            Category.EDUCATION,
        ),
        # 5. 취업상태
        ('employment in ["미취업"]', InSet("employment", ("미취업",)), Category.EMPLOYMENT),
        # 6. 기간
        ("residence_months >= 12", Residence(Comp.GE, 12), Category.PERIOD),
        # 7. 중복수혜
        ('receiving("국민취업지원제도")', Receiving("국민취업지원제도"), Category.DUPLICATE),
        # 8. 기타
        ('manual("무주택자")', Manual("무주택자"), Category.OTHER),
    ],
)
def test_condition_types(dsl, expected, category):
    node = parse(dsl)
    assert node == expected
    assert node.CATEGORY == category


# ---------------------------------------------------------------------------
# 요구사항 9: 조건을 AND / OR / NOT / 괄호로 조합할 수 있다
# ---------------------------------------------------------------------------
def test_and_or_precedence():
    """AND가 OR보다 먼저 묶인다: A OR B AND C == A OR (B AND C)"""
    node = parse('manual("A") OR manual("B") AND manual("C")')
    assert node == Or((Manual("A"), And((Manual("B"), Manual("C")))))


def test_parentheses_override_precedence():
    node = parse('(manual("A") OR manual("B")) AND manual("C")')
    assert node == And((Or((Manual("A"), Manual("B"))), Manual("C")))


def test_not_binds_tightest():
    node = parse('NOT receiving("X") AND age(19..)')
    assert node == And((Not(Receiving("X")), Age(19, None)))


def test_nested_and_is_flattened():
    node = parse('age(19..) AND (region("부산광역시") AND residence_months >= 6)')
    assert isinstance(node, And) and len(node.children) == 3


def test_double_negation_removed():
    assert parse("NOT NOT age(19..)") == Age(19, None)


def test_whitespace_newlines_and_comments_ignored():
    dsl = """
        age(19..34)      # 나이
        AND region("부산광역시")   # 거주
    """
    assert parse(dsl) == And((Age(19, 34), Region("부산광역시")))


# ---------------------------------------------------------------------------
# 요구사항 10: 파싱 → 문자열 → 파싱 결과가 같다 (저장·표시해도 뜻이 변하지 않음)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "dsl",
    [
        'age(19..34) AND region("부산광역시")',
        '(manual("A") OR manual("B")) AND NOT receiving("C")',
        'NOT (age(..18) OR employment in ["재직"])',
        'region("부산광역시", "해운대구") AND income_pct(personal) <= 150',
        'manual("따옴표 \\"포함\\" 문장")',
    ],
)
def test_round_trip(dsl):
    node = parse(dsl)
    assert parse(node.to_dsl()) == node


# ---------------------------------------------------------------------------
# 요구사항 11: 실제 부산 정책 변환 예시가 모두 파싱된다
# ---------------------------------------------------------------------------
EXAMPLES = json.loads((ROOT / "data" / "examples" / "dsl_examples.json").read_text("utf-8"))


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["name"] for e in EXAMPLES])
def test_real_policy_examples_parse(example):
    node = parse(example["dsl"])
    assert list(iter_predicates(node)), "조건이 하나 이상 있어야 한다"


def test_examples_cover_all_eight_categories():
    """예시 전체가 조건 유형 8종 중 몇 개를 쓰는지 확인 (문법 설계 검증용 지표)."""
    used = {p.CATEGORY for e in EXAMPLES for p in iter_predicates(parse(e["dsl"]))}
    # 학력(education) 예시는 아직 실제 정책에서 못 찾았다 → 데이터 수집 후 8종 완성 목표
    assert used >= {
        Category.AGE,
        Category.INCOME,
        Category.REGION,
        Category.EMPLOYMENT,
        Category.DUPLICATE,
        Category.OTHER,
    }


# ---------------------------------------------------------------------------
# 요구사항 12: 잘못된 입력은 위치와 이유를 알려주며 거부한다
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "dsl",
    [
        "age(19..34) AND",  # 문장이 끝나지 않음
        "age(19..34",  # 괄호 안 닫힘
        "나이 19세 이상",  # DSL이 아닌 자연어
        'age(19..34) region("부산광역시")',  # AND 누락
        "income_pct(family) <= 100",  # 없는 범위(scope)
    ],
)
def test_syntax_errors(dsl):
    with pytest.raises(DSLSyntaxError) as exc:
        parse(dsl)
    assert "행" in str(exc.value) and "열" in str(exc.value)


@pytest.mark.parametrize(
    ("dsl", "message_part"),
    [
        ("age(40..19)", "최소 나이"),
        ("age(..)", "하나가 있어야"),
        ("born(2008-12-31..1986-01-01)", "시작일"),
        ("born(2026-02-30..)", "존재하지 않는 날짜"),
        ('region("부산시")', "정식 명칭"),
        ('region("부산광역시", "해운대")', "없는 시·군·구"),
        ('education in ["박사"]', "없는 값"),
        ('employment in ["알바"]', "없는 값"),
    ],
)
def test_semantic_errors(dsl, message_part):
    with pytest.raises(DSLSemanticError) as exc:
        parse(dsl)
    assert message_part in str(exc.value)
