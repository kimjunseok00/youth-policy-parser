"""온통청년 수집기(ingest/ontong.py): 응답 구조가 달라도 정책 목록을 찾고, 초안이 검증을 통과하는지.

실제 API 응답 형식은 실제 호출(scripts/collect.py --inspect)로 확인한다. 여기서는 그 결과가
어떤 경로에 담겨 오든 처리할 수 있는지와, 자동 변환 규칙이 맞는지를 검사한다.
"""

from datetime import date

import pytest

from engine.parser import parse
from engine.schemas import Policy
from ingest.ontong import (
    clean_url,
    classify_region,
    draft,
    find_items,
    find_total,
    is_open,
    is_other_region_gov,
    parse_period,
    wanted,
    zip_codes,
)

BUSAN_ALL = ",".join(
    ["26110", "26140", "26170", "26200", "26230", "26260", "26290", "26320",
     "26350", "26380", "26410", "26440", "26470", "26500", "26530", "26710"]
)  # fmt: skip
NATION = ",".join(f"{c}110" for c in ["11", "26", "27", "28", "29", "30", "31", "36", "41", "51"])

ITEM = {
    "plcyNo": "20260301005400110001",
    "plcyNm": "부산 청년 테스트 지원",
    "sprvsnInstCdNm": "부산광역시",
    "sprtTrgtMinAge": "19",
    "sprtTrgtMaxAge": "34",
    "zipCd": "26350,26230",
    "aplyYmd": "20260301 ~ 20260331",
    "plcySprtCn": '월 30만 원 "최대" 6개월',
    "addAplyQlfcCndCn": "미취업 청년\n(고용보험 미가입)",
    "earnMaxAmt": "0",
    "refUrlAddr1": "https://young.busan.go.kr",
}


@pytest.mark.parametrize(
    "payload",
    [
        {"result": {"pagging": {"totCount": 1}, "youthPolicyList": [ITEM]}},
        {"youthPolicyList": [ITEM], "totalCount": "1"},
        [ITEM],
    ],
)
def test_find_items_wherever_the_list_is(payload):
    assert find_items(payload) == [ITEM]
    assert find_total(payload) in (1, None)


def test_region_classification():
    assert classify_region(zip_codes("26350,26230")) == ("부산광역시", ["부산진구", "해운대구"])
    assert classify_region(zip_codes(BUSAN_ALL)) == ("부산광역시", [])  # 부산 전체
    assert classify_region(zip_codes(NATION))[0] == "전국"
    assert classify_region(zip_codes("11110"))[0] == "서울특별시"
    assert classify_region([]) == (None, [])


def test_period_formats():
    assert parse_period("20260301 ~ 20260331") == (date(2026, 3, 1), date(2026, 3, 31))
    assert parse_period("2026.03.01~2026.03.31") == (date(2026, 3, 1), date(2026, 3, 31))
    assert parse_period("상시") == (None, None)


def test_draft_is_valid_policy_and_parses():
    d = draft(ITEM)
    pol = Policy.model_validate(d["policy"])
    assert pol.policy_id == "ontong-20260301005400110001"
    assert pol.region == "부산광역시" and pol.apply_end == date(2026, 3, 31)
    assert pol.amount_krw is None  # 금액은 사람이 계산해서 넣는다
    tree = parse(pol.condition_dsl)
    dsl = tree.to_dsl()
    assert "age(19..34)" in dsl and "해운대구" in dsl and "manual(" in dsl
    assert any("금액" in r for r in d["review"])


def test_scope_filter():
    assert wanted({**ITEM, "zipCd": NATION}, "busan")
    assert not wanted({**ITEM, "zipCd": "11110"}, "busan")
    assert wanted({**ITEM, "zipCd": "11110"}, "all")


def test_code_tables_become_conditions():
    """온통청년 코드(취업·학력·혼인·소득)가 조건식으로 바뀌고, 그 조건식이 실제로 판정된다."""
    item = {
        **ITEM,
        "jobCd": "0013003,0013006",  # 미취업자 + (예비)창업자
        "schoolCd": "0049007",  # 대학 졸업
        "mrgSttsCd": "0055003",  # 제한없음 → 조건 없음
        "earnCndSeCd": "0043002",
        "earnMaxAmt": "3600",  # 연 3,600만 원 (만 원 단위로 보임)
        "aplyPrdSeCd": "0057002",  # 상시
        "addAplyQlfcCndCn": "",
    }
    d = draft(item)
    dsl = parse(d["policy"]["condition_dsl"]).to_dsl()
    assert 'employment in ["구직중", "미취업"]' in dsl and "(예비)창업자" in dsl
    assert 'education in ["대학졸업"]' in dsl
    assert "income(personal) <= 3000000" in dsl  # 연 3,600만 ÷ 12
    assert "미혼" not in dsl and "기혼" not in dsl
    assert d["policy"]["apply_start"] is None and d["policy"]["apply_end"] is None
    assert any("단위" in r for r in d["review"])


def test_other_region_government_is_not_nationwide():
    """전국 코드로 등록돼도 부산 밖 지자체 정책은 거르고, 중앙부처·산하기관은 남긴다."""
    gov = {**ITEM, "zipCd": NATION}
    assert wanted({**gov, "rgtrHghrkInstCdNm": "국토교통부"}, "busan")
    assert wanted(
        {**gov, "rgtrHghrkInstCdNm": "정부산하기관및위원회"}, "busan"
    )  # '부산' 글자 포함 주의
    for name in ("경상북도", "충청북도", "전남광주통합특별시", "서울특별시"):
        assert is_other_region_gov({**gov, "rgtrHghrkInstCdNm": name})
        assert not wanted({**gov, "rgtrHghrkInstCdNm": name}, "busan")
    assert is_other_region_gov({**gov, "sprvsnInstCdNm": "경상북도 의성군 관광복지국"})
    assert not is_other_region_gov({**gov, "sprvsnInstCdNm": "부산광역시 청년산학국"})
    assert wanted({**gov, "rgtrHghrkInstCdNm": "경상북도"}, "all")


def test_is_open():
    today = date(2026, 11, 2)
    assert is_open({"aplyPrdSeCd": "0057002"}, today)  # 상시
    assert not is_open({"aplyPrdSeCd": "0057003"}, today)  # 마감
    assert is_open({"aplyPrdSeCd": "0057001", "aplyYmd": "20260801 ~ 20261231"}, today)
    assert not is_open({"aplyPrdSeCd": "0057001", "aplyYmd": "20260301 ~ 20260331"}, today)
    assert is_open({"aplyPrdSeCd": "0057001", "aplyYmd": "20261201 ~ 20261215"}, today)  # 예정
    assert is_open({"aplyPrdSeCd": "0057001", "aplyYmd": ""}, today)  # 읽을 수 없으면 사람이 확인


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("[www.hf.go.kr](https://www.hf.go.kr)", "https://www.hf.go.kr"),
        ("www.kiat.or.kr", "https://www.kiat.or.kr"),
        ("http://www.moel.go.kr/policy/list18.do", "https://www.moel.go.kr/policy/list18.do"),
        ("https://www.molit.go.kr/", "https://www.molit.go.kr/"),
        ("", "https://www.youthcenter.go.kr"),
        (None, "https://www.youthcenter.go.kr"),
        ("문의 바랍니다", "https://www.youthcenter.go.kr"),
    ],
)
def test_clean_url(raw, expected):
    assert clean_url(raw) == expected
