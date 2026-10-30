"""온통청년 청년정책 API 응답 → 검수용 정책 초안.

원칙
- 응답 구조: result.youthPolicyList(정책 목록), result.pagging.totCount(전체 건수).
  공개 프로젝트 코드로 확인했지만, 바뀌어도 동작하도록 정책 필드(plcyNm 등)를 가진 가장 큰 목록을 찾는다.
- 코드표: 온통청년 「API코드정보.xlsx」(공개 저장소 YouthFit의 docs/에서 확인, 2026-10).
- 자동 변환: 연령, 지역(zipCd), 신청 기간, 취업 상태(jobCd), 학력(schoolCd), 연소득(earnCndSeCd=0043002).
  연소득 단위는 '만원'으로 보이지만 공식 문서로 확인하지 못해 review에 남긴다.
  혼인·특화 대상·추가 자격처럼 프로필로 판정할 수 없는 조건은 manual()로 남겨 '확인 필요'가 되게 한다.
- 결과는 '초안(draft)'이다. data/drafts/에만 저장하고, 사람이 공고문과 대조한 뒤
  scripts/promote.py로 data/policies/에 옮겨야 앱에 나온다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date

from engine.regions import BUSAN_SIGUNGU

NAME_KEYS = ("plcyNm", "plcyNo")  # 이 필드가 있는 dict 목록 = 정책 목록

# 법정동코드 앞 2자리 → 시·도 (2023 강원특별자치도 51, 2024 전북특별자치도 52 반영)
SIDO_CODE = {
    "11": "서울특별시", "26": "부산광역시", "27": "대구광역시", "28": "인천광역시",
    "29": "광주광역시", "30": "대전광역시", "31": "울산광역시", "36": "세종특별자치시",
    "41": "경기도", "42": "강원특별자치도", "51": "강원특별자치도", "43": "충청북도",
    "44": "충청남도", "45": "전북특별자치도", "52": "전북특별자치도", "46": "전라남도",
    "47": "경상북도", "48": "경상남도", "50": "제주특별자치도",
}  # fmt: skip
# 부산 구·군 법정동코드 앞 5자리 (행정표준코드)
BUSAN_CODE = {
    "26110": "중구", "26140": "서구", "26170": "동구", "26200": "영도구", "26230": "부산진구",
    "26260": "동래구", "26290": "남구", "26320": "북구", "26350": "해운대구", "26380": "사하구",
    "26410": "금정구", "26440": "강서구", "26470": "연제구", "26500": "수영구", "26530": "사상구",
    "26710": "기장군",
}  # fmt: skip
# 온통청년 코드 → 우리 프로필 값. None은 프로필로 판정할 수 없어 manual()로 남기는 코드
JOB_CODE = {
    "0013001": ["재직"], "0013002": ["자영업"], "0013003": ["미취업", "구직중"], "0013004": ["프리랜서"],
    "0013005": None, "0013006": None, "0013007": ["재직"], "0013008": None, "0013009": None,
}  # fmt: skip
JOB_NAME = {
    "0013005": "일용근로자",
    "0013006": "(예비)창업자",
    "0013008": "영농종사자",
    "0013009": "기타",
}
SCHOOL_CODE = {
    "0049001": None, "0049002": None, "0049003": None, "0049004": ["고졸"],
    "0049005": ["대학재학", "대학휴학"], "0049006": ["졸업예정"], "0049007": ["대학졸업"],
    "0049008": ["대학원"], "0049009": None,
}  # fmt: skip
SCHOOL_NAME = {
    "0049001": "고졸 미만",
    "0049002": "고교 재학",
    "0049003": "고졸 예정",
    "0049009": "기타",
}
SBIZ_NAME = {
    "0014001": "중소기업", "0014002": "여성", "0014003": "기초생활수급자", "0014004": "한부모가정",
    "0014005": "장애인", "0014006": "농업인", "0014007": "군인", "0014008": "지역인재", "0014009": "기타",
}  # fmt: skip
NO_LIMIT = {"0013010", "0049010", "0014010", "0055003"}  # '제한없음'
ALWAYS_OPEN = "0057002"  # aplyPrdSeCd 상시
INCOME_ANNUAL = "0043002"  # earnCndSeCd 연소득
NATIONWIDE_MIN_SIDO = 10  # 이만큼 많은 시·도를 포함하면 전국 정책으로 본다


# ---------------------------------------------------------------------------
# 응답 구조 다루기
# ---------------------------------------------------------------------------
def find_items(payload: object) -> list[dict]:
    """응답 어디에 있든 정책 dict 목록을 찾는다 (가장 긴 것)."""
    best: list[dict] = []

    def walk(x: object) -> None:
        nonlocal best
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            dicts = [i for i in x if isinstance(i, dict)]
            if dicts and any(k in dicts[0] for k in NAME_KEYS) and len(dicts) > len(best):
                best = dicts
            for i in x:
                walk(i)

    walk(payload)
    return best


def find_total(payload: object) -> int | None:
    """전체 건수 필드(totCount 등)를 찾는다. 없으면 None."""
    if isinstance(payload, dict):
        for k, v in payload.items():
            if re.fullmatch(r"(?i)tot(al)?_?cnt|tot(al)?_?count|totalcount", k):
                try:
                    return int(v)
                except (TypeError, ValueError):
                    pass
            found = find_total(v)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for i in payload:
            found = find_total(i)
            if found is not None:
                return found
    return None


def describe(payload: object, depth: int = 0, key: str = "(최상위)") -> list[str]:
    """응답 구조를 사람이 읽을 수 있게 요약 (값은 빼고 키와 형태만). --inspect용."""
    pad = "  " * depth
    if isinstance(payload, dict):
        lines = [f"{pad}{key}: dict({len(payload)})"]
        for k, v in payload.items():
            lines += describe(v, depth + 1, k)
        return lines
    if isinstance(payload, list):
        lines = [f"{pad}{key}: list({len(payload)})"]
        if payload:
            lines += describe(payload[0], depth + 1, "[0]")
        return lines
    return [f"{pad}{key}: {type(payload).__name__}"]


# ---------------------------------------------------------------------------
# 필드 해석
# ---------------------------------------------------------------------------
def text(item: dict, key: str) -> str:
    v = item.get(key)
    return "" if v is None else str(v).strip()


def to_int(v: object) -> int | None:
    try:
        n = int(str(v).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None
    return n


def zip_codes(v: object) -> list[str]:
    """zipCd: '26110,26140' 같은 문자열이나 목록 → 5자리 코드 목록."""
    if isinstance(v, list):
        v = ",".join(map(str, v))
    return sorted(set(re.findall(r"\d{5}", str(v or ""))))


def classify_region(codes: Iterable[str]) -> tuple[str | None, list[str]]:
    """(시·도 또는 '전국', 부산 구·군 목록). 코드가 없으면 (None, [])."""
    codes = list(codes)
    if not codes:
        return None, []
    sidos = {SIDO_CODE.get(c[:2]) for c in codes} - {None}
    if len(sidos) >= NATIONWIDE_MIN_SIDO:
        return "전국", []
    if sidos == {"부산광역시"}:
        gus = sorted({BUSAN_CODE[c] for c in codes if c in BUSAN_CODE}, key=BUSAN_SIGUNGU.index)
        return "부산광역시", [] if len(gus) == len(BUSAN_CODE) else gus
    if len(sidos) == 1:
        return sidos.pop(), []
    return "여러 지역", []


def parse_period(v: object) -> tuple[date | None, date | None]:
    """aplyYmd: '20260301 ~ 20260331' / '2026.03.01~2026.03.31' 등 → (시작, 마감). 상시면 (None, None)."""
    found = re.findall(r"(20\d{2})[.\-/]?(\d{2})[.\-/]?(\d{2})", str(v or ""))
    days = []
    for y, m, d in found:
        try:
            days.append(date(int(y), int(m), int(d)))
        except ValueError:
            continue
    if not days:
        return None, None
    return min(days), max(days)


def codes(v: object) -> list[str]:
    """'0013003,0013006' 같은 쉼표 목록 → 코드 목록."""
    return re.findall(r"\d{7}", str(v or ""))


def status_condition(field: str, mapping: dict, names: dict, label: str, item: dict) -> str | None:
    """취업·학력 코드 → 'employment in [...]' 조건. 프로필에 없는 값은 manual()로 OR 연결."""
    cs = [c for c in codes(item.get(field)) if c not in NO_LIMIT]
    if not cs:
        return None
    values = sorted({v for c in cs for v in (mapping.get(c) or [])})
    others = [names.get(c, c) for c in cs if mapping.get(c) is None]
    parts = []
    if values:
        key = "employment" if field == "jobCd" else "education"
        parts.append(f"{key} in [" + ", ".join(f'"{v}"' for v in values) + "]")
    if others:
        parts.append(f'manual("{label}: ' + "·".join(others) + ' 해당")')
    return parts[0] if len(parts) == 1 else "(" + " OR ".join(parts) + ")"


def policy_id(item: dict) -> str:
    raw = text(item, "plcyNo") or text(item, "plcyNm")
    return "ontong-" + (re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-") or "unknown")


def _quote(s: str) -> str:
    return s.replace("\\", " ").replace('"', "'").replace("\n", " ").strip()


# ---------------------------------------------------------------------------
# 초안 만들기
# ---------------------------------------------------------------------------
def draft(item: dict) -> dict:
    """정책 1건 → {'policy': Policy 형식 dict, 'review': 사람이 확인할 목록, 'raw': 원본}."""
    review: list[str] = []
    lines: list[str] = []

    lo, hi = to_int(item.get("sprtTrgtMinAge")), to_int(item.get("sprtTrgtMaxAge"))
    lo = lo if lo and 0 < lo < 120 else None
    hi = hi if hi and 0 < hi < 120 else None
    if lo or hi:
        lines.append(f"age({lo or ''}..{hi or ''})   # API sprtTrgtMinAge/MaxAge")
        review.append("연령: 만 나이 기준인지, 군 복무 연장(military=)이 있는지 공고문 확인")
    else:
        review.append("연령 조건이 API에 없음: 공고문에서 확인")

    region, gus = classify_region(zip_codes(item.get("zipCd")))
    if region == "부산광역시":
        if gus:
            lines.append(
                "(" + " OR ".join(f'region("부산광역시", "{g}")' for g in gus) + ")   # API zipCd"
            )
        else:
            lines.append('region("부산광역시")   # API zipCd')
    elif region in (None, "여러 지역"):
        review.append("지역: API zipCd로 판단할 수 없음, 공고문 확인")

    for field, mapping, names, label in (
        ("jobCd", JOB_CODE, JOB_NAME, "취업 상태"),
        ("schoolCd", SCHOOL_CODE, SCHOOL_NAME, "학력"),
    ):
        cond = status_condition(field, mapping, names, label, item)
        if cond:
            lines.append(f"{cond}   # API {field}")
    if "0055002" in codes(item.get("mrgSttsCd")):
        lines.append('manual("미혼")   # API mrgSttsCd')
    elif "0055001" in codes(item.get("mrgSttsCd")):
        lines.append('manual("기혼")   # API mrgSttsCd')
    special = [SBIZ_NAME[c] for c in codes(item.get("sbizCd")) if c in SBIZ_NAME]
    if special:
        lines.append('manual("특화 대상: ' + "·".join(special) + ' 해당")   # API sbizCd')

    earn_max = to_int(item.get("earnMaxAmt"))
    if text(item, "earnCndSeCd") == INCOME_ANNUAL and earn_max:
        monthly = earn_max * 10_000 // 12
        lines.append(f"income(personal) <= {monthly}   # API 연소득 {earn_max}만 원 이하 → 월 환산")
        review.append(
            f"소득: API 연소득 상한 {earn_max} — 단위(만 원)와 본인/가구 기준을 공고문으로 확인"
        )
    elif text(item, "earnCndSeCd") == "0043003" or text(item, "earnEtcCn"):
        etc = _quote(text(item, "earnEtcCn"))[:50] or "공고문 기준"
        lines.append(f'manual("소득: {etc}")   # API earnEtcCn')
        review.append("소득: 기준중위소득 %면 income_pct(household) 조건으로 바꾸기")
    extra = text(item, "addAplyQlfcCndCn")
    if extra:
        short = _quote(extra)[:60]
        lines.append(f'manual("추가 자격: {short}")   # API addAplyQlfcCndCn')
        review.append("추가 자격조건 원문을 조건식(취업상태·학력·거주기간 등)으로 나누기")
    excl = text(item, "ptcpPrpTrgtCn")
    if excl:
        review.append("참여 제한 대상(중복수혜 등)을 NOT receiving(...)으로 옮기기")

    start, end = (
        (None, None)
        if text(item, "aplyPrdSeCd") == ALWAYS_OPEN
        else parse_period(item.get("aplyYmd"))
    )
    source = (
        text(item, "refUrlAddr1") or text(item, "aplyUrlAddr") or "https://www.youthcenter.go.kr"
    )
    review.append("지원 금액(amount_krw): 1인 총 수령액으로 계산해 넣기")
    policy = {
        "policy_id": policy_id(item),
        "name": text(item, "plcyNm"),
        "agency": text(item, "sprvsnInstCdNm") or text(item, "operInstCdNm") or "확인 필요",
        "region": region if region and region != "여러 지역" else "확인 필요",
        "amount_krw": None,
        "amount_text": _quote(text(item, "plcySprtCn"))[:300] or "공고문 확인",
        "apply_start": start.isoformat() if start else None,
        "apply_end": end.isoformat() if end else None,
        "source_url": source,
        "eligibility_text": "\n".join(x for x in [text(item, "plcyExplnCn"), extra] if x)
        or "공고문 확인",
        "exclusion_text": excl,
        "condition_dsl": "\nAND ".join(lines) if lines else None,
        "exclusive_with": [],
    }
    return {"status": "draft", "source": "온통청년 OpenAPI", "review": review,
            "policy": policy, "raw": item}  # fmt: skip


def wanted(item: dict, scope: str) -> bool:
    """수집 범위: 'busan' = 부산 + 전국 정책, 'all' = 전부."""
    if scope == "all":
        return True
    region, _ = classify_region(zip_codes(item.get("zipCd")))
    return region in ("부산광역시", "전국")
