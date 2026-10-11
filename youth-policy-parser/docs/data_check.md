# 정책 데이터 검수 체크리스트

정책 9건은 2차 출처(언론 보도, 정책 정리 사이트)로 작성했습니다.
발표 전에 공식 공고문과 아래 항목을 대조하고, 다르면 JSON을 고친 뒤 `validate.py`와 `pytest`를 돌리세요.

| 정책 파일 | 현재 출처 | 공식 확인처 | 특히 볼 것 |
| --- | --- | --- | --- |
| `busan-joy-double-account-2026` | 서울신문 2026-08-03 | boogi2.kr | 소득 판단 방식(건보료), 제외대상 목록이 2026 공고와 같은지 (현재 과거 공고 기준) |
| `busan-didimdol-plus-2026` | 정리 블로그 | youthdidimdol.kr | 소득 150% 기준 연도(2025), 학력 예외, 국민취업지원제도와 중복 가능 여부 |
| `busan-youth-rent-support` | 부산청년플랫폼 안내 | young.busan.go.kr | 지원 개월 수(12 / 24), 2026 신청 기간 |
| `busan-job-matching-intern-2026` | 부산청년플랫폼 요약 | 부산시 공고 | 거주 요건, 신청 기간 |
| `busan-culture-art-pass-2026` | 부산청년플랫폼 요약 | 부산시 공고 | 나이 기준이 '만 나이'인지 '출생연도'인지 |
| `youth-challenge-support-2026` | 정책 정리 사이트 | work.go.kr/youngChallenge | 부산 운영 여부, 휴학생 참여 가능 여부 |
| `national-employment-support-youth` | 정리 블로그 | work24.go.kr | 청년특례 나이(15 / 18세~), 소득 120%, 재산 기준 |
| `youth-tomorrow-savings-2026` | 정책 정리 사이트 | bokjiro.go.kr | 2026 모집 기간, 소득 50% 기준 |
| `youth-future-savings-2026` | 다음 뉴스 2026-06-22 | 서민금융진흥원 | 정부기여금 % (금액 108만 원 계산 근거) |

## 데이터에 반영하지 못한 것 (발표에서 '한계'로 설명)

- 군 복무 기간만큼 연령 상한을 늘려 주는 규칙 (프로필에 복무 기간이 없음)
- 건강보험료 기준 소득 → 월소득으로 근사
- 원가구(부모 포함) 소득 → `manual()`로 '확인 필요' 처리
- 재산 기준 → 프로필에 없음
