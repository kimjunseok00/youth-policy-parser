"""스키마 테스트: 팀이 주고받는 데이터 형식이 깨지지 않았는지 확인한다."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.schemas import EvaluationResult, Policy, Profile, Verdict

ROOT = Path(__file__).resolve().parent.parent


def make_profile(**overrides) -> Profile:
    """테스트용 기본 프로필. 필요한 필드만 덮어써서 쓴다."""
    data = {
        "birth_date": "2001-03-15",
        "sido": "부산광역시",
        "sigungu": "부산진구",
        "residence_since": "2024-02-01",
        "education": "대학휴학",
        "employment": "구직중",
        "personal_income_monthly": 0,
        "household_size": 3,
        "household_income_monthly": 4_500_000,
        "current_benefits": ["국민취업지원제도"],
    }
    data.update(overrides)
    return Profile.model_validate(data)


def test_profile_valid():
    p = make_profile()
    assert p.birth_date == date(2001, 3, 15)
    assert p.education.value == "대학휴학"


def test_profile_rejects_residence_before_birth():
    with pytest.raises(ValidationError):
        make_profile(residence_since="1999-01-01")


def test_profile_rejects_negative_income():
    with pytest.raises(ValidationError):
        make_profile(household_income_monthly=-1)


def test_profile_rejects_unknown_education():
    with pytest.raises(ValidationError):
        make_profile(education="박사")


def test_mock_result_matches_schema():
    """앱 담당이 쓰는 가짜 결과 파일이 스키마와 맞는지 확인."""
    raw = (ROOT / "data" / "mock" / "mock_results.json").read_text(encoding="utf-8")
    result = EvaluationResult.model_validate_json(raw)
    assert len(result.by_verdict(Verdict.PASS)) == 2
    assert len(result.by_verdict(Verdict.FAIL)) == 3
    assert len(result.by_verdict(Verdict.UNKNOWN)) == 1
    # 충족 정책 합계: 4,500,000 + 200,000
    assert result.total_expected_krw == 4_700_000


def test_policy_id_format():
    base = {
        "name": "테스트 정책",
        "agency": "부산광역시",
        "region": "부산광역시",
        "amount_text": "20만 원",
        "source_url": "https://example.com",
        "eligibility_text": "부산 거주 청년",
    }
    Policy.model_validate({**base, "policy_id": "busan-test-2026"})
    with pytest.raises(ValidationError):
        Policy.model_validate({**base, "policy_id": "부산 테스트"})
