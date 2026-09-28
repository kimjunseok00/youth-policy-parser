# 청년정책 자격요건 파서

부산 청년이 프로필을 넣으면 정책별로 **충족 / 불충족 / 확인 필요**와 그 이유를 알려주는 서비스입니다.

## 폴더 구조

| 경로 | 담당 | 내용 |
| --- | --- | --- |
| `engine/` | 엔진 | 판정 엔진 (Streamlit을 import하지 않음) |
| `engine/schemas.py` | 엔진 | **팀 공용 스키마** Profile / Policy / Result (변경은 팀장 승인) |
| `streamlit_app.py`, `app/` | 앱 | 화면 |
| `data/mock/mock_results.json` | 앱 | 엔진 완성 전까지 쓰는 가짜 판정 결과 |
| `data/policies/` | 데이터 | 정책 1건 = JSON 1파일 (파일 이름 = policy_id) |
| `data/reference/` | 데이터 | 기준중위소득표, 중복수혜 관계 |
| `scripts/validate.py` | 데이터 | 정책 파일 검증 (통과한 것만 커밋) |
| `tests/` | 전원 | 테스트 |

## 처음 설정 (한 번만)

```bash
git clone https://github.com/<계정>/youth-policy-parser.git
cd youth-policy-parser
uv sync                 # 가상환경 + 패키지 설치
```

## 자주 쓰는 명령

```bash
uv run streamlit run streamlit_app.py   # 화면 실행 (브라우저가 열림)
uv run pytest                           # 테스트
uv run python scripts/validate.py       # 정책 데이터 검증
uv run ruff check . && uv run ruff format .   # 코드 정리
```

## 규칙

- 작업은 브랜치에서, `main`에는 PR로만 합칩니다. `main`에 합치면 자동 배포됩니다.
- API 키는 `.env` 또는 `.streamlit/secrets.toml`에만 넣습니다. **절대 커밋하지 않습니다.**
- 자격요건 원문은 요약하지 않고 그대로 보관합니다.
