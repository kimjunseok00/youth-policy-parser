"""소득 환산: 월소득 → 기준중위소득 대비 %.

정책 조건의 "기준중위소득 150% 이하"를 판정하려면 사용자의 소득이 몇 %인지 알아야 한다.
대부분의 청년은 자기가 몇 %인지 모르기 때문에, 이 모듈은 평가기와 '소득 환산기' 화면 양쪽에서 쓴다.

기준표: data/reference/median_income_2026.json (보건복지부고시 제2025-135호)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

REFERENCE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "reference" / "median_income_2026.json"
)


@dataclass(frozen=True)
class MedianIncomeTable:
    """가구원 수별 기준중위소득 표."""

    year: int
    monthly_krw: dict[int, int]  # 가구원 수 → 월 금액(원)
    per_additional_member_krw: int  # 표의 최대 인원을 넘을 때 1인당 추가액

    def monthly(self, household_size: int) -> int:
        """가구원 수에 해당하는 기준중위소득(월). 표보다 큰 가구는 1인당 추가액으로 늘린다."""
        if household_size < 1:
            raise ValueError("가구원 수는 1 이상이어야 합니다.")
        if household_size in self.monthly_krw:
            return self.monthly_krw[household_size]
        largest = max(self.monthly_krw)
        extra = household_size - largest
        return self.monthly_krw[largest] + extra * self.per_additional_member_krw

    def pct(self, monthly_income: int, household_size: int) -> float:
        """월소득이 기준중위소득의 몇 %인지. 예: 1인 가구 월 256만 원 → 약 100.0"""
        return monthly_income / self.monthly(household_size) * 100


@cache
def load_table(path: Path = REFERENCE_PATH) -> MedianIncomeTable:
    """기준표 JSON을 읽는다. 한 번 읽은 표는 재사용한다."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return MedianIncomeTable(
        year=raw["year"],
        monthly_krw={int(k): int(v) for k, v in raw["monthly_krw"].items()},
        per_additional_member_krw=int(raw["per_additional_member_krw"]),
    )
