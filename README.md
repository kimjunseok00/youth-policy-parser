# 청년정책 자격요건 파서

청년정책의 자연어 자격요건을 조건식(DSL)으로 바꿔서, 프로필을 넣으면 정책마다
**충족 / 불충족 / 확인 필요**와 그 이유, **이것만 바꾸면 받을 수 있는 정책**, **중복수혜를 고려한 최대 수령액**을 알려주는 서비스입니다.

- 프로젝트 코드와 상세 설명: [`youth-policy-parser/`](youth-policy-parser/README.md)
- DSL 명세: [`youth-policy-parser/docs/dsl_spec.md`](youth-policy-parser/docs/dsl_spec.md)
- 정책 데이터 검수 체크리스트: [`youth-policy-parser/docs/data_check.md`](youth-policy-parser/docs/data_check.md)

## 빠르게 실행하기

```bash
cd youth-policy-parser
uv sync
uv run streamlit run streamlit_app.py
```

## 배포

Streamlit Community Cloud가 이 저장소의 `main` 브랜치를 배포합니다.
진입 파일은 `youth-policy-parser/streamlit_app.py`이고, `main`에 머지되면 자동으로 다시 배포됩니다.

## 작업 규칙

1. `main`에서 직접 작업하지 않고 브랜치(`feat/...`, `fix/...`, `data/...`)를 만든다.
2. PR을 올리면 GitHub Actions(CI)가 린트 · 데이터 검증 · 테스트를 자동으로 돌린다.
3. CI가 ✅일 때만 머지한다.

## 팀

| 역할 | 담당 |
| --- | --- |
| 엔진 · 팀장 | 판정 엔진, DSL, 저장소 관리 |
| 데이터 | 정책 수집 · DSL 변환 · 공고문 검수 |
| 앱 · 발표 | Streamlit 화면, 데모 시나리오, 발표 자료 |
