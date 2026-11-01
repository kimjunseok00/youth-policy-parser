# CLAUDE.md — 되나요 프로젝트 인수인계

Claude Cowork 대화(2026-10-01 ~ 10-13)에서 진행한 내용을 Claude Code가 이어받기 위한 문서다.
코드가 사실의 기준이고, 이 문서는 "왜 그렇게 했는지"와 "다음에 할 일"을 담는다.

## 사용자·팀

- 팀장 준석(엔진 담당, 부산 거주). 팀 3명: 엔진·팀장 / 데이터 / 앱·발표. 동아대 SW창업 수업 프로젝트.
- 답변 규칙: **항상 한국어**, 인사·뻔한 설명 없이 본론부터, 모호하면 추측하지 말고 되묻기.
- 개발 규칙: 코드 전에 작업 계획과 구조를 먼저 설명, 최신 모범 사례, 의도를 설명하는 주석,
  검증되지 않은 가정으로 코드를 짜지 않기, 확실하지 않은 기술 사항은 최신 문서 확인.
- 기획·글 요청: 바로 쓰지 말고 3가지 이상 방향을 먼저 제시하고 고르게 한다.
- 사용자는 git 초보다. 명령은 복사해서 그대로 실행할 수 있게, 위험한 명령(rm, rsync --delete)은 실행 위치를 먼저 확인시킨다.

## 서비스

**되나요** — "청년정책, 나도 되나요?" 청년정책 자격요건(자연어)을 조건식(DSL)으로 바꿔
프로필을 넣으면 정책마다 충족 / 불충족 / 확인 필요와 그 이유를 알려준다.

| 대상 | 화면 | 배포 |
| --- | --- | --- |
| 청년 | 모바일 앱 PWA (`youth-policy-parser/pwa/`), 엔진을 브라우저 안 Pyodide로 실행 | GitHub Pages `/app/` |
| 지자체 | Streamlit 웹 (리포트·조건 완화 시뮬레이터·PC용 판정) | Streamlit Community Cloud |
| 홍보 | 소개·개인정보처리방침·약관 (`site/`) | GitHub Pages |

수익 모델(발표용): 청년 무료 → 동의한 익명 통계로 지자체 리포트 구독(B2G, 주력) → 판정 엔진 API(B2B, 확장).

## 저장소 구조 (이 폴더가 저장소 루트)

```
site/                     소개 사이트 (정적 HTML)
.github/workflows/        ci.yml(ruff·validate·pytest), pages.yml(site + PWA 빌드 배포)
youth-policy-parser/
  engine/                 판정 엔진 (Streamlit import 금지 — 브라우저에서도 돌아야 함)
    grammar.lark          DSL 문법 = BNF 설계 문서
    evaluator.py          3값 판정 + 사유 트리, manual("※ ...")은 참고 안내문(판정 중립)
    service.py            웹·앱 공용 입구 judge_json()/meta_json()
    counterfactual.py · timeline.py · optimizer.py · report.py · anonymize.py
  app/                    Streamlit 화면 (page_check / page_report / page_about)
  pwa/                    청년용 앱 원본, scripts/build_app.py가 pwa/dist/로 빌드
  ingest/ontong.py        온통청년 API 응답 → 검수용 초안
  scripts/                validate.py, collect.py, promote.py, build_app.py, check_api.py
  data/policies/          정식 정책 (1건 = JSON 1개, 현재 36건)
  data/drafts/            API 수집 초안 (검수 전, 앱에 안 나옴)
  docs/                   dsl_spec, data_check(검수 체크리스트), deploy, app, collect
  tests/                  pytest (페르소나 회귀 스냅샷 포함)
```

## 명령 (youth-policy-parser 폴더에서)

```bash
uv sync
uv run ruff check . && uv run ruff format .
uv run python scripts/validate.py           # 정책 데이터 검증
uv run pytest -q                            # 맥(M 칩)에서는 PuLP 테스트 1개 skip이 정상
uv run streamlit run streamlit_app.py
uv run python scripts/build_app.py && (cd pwa/dist && python -m http.server 8000)   # 앱, ?as_of=2026-10-13
uv run --env-file .env python scripts/collect.py --inspect                         # 온통청년 응답 구조 확인
```

