# 배포·운영 가이드

되나요는 세 곳에 무료로 배포됩니다.

| 무엇 | 어디 | 주소 | 갱신 방법 |
| --- | --- | --- | --- |
| 판정 앱 | Streamlit Community Cloud | `app/branding.py`의 `APP_URL` | `main`에 머지하면 자동 |
| 서비스 소개·약관 | GitHub Pages | `https://<계정>.github.io/youth-policy-parser` | `site/`가 바뀐 채 `main`에 머지하면 자동 |
| 익명 통계 저장소 (선택) | Supabase 무료 플랜 | Supabase 대시보드 | 설정 후 자동 |

---

## 1. 처음 한 번만 하는 설정

### 1-1. GitHub Pages 켜기 (서비스 소개 사이트)

1. GitHub 저장소 → **Settings → Pages**
2. **Source**를 **GitHub Actions**로 선택
3. **Actions** 탭에서 `Pages` 워크플로가 ✅가 되면 주소가 열립니다 (첫 배포는 `main`에 `site/` 변경이 들어가거나, Actions에서 수동 실행).

### 1-2. 앱 주소를 보기 좋게 바꾸기 (선택)

1. Streamlit Cloud → 앱 오른쪽 **⋮ → Settings → General → Custom subdomain**
2. 예: `doenayo` → `https://doenayo.streamlit.app`
3. 바꿨다면 아래 두 곳의 주소도 같이 바꿉니다.
   - `youth-policy-parser/app/branding.py`의 `APP_URL`
   - `site/index.html`의 `data-app` 링크 2개

### 1-3. Python 버전 확인

Streamlit Cloud → 앱 **Settings → General → Python version**이 **3.12**인지 확인합니다. (다르면 앱을 삭제 후 재배포할 때 3.12 선택)

### 1-4. 익명 통계 켜기 (선택)

통계 수집을 켜지 않아도 서비스는 그대로 동작합니다. 지자체 리포트는 가상 인구로 시연됩니다.

1. [supabase.com](https://supabase.com)에서 무료 프로젝트 생성 (지역: Northeast Asia (Seoul) 권장)
2. **SQL Editor**에서 [`docs/supabase.sql`](supabase.sql) 실행 → `events` 테이블과 '쓰기만 허용' 정책이 생깁니다
3. **Project Settings → API Keys**에서 **Publishable key**와 **Secret key** 복사
4. Streamlit Cloud → 앱 **Settings → Secrets**에 아래를 붙여 넣고 저장

   ```toml
   [telemetry]
   supabase_url = "https://<프로젝트 ID>.supabase.co"
   insert_key = "sb_publishable_..."
   read_key = "sb_secret_..."
   table = "events"
   ```

5. 앱이 재시작되면 입력 화면에 **"익명 통계 제공에 동의합니다 (선택)"** 체크박스가 나타납니다.
6. 동의한 판정이 5건 이상 쌓이면 지자체 리포트에서 **실사용 익명 통계**를 고를 수 있습니다.

> Secret key는 행 수준 보안(RLS)을 우회하는 관리자 키입니다. **Streamlit Secrets에만** 넣고, 코드·채팅·문서에 붙여넣지 마세요.

### 1-5. 개인정보처리방침의 빈칸 채우기

`site/privacy.html`의 **10. 개인정보 보호책임자** 표에서 `[팀장 이름]`, `[대표 이메일]`을 채웁니다. 실제 사용자를 받기 전에 법률 검토를 한 번 받는 것을 권합니다.

---

## 2. 평소 작업 흐름

```bash
git switch main && git pull
git switch -c feat/무엇을-하는지
# … 작업 …
cd youth-policy-parser
uv run ruff check . && uv run ruff format .
uv run python scripts/validate.py
uv run pytest
git add -A && git commit -m "..." && git push -u origin HEAD
```

GitHub에서 PR을 만들고 **CI ✅**를 확인한 뒤 머지합니다. 머지하면 앱과 사이트가 자동으로 갱신됩니다.

## 3. 정책 데이터 갱신

1. `docs/data_check.md` 순서로 공식 공고문과 대조
2. `data/policies/<policy_id>.json` 수정 또는 추가 (`prompts/convert.md` 프롬프트 활용)
3. `uv run python scripts/validate.py` → 실패 0건
4. 판정이 바뀌었다면 원문을 확인한 뒤 `tests/regression/persona_expected.json` 갱신
5. 금액·기간이 바뀐 정책은 `site/index.html`의 정책 수 문구도 확인

## 4. 문제가 생겼을 때

| 증상 | 확인할 곳 | 조치 |
| --- | --- | --- |
| 앱이 에러 화면 | Streamlit Cloud → **Manage app → 로그** | 마지막 에러 줄 확인 → 고친 뒤 머지, 급하면 **Reboot app** |
| 새 버전이 반영 안 됨 | 앱 로그의 마지막 배포 시각 | **⋮ → Reboot app** |
| 바로 전 버전으로 되돌리기 | GitHub 해당 PR | **Revert** 버튼 → 새 PR 머지 |
| CI ❌ | PR의 **Checks → 실패한 단계** | 로컬에서 같은 명령(`ruff`, `validate.py`, `pytest`)으로 재현 |
| 사이트 404 | Settings → Pages가 GitHub Actions인지 | Actions에서 `Pages` 워크플로 수동 실행 |
| 동의 체크박스가 안 보임 | 앱 Settings → Secrets | `[telemetry]` 블록과 키 이름 확인 |

## 5. 발표 전날 점검

- [ ] 앱 주소 접속 → 예시 인물 6명 각각 판정까지 눌러 보기 (첫 접속은 잠든 앱이 깨어나는 데 1~2분)
- [ ] 지자체 리포트 → 시뮬레이터 슬라이더 움직여 보기
- [ ] 서비스 소개 사이트 → "내 자격 확인하기" 버튼이 앱으로 연결되는지
- [ ] 개인정보처리방침 빈칸 채웠는지
- [ ] 정책 데이터 공식 공고문 대조 (`docs/data_check.md`)
