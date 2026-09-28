"""팀 공용 데이터 스키마 (Profile / Policy / Result).

세 역할(엔진·데이터·앱)이 동시에 작업할 수 있도록 주고받는 데이터의 모양을 여기서 고정한다.
필드 이름을 바꾸면 세 사람의 작업이 동시에 깨지므로, 변경은 반드시 팀장 승인 후에만 한다.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field, model_validator


# ---------------------------------------------------------------------------
# 1. Profile: 사용자가 입력하는 정보
# ---------------------------------------------------------------------------
class Education(StrEnum):
    """학력/재학 상태. 정책 조건의 '재학생', '졸업예정자' 등을 판정하는 기준."""

    HIGH_SCHOOL = "고졸"
    ENROLLED = "대학재학"
    ON_LEAVE = "대학휴학"
    GRADUATING = "졸업예정"
    GRADUATED = "대학졸업"
    GRADUATE_SCHOOL = "대학원"


class Employment(StrEnum):
    """취업 상태. '미취업자', '구직자' 조건 판정 기준."""

    UNEMPLOYED = "미취업"
    JOB_SEEKING = "구직중"
    EMPLOYED = "재직"
    SELF_EMPLOYED = "자영업"
    FREELANCER = "프리랜서"


class Profile(BaseModel):
    """판정에 쓰이는 사용자 프로필.

    나이 대신 생년월일을 받는다. 기준일을 바꿔 다시 판정하면
    "언제부터 자격이 생기는지(시간축 판정)"를 계산할 수 있기 때문이다.
    """

    birth_date: date
    sido: str = Field(examples=["부산광역시"])
    sigungu: str = Field(examples=["부산진구"])
    residence_since: date = Field(description="현 주소 전입일")
    education: Education
    employment: Employment
    personal_income_monthly: int = Field(ge=0, description="본인 월소득(원)")
    household_size: int = Field(ge=1, description="가구원 수")
    household_income_monthly: int = Field(ge=0, description="가구 월소득(원)")
    current_benefits: list[str] = Field(default_factory=list, description="현재 받고 있는 지원")

    @model_validator(mode="after")
    def _check_dates(self) -> Profile:
        # 태어나기 전에 전입할 수는 없다: 입력 실수를 조기에 잡는다.
        if self.residence_since < self.birth_date:
            raise ValueError("전입일(residence_since)이 생년월일보다 빠를 수 없습니다.")
        return self


# ---------------------------------------------------------------------------
# 2. Policy: 데이터 담당이 만드는 정책 1건 (data/policies/*.json 한 파일)
# ---------------------------------------------------------------------------
class Policy(BaseModel):
    """정책 1건. 원문과 DSL을 함께 보관해서 판정 근거를 원문으로 되짚을 수 있게 한다."""

    policy_id: str = Field(pattern=r"^[a-z0-9_-]+$", examples=["busan-job-intern-2026"])
    name: str
    agency: str
    region: str = Field(description="'전국' 또는 시·도 이름", examples=["부산광역시"])
    amount_krw: int | None = Field(
        default=None, ge=0, description="예상 총 수령액(원). 대출처럼 금액 환산이 어려우면 null"
    )
    amount_text: str = Field(
        description="지원 내용 원문 요약", examples=["월 150만 원 × 최대 3개월"]
    )
    apply_start: date | None = Field(default=None, description="null이면 상시")
    apply_end: date | None = Field(default=None, description="null이면 상시")
    source_url: str
    eligibility_text: str = Field(description="자격요건 원문 (요약 금지)")
    exclusion_text: str = Field(default="", description="제외대상 원문 (요약 금지)")
    condition_dsl: str | None = Field(
        default=None, description="자격요건을 DSL로 변환한 것. null이면 '확인 필요'로 처리"
    )
    exclusive_with: list[str] = Field(
        default_factory=list, description="중복수혜가 불가능한 다른 정책의 policy_id"
    )


# ---------------------------------------------------------------------------
# 3. Result: 엔진이 돌려주고 앱이 화면에 그리는 판정 결과
# ---------------------------------------------------------------------------
class Verdict(StrEnum):
    """3값 논리. 해석할 수 없는 조건을 억지로 판정하지 않고 '확인 필요'로 분리한다."""

    PASS = "충족"
    FAIL = "불충족"
    UNKNOWN = "확인필요"


class ReasonNode(BaseModel):
    """탈락 사유 트리의 노드. AND/OR 같은 복합 조건은 children으로 내려간다."""

    label: str = Field(examples=["가구소득 기준중위소득 150% 이하"])
    verdict: Verdict
    detail: str = Field(default="", examples=["내 가구소득 180% > 기준 150%"])
    source_quote: str | None = Field(
        default=None, description="근거가 된 원문 문장 (원문 하이라이트용)"
    )
    children: list[ReasonNode] = Field(default_factory=list)


class PolicyResult(BaseModel):
    """정책 1건에 대한 판정."""

    policy_id: str
    policy_name: str
    agency: str
    verdict: Verdict
    amount_krw: int | None = None
    apply_end: date | None = None
    reason: ReasonNode


class EvaluationResult(BaseModel):
    """프로필 1개에 대한 전체 판정 결과. 앱은 이 객체 하나만 받아서 화면을 그린다."""

    as_of: date = Field(description="판정 기준일")
    results: list[PolicyResult]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_expected_krw(self) -> int:
        """충족 정책의 수령액 단순 합계. (중복수혜를 반영한 값은 최적 조합 기능에서 계산)"""
        return sum(r.amount_krw or 0 for r in self.results if r.verdict == Verdict.PASS)

    def by_verdict(self, verdict: Verdict) -> list[PolicyResult]:
        """화면의 탭(충족/불충족/확인 필요)별로 결과를 나눌 때 사용."""
        return [r for r in self.results if r.verdict == verdict]
