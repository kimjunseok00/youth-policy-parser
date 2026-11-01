# 온통청년 API로 정책 늘리기

정책 데이터는 **수집 → 초안 → 검수 → 반영** 순서로 늘린다. 자동으로 만든 초안은 검수 전까지 앱에 나오지 않는다.

```
온통청년 청년정책 API ──collect.py──▶ data/raw/ontong/  (원본, 커밋 안 함)
                                  └▶ data/drafts/      (검수용 초안, 커밋)
                                        │ 데이터 담당이 공고문과 대조, review 항목 처리
                                        ▼
                         promote.py ──▶ data/policies/  (앱·리포트에 반영)
```

## 1. 준비 (처음 한 번)

`youth-policy-parser/.env` 파일을 만들고 **청년정책API**의 인증키를 넣는다. (온통청년 마이페이지 → 오픈API → 청년정책API → 조회하기)

```
ONTONG_API_KEY=여기에_인증키
```

`.env`는 `.gitignore`에 들어 있어 커밋되지 않는다. 키를 채팅·문서에 붙여 넣지 않는다.

## 2. 응답 형식 확인 (처음 한 번)

```bash
cd youth-policy-parser
uv run --env-file .env python scripts/collect.py --inspect
```

키는 앞 4자리만 보이게 가려서 출력된다. `정책 목록: 2건 찾음`이 나오면 형식이 맞는 것이다. 0건이면 출력 전체를 엔진 담당에게 전달한다.

## 3. 수집

```bash
uv run --env-file .env python scripts/collect.py              # 부산 + 전국 정책
uv run --env-file .env python scripts/collect.py --keyword 월세  # 정책명 검색
```

이미 `data/policies/`에 반영된 정책은 덮어쓰지 않는다.

## 4. 자동 변환 규칙

응답 구조는 `result.youthPolicyList`(정책 목록), `result.pagging.totCount`(전체 건수)이고, 코드 값은 온통청년 「API코드정보.xlsx」 기준이다 (공개 저장소에서 확인, 2026-10).

| API 필드 | 초안에서 | 비고 |
| --- | --- | --- |
| `sprtTrgtMinAge`, `sprtTrgtMaxAge` | `age(lo..hi)` | 0이면 조건 없음. 군 복무 연장은 공고문 보고 `military=` 추가 |
| `zipCd` (쉼표로 구분한 5자리 시군구 코드) | `region("부산광역시")` 또는 구·군별 `region(...)` | 10개 이상 시·도면 전국 정책 |
| `aplyYmd` (`YYYYMMDD ~ YYYYMMDD`), `aplyPrdSeCd` | `apply_start`, `apply_end` | `0057002`(상시)이면 기간 없음 |
| `jobCd` | `employment in [...]` | 재직·자영업·미취업·프리랜서는 자동, 일용·창업·영농은 `manual()` |
| `schoolCd` | `education in [...]` | 고졸·대학재학·졸업예정·대학졸업·대학원은 자동, 고교 재학 등은 `manual()` |
| `earnCndSeCd=0043002`(연소득) + `earnMaxAmt` | `income(personal) <= 월 환산액` | 단위는 만 원으로 보이나 **공식 문서 미확인** → review에서 확인 |
| `earnCndSeCd=0043003`(기타), `earnEtcCn` | `manual("소득: …")` | 기준중위소득 %면 `income_pct`로 바꾼다 |
| `mrgSttsCd`, `sbizCd` | `manual("미혼")`, `manual("특화 대상: …")` | 프로필에 없는 항목 |
| `addAplyQlfcCndCn` (추가 자격) | `manual("추가 자격: …")` | 취업상태·학력 등으로 나눠서 바꾼다 |
| 지원 금액 | 비워 둠 (`amount_krw: null`) | 1인 총 수령액을 계산해 넣는다 |

## 5. 검수와 반영

1. `data/drafts/<id>.json`의 `review` 목록을 하나씩 처리하고 `policy` 부분을 고친다 (`docs/data_check.md` 체크리스트).
2. 다 처리했으면 `review`를 `[]`로 비운다.
3. 반영:

```bash
uv run python scripts/promote.py data/drafts/<id>.json
uv run python scripts/validate.py && uv run pytest -q
```

`promote.py`는 금액이 비어 있거나 `review`가 남아 있으면 멈춘다.