## 지켜야 할 결정

- **디자인 A안 '행정 문서형'**: 남색 `#1F3A5F` 하나만 강조색, 거의 각진 모서리, Pretendard.
  **이모티콘 금지** — 상태는 글자 배지(충족·불충족·확인 필요·참고). `tests/test_app.py`가 앱 코드의 이모티콘을 막는다.
  색 값은 `.streamlit/config.toml`(루트와 youth-policy-parser 두 곳), `site/style.css`, `pwa/style.css`가 같아야 한다.
- 판정 규칙은 한 벌만: 웹과 앱 모두 `engine/`을 쓴다. 자바스크립트로 다시 구현하지 않는다.
- 자동 판정할 수 없는 조건은 `manual("...")` → '확인 필요'. 억지로 판정하지 않는다.
  `manual("※ ...")`는 조건이 아니라 참고 문구(판정 중립, 화면에 '참고'로 표시).
- 정책 데이터는 출처 URL 필수. 2차 출처(언론 등)는 공고문 대조 전까지 그렇다고 표시한다. 금액·조건을 지어내지 않는다.
- 판정이 바뀌면 원문을 확인한 뒤 `tests/regression/persona_expected.json`을 갱신한다.
- 지자체 리포트의 가상 인구는 시연용이며 화면에 항상 '가상'이라고 표시한다. 실통계는 동의한 익명 요약만, 5명 미만 집단은 숨긴다.

## 보안

- API 키·Supabase secret을 코드·채팅·문서에 넣지 않는다. `.env`, `.streamlit/secrets.toml`은 커밋 금지(.gitignore).
- 키를 출력하는 스크립트는 앞 4자리만 보이게 가린다 (`mask()`).

## 외부 정보 (검증 상태 포함)

- 온통청년 청년정책 API: `https://www.youthcenter.go.kr/go/ythip/getPlcy`, 키 파라미터 `apiKeyNm`,
  `pageNum`·`pageSize`·`rtnType=json`. 다른 공개 프로젝트 코드에서 확인한 값이며 **JSON 구조는 실제 호출로 아직 미확인**.
  키는 청년정책API용(청년센터API·청년콘텐츠API 키와 다름). 유효기간 2026-10-12 ~ 2027-10-12.
- 2026 기준중위소득: 보건복지부고시 제2025-135호 (`data/reference/median_income_2026.json`).

## 현재 상태 (2026-10-13)

- `main`: v1.0.0. 브랜치 `release/v1.1.0`에 v1.1(PWA·디자인·리포트 수정) + v1.2(수집기) 작업 중, 아직 머지 전.
- 바로 전에 안내한 정리: 이 폴더 안의 옛 `ypp/` 하위 저장소가 브랜치에 링크로 커밋되어 있어
  `git rm --cached ypp` 후 폴더를 밖으로 옮기고 커밋·push → PR → CI 성공 후 머지하기로 함.

## 다음 할 일

1. `collect.py --inspect`로 온통청년 실제 응답 확인 → 0건이면 `ingest/ontong.py`를 실제 구조에 맞게 수정
2. 수집 → 초안 검수 → `promote.py`로 정책 13건 → 36건 (완료: 온통청년 API 후보 22건 중 15건을 공식 사이트와 대조해 반영, 7건 보류·제외. `docs/data_sources.md` 참조)
3. 9건 공식 출처 대조는 2026-10-13에 반영함 (`docs/data_sources.md`). 표의 '아직 확인 못 한 것'과 공식 URL 직접 확인이 남음
4. 머지 후 Pages 배포 확인, 휴대폰에서 앱 설치 확인, 발표 전날 `docs/deploy.md` 점검표
5. `site/privacy.html` 개인정보 보호책임자 빈칸 채우기
6. 발표: 1주 이내. 시연 순서는 소개 사이트 → 앱(예시 인물 판정·상세·더 받기) → 지자체 리포트 시뮬레이터
