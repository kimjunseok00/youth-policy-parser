# 되나요 — 청년정책, 나도 되나요?

부산 청년정책의 자격요건을 조건식으로 판정해, 받을 수 있는 것과 없는 것을 **이유까지** 알려주는 서비스입니다.

| | 주소 |
| --- | --- |
| 서비스 소개 | https://kimjunseok00.github.io/youth-policy-parser |
| 판정 앱 | https://youth-policy-parser-kenjdcyvrqqgkjbfxtebmw.streamlit.app |

## 저장소 구조

```
youth-policy-parser/   판정 엔진 + Streamlit 앱 (코드·데이터·테스트)
site/                  서비스 소개·개인정보처리방침·이용약관 (GitHub Pages)
.github/workflows/     CI(린트·데이터 검증·테스트), Pages 배포
.devcontainer/         Codespaces 개발 환경
```

- 코드 설명: [`youth-policy-parser/README.md`](youth-policy-parser/README.md)
- 배포·운영 가이드: [`youth-policy-parser/docs/deploy.md`](youth-policy-parser/docs/deploy.md)
- DSL 명세: [`youth-policy-parser/docs/dsl_spec.md`](youth-policy-parser/docs/dsl_spec.md)

## 빠르게 실행하기

```bash
cd youth-policy-parser
uv sync
uv run streamlit run streamlit_app.py
```

## 작업 규칙

1. `main`에서 직접 작업하지 않고 브랜치(`feat/...`, `fix/...`, `data/...`)를 만든다.
2. PR을 올리면 CI가 린트 · 데이터 검증 · 테스트를 자동으로 돌린다.
3. CI가 ✅일 때만 머지한다. 머지하면 앱과 소개 사이트가 자동으로 갱신된다.

## 팀

| 역할 | 담당 |
| --- | --- |
| 엔진 · 팀장 | 판정 엔진, DSL, 저장소·배포 관리 |
| 데이터 | 정책 수집 · DSL 변환 · 공고문 검수 |
| 앱 · 발표 | 화면, 데모 시나리오, 발표 자료 |
