# 청년정책 자격요건 파서

청년정책의 자연어 자격요건을 **조건식(DSL)** 으로 바꿔서, 프로필을 넣으면
정책마다 **충족 / 불충족 / 확인 필요**와 그 이유를 알려주는 서비스입니다.

기존 서비스는 정책 목록과 조건 나열을 보여줍니다. 이 서비스는 거기에 더해 다음을 알려줍니다.

| 기능 | 설명 | 코드 |
| --- | --- | --- |
| 판정 + 탈락 사유 | 조건별로 ✅ / ❌ / ⚠️ 와 "내 값"을 보여줌 (예: 가구소득 112% > 기준 100%) | `engine/evaluator.py` |
| 확인 필요 분리 | 자동 판정할 수 없는 조건은 억지로 판정하지 않고 그 조건만 짚어 줌 | `manual()` + 3값 논리 |
| 이것만 바꾸면 | 전입·구직 등록·기존 지원 종료처럼 **행동으로 바꿀 수 있는 것**만 골라 전체를 다시 판정. 얻는 정책과 **잃는 정책**을 함께 계산 | `engine/counterfactual.py` |
| 조건 하나만 어긋난 정책 | 탈락 원인이 딱 하나인 정책과 차이 (예: 기준선까지 월 128만 원) | `engine/counterfactual.py` |
| 일정 | 자격이 **생기는 날**(나이·거주기간), **사라지는 날**(연령 상한), **마감 임박** | `engine/timeline.py` |
| 최적 조합 | 중복수혜 제약을 지키면서 금액이 가장 큰 정책 묶음 (정수계획법, PuLP) | `engine/optimizer.py` |
| 소득 환산기 | 월소득 → 기준중위소득 % (2026, 보건복지부고시 제2025-135호) | `engine/income.py` |

## 구조

```
streamlit_app.py      화면 (입력 → 결과). 판정 로직 없음
app/__init__.py       화면이 부르는 함수: get_results(), get_insights(), personas()
engine/               판정 엔진 (Streamlit을 import하지 않음 → API로 감싸기 쉬움)
  grammar.lark        DSL 문법 = BNF 설계 문서
  parser.py           문장 → AST (+ 의미 검사)
  evaluator.py        AST + 프로필 → 판정 + 사유 트리
  counterfactual.py   이것만 바꾸면 / 조건 하나만 어긋난 정책
  timeline.py         자격 발생·상실·마감 일정
  optimizer.py        최적 조합
  income.py           기준중위소득 환산
  regions.py          시·도 / 부산 구·군 목록
  benefits.py         혜택 이름 사전 (receiving()과 화면 선택지 공용)
data/
  policies/           정책 1건 = JSON 1개 (현재 9건)
  personas.json       예시 인물 5명 (데모 시나리오)
  reference/          기준중위소득표, 혜택 이름 사전
docs/dsl_spec.md      DSL 명세
prompts/convert.md    정책 원문 → DSL 변환용 공용 프롬프트
tests/                124개 (파서 · 평가기 · 차별 기능 · 데이터 · 화면 · 페르소나 회귀)
```

## 실행

```bash
uv sync                                   # 설치 (Python 3.12)
uv run streamlit run streamlit_app.py     # 화면
uv run pytest                             # 테스트
uv run python scripts/validate.py         # 정책 데이터 검증
uv run ruff check . && uv run ruff format .
```

## 정책 데이터를 추가하는 방법

1. 공고문의 자격요건을 `prompts/convert.md` 프롬프트로 DSL 초안으로 바꾼다.
2. `data/policies/<policy_id>.json`으로 저장한다 (형식은 기존 파일 참고).
3. `uv run python scripts/validate.py` → 실패 0건이 될 때까지 고친다.
4. 판정이 바뀌는 게 맞다면 `tests/regression/persona_expected.json`도 갱신한다.

## ⚠️ 발표 전에 꼭 확인할 것: 데이터 출처

정책 9건은 공식 사이트 접근이 일부 막혀 있어 **언론 보도·정리 블로그 등 2차 출처**로 작성했습니다.
각 파일의 `source_url`에 출처가 있습니다. 발표 전에 데이터 담당이 **공식 공고문과 대조**해 주세요.
→ 체크리스트: [`docs/data_check.md`](docs/data_check.md)

판정 결과는 참고용이며, 최종 자격은 각 공고문과 담당 기관에서 확인해야 합니다.
