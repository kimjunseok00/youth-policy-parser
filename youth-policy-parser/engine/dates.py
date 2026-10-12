"""날짜 계산 규칙 (평가기와 시간축이 같은 규칙을 쓰도록 한 곳에 모은다).

- 만 나이: 생일 당일에 한 살 늘어난다.
- 개월 수: 일(day)까지 채워야 한 달로 센다. 말일 처리는 add_months와 full_months가 서로 일치한다.
- 2월 29일생: 평년에는 3월 1일에 나이가 늘어난다.
"""

from __future__ import annotations

from datetime import date


def full_age(birth: date, on: date) -> int:
    """만 나이."""
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def full_months(start: date, on: date) -> int:
    """start부터 on까지 꽉 찬 개월 수. 2024-02-01 → 2025-02-01 = 12개월."""
    months = (on.year - start.year) * 12 + (on.month - start.month)
    return months - (on.day < start.day)


def add_months(d: date, months: int) -> date:
    """d에서 months개월 뒤. 그 달에 같은 날이 없으면 다음 달 1일 (full_months와 같은 기준)."""
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    try:
        return d.replace(year=year, month=month)
    except ValueError:
        nxt_y, nxt_m = (year + 1, 1) if month == 12 else (year, month + 1)
        return date(nxt_y, nxt_m, 1)


def birthday(birth: date, age: int) -> date:
    """만 age세가 되는 날. 2월 29일생은 평년에는 3월 1일로 본다 (full_age와 일치)."""
    year = birth.year + age
    try:
        return birth.replace(year=year)
    except ValueError:
        return date(year, 3, 1)


def age_for_cap(birth: date, on: date, service_months: int, max_extension_months: int) -> int:
    """연령 '상한' 판정용 나이. 군 복무 기간을 (최대 max_extension_months까지) 빼고 센다.

    "군 복무 기간만큼 연령 상한 연장(최대 6년)" = 생일을 복무 기간만큼 늦춘 것과 같다.
    """
    extension = min(max(service_months, 0), max_extension_months)
    return full_age(add_months(birth, extension), on)
