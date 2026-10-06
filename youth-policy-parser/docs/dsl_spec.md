# 자격요건 DSL 명세 (v0.1 초안)

정책의 자연어 자격요건을 **기계가 판정할 수 있는 조건식**으로 옮기기 위한 작은 언어입니다.
문법의 원본은 [`engine/grammar.lark`](../engine/grammar.lark)이고, 이 문서는 그 해설입니다.

## 1. 한눈에 보기

```
region("부산광역시")
AND born(1986-01-01..2008-12-31)
AND income_pct(personal) <= 150
AND (employment in ["재직", "자영업"] OR manual("일용직 20일 이상 근무"))
AND NOT receiving("국민취업지원제도")
```

## 2. 조건 8종

| 유형 | 문법 | 예시 | 판정에 쓰는 프로필 필드 |
| --- | --- | --- | --- |
| 연령 | `age(최소..최대)` | `age(19..34)`, `age(..39)` | birth_date + 기준일 |
| 연령(생년) | `born(시작일..종료일)` | `born(1986-01-01..2008-12-31)` | birth_date |
| 거주 | `region("시·도"[, "시·군·구"])` | `region("부산광역시", "해운대구")` | sido, sigungu |
| 기간 | `residence_months 비교 개월` | `residence_months >= 12` | residence_since + 기준일 |
| 소득(%) | `income_pct(personal\|household) 비교 %` | `income_pct(household) <= 150` | 소득, household_size, 중위소득표 |
| 소득(원) | `income(personal\|household) 비교 원` | `income(personal) <= 2910000` | 소득 |
| 학력 | `education in [값, ...]` | `education in ["대학재학", "대학휴학"]` | education |
| 취업상태 | `employment in [값, ...]` | `employment in ["미취업", "구직중"]` | employment |
| 중복수혜 | `receiving("지원명")` | `NOT receiving("국민취업지원제도")` | current_benefits |
| 기타 | `manual("원문")` | `manual("무주택 청년")` | 없음 → 항상 **확인 필요** |

비교 연산자: `<=` `>=` `<` `>` `==`

## 3. 조합 규칙

- `AND`, `OR`, `NOT`, 괄호 `( )`
- 우선순위: `NOT` > `AND` > `OR` → `A OR B AND C`는 `A OR (B AND C)`
- `#` 뒤는 주석 (변환 근거 메모용)

## 4. 3값 판정 (평가기 설계 방향, 2주차 구현)

| 조합 | 결과 |
| --- | --- |
| AND | 하나라도 불충족 → **불충족** / 모두 충족 → 충족 / 그 외 → 확인 필요 |
| OR | 하나라도 충족 → **충족** / 모두 불충족 → 불충족 / 그 외 → 확인 필요 |
| NOT | 충족 ↔ 불충족, 확인 필요는 그대로 |

→ `manual()`이 섞여 있어도 **다른 조건에서 이미 탈락하면 불충족**으로 확정됩니다.
억지로 판정하지 않고, 판정할 수 없는 부분만 정확히 짚어 "확인 필요"로 보냅니다.

## 5. 변환 원칙 (데이터 담당용)

1. 프로필로 판정할 수 있는 조건은 전용 문법으로, 없는 조건은 `manual("원문")`으로 옮깁니다.
2. 제외대상은 `NOT`으로 표현합니다.
3. 원문에 없는 조건을 추측해서 넣지 않습니다. 애매하면 `manual()`에 넣습니다.
4. 시·도는 정식 명칭만 씁니다 (`"부산광역시"` O, `"부산시"` X). 틀리면 검증에서 거부됩니다.
5. 변환 후 `uv run python scripts/validate.py`를 통과해야 커밋합니다.

실제 부산 정책 변환 예시: [`data/examples/dsl_examples.json`](../data/examples/dsl_examples.json)

## 6. 알려진 한계 (문법 동결 전 검토 항목)

- 학력 조건이 들어간 실제 정책 예시를 아직 확보하지 못함
- "병역의무 이행자는 최대 2년 연장" 같은 **조건부 예외**는 `OR`와 `manual()`로만 표현 가능
- 건강보험료 기준 소득은 본인 소득(`income_pct(personal)`)으로 근사
- 원가구(부모 포함) 소득은 프로필에 없어서 `manual()` 처리
