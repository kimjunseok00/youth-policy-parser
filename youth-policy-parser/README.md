# 되나요 — 청년정책 자격 판정 엔진과 앱

| 화면 | 대상 | 코드 | 배포 |
| --- | --- | --- | --- |
| 청년용 앱 (PWA, 휴대폰) | 청년 | `pwa/` + `engine/service.py` | GitHub Pages `/app/` — [구조 설명](docs/app.md) |
| 지자체용 웹 | 지자체·기관 | `app/`, `streamlit_app.py` | Streamlit Community Cloud |

두 화면은 같은 판정 엔진(`engine/`)을 쓴다. 앱은 브라우저 안의 Python(Pyodide)으로 엔진을 직접 실행하므로 입력 정보가 서버로 가지 않는다.

청년정책의 자연어 자격요건을 **조건식(DSL)** 으로 바꿔서, 프로필을 넣으면 정책마다
**충족 / 불충족 / 확인 필요**와 그 이유를 알려주는 서비스입니다.

## 기능

| 기능 | 설명 | 코드 |
| --- | --- | --- |
| 판정 + 탈락 사유 | 조건별 충족 / 불충족 / 확인 필요 배지와 "내 값" (예: 가구소득 84% > 기준 60%), 사유 트리 그림 | `engine/evaluator.py`, `app/viz.py` |
| 확인 질문 | 자동 판정할 수 없는 조건(무주택 등)을 예/아니오로 묻고 다시 판정 | `manual()` + `answers` |
| 이것만 바꾸면 | 전입·구직 등록·기존 지원 종료처럼 **행동으로 바꿀 수 있는 것**만 골라 전체를 다시 판정. 잃는 정책도 계산 | `engine/counterfactual.py` |
| 조건 하나만 어긋난 정책 | 탈락 원인이 하나뿐인 정책과 기준선까지의 차이 | `engine/counterfactual.py` |
| 일정 | 자격이 생기는 날·사라지는 날(연령 상한, 군 복무 연장 반영)·마감 임박 | `engine/timeline.py` |
| 최적 조합 | 중복수혜 제약을 지키며 금액이 가장 큰 묶음 (정수계획법, PuLP) | `engine/optimizer.py` |
| 기대 수령액 순위 | '확인 필요' 정책을 금액 × 통과 가능성 순으로 정렬 | `likelihood()` |
| 군 복무 연장 | "군 복무 기간만큼 연령 상한 연장(최대 N년)" 규칙 | `age(..34, military=72)` |
| 소득 환산기 | 월소득 → 기준중위소득 % (2026, 보건복지부고시 제2025-135호) | `engine/income.py` |
| 지자체 리포트 | 정책별 탈락 원인 순위, 구·군별 충족률, **조건 완화 시뮬레이터**(대상자·예산 추정) | `engine/report.py`, `app/page_report.py` |
| 익명 통계 (선택) | 동의한 경우에만 개인을 알아볼 수 없는 요약 저장 → 실사용 리포트 | `engine/anonymize.py`, `app/telemetry.py` |

## 구조

```
pwa/                    청년용 앱 화면 (index.html, app.js, worker.js, sw.js) — docs/app.md
streamlit_app.py        지자체용 웹 진입점: 페이지 3개(자격 판정 · 지자체 리포트 · 서비스 안내)
app/
  __init__.py           화면이 부르는 함수: get_results(), get_insights(), manual_questions()
  page_check.py         자격 판정 화면
  page_report.py        지자체 리포트 화면
  page_about.py         서비스 안내 화면
  telemetry.py          익명 통계 저장 (Supabase, 설정했을 때만)
  branding.py           서비스 이름·주소 (이름을 바꾸려면 여기만)
  viz.py, ui_common.py  사유 트리 그림, 공통 표시
engine/                 판정 엔진 (Streamlit을 import하지 않음 → 브라우저에서도 실행)
  service.py            웹·앱 공용 입구: judge_json() / meta_json()
  grammar.lark          DSL 문법 = BNF 설계 문서
  parser.py · nodes.py  문장 → AST (+ 의미 검사)
  evaluator.py          AST + 프로필 → 판정 + 사유 트리
  counterfactual.py     이것만 바꾸면 / 조건 하나만 어긋난 정책
  timeline.py           일정
  optimizer.py          최적 조합
  report.py             지자체 리포트 (가상 인구, 집계, 시뮬레이터)
  anonymize.py          익명 요약
  dates.py · income.py  날짜 규칙 · 기준중위소득
  regions.py · benefits.py  행정구역 · 혜택 이름 사전
data/
  policies/             정책 1건 = JSON 1개 (현재 9건, 출처 URL 포함)
  personas.json         예시 인물 6명 (데모 시나리오)
  reference/            기준중위소득표, 혜택 이름 사전
docs/                   DSL 명세, 데이터 검수 체크리스트, 배포·운영 가이드, Supabase SQL
prompts/convert.md      정책 원문 → DSL 변환 공용 프롬프트
tests/                  파서 · 평가기 · 차별 기능 · 리포트 · 데이터 · 화면 · 페르소나 회귀
```

## 실행

```bash
uv sync                                   # 설치 (Python 3.12)
uv run streamlit run streamlit_app.py     # 화면 (http://localhost:8501)
uv run pytest                             # 테스트
uv run python scripts/validate.py         # 정책 데이터 검증
uv run python scripts/build_app.py        # 청년용 앱 빌드 → pwa/dist (docs/app.md)
uv run ruff check . && uv run ruff format .
```

익명 통계를 로컬에서 시험하려면 `.streamlit/secrets.toml.example`을 `.streamlit/secrets.toml`로 복사해 값을 채웁니다 (커밋 금지).

## 문서

- [DSL 명세](docs/dsl_spec.md)
- [정책 데이터 검수 체크리스트](docs/data_check.md) — **발표·출시 전에 꼭**
- [청년용 앱 구조·실행](docs/app.md)
- [배포·운영 가이드](docs/deploy.md)

판정 결과는 참고용이며, 최종 자격은 각 공고문과 담당 기관에서 확인해야 합니다.
