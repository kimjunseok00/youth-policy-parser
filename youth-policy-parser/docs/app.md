# 청년용 앱 (PWA)

청년은 휴대폰 앱, 지자체는 PC 웹(Streamlit)을 쓰는 구성입니다. 판정 엔진은 하나이고 두 화면이 같이 씁니다.

```
                 engine/  (판정 엔진, Python — 한 벌만 유지)
                    │
     ┌──────────────┴───────────────┐
     │                              │
 engine/service.py              app/  (Streamlit)
 judge_json() / meta_json()      지자체 리포트 · 시뮬레이터 · PC용 판정
     │                              │
 pwa/  (청년용 앱)               Streamlit Community Cloud
 브라우저 안의 Python(Pyodide)이
 엔진을 직접 실행
     │
 GitHub Pages  …/youth-policy-parser/app/
```

## 왜 이렇게 만들었나

| 결정 | 이유 |
| --- | --- |
| 별도 API 서버를 두지 않음 | 무료 서버(Render 등)는 잠들었다 깨는 데 30~60초가 걸려 시연 중 멈출 위험이 있다 |
| 엔진을 자바스크립트로 다시 짜지 않음 | 판정 규칙이 두 벌이 되면 웹과 앱 결과가 어긋난다. 같은 Python 코드를 브라우저에서 돌린다 |
| Pyodide를 CDN이 아니라 같이 배포 | 외부 서비스가 막혀도 동작하고, 서비스 워커가 저장해 오프라인에서도 열린다 |
| 입력값을 서버로 보내지 않음 | 생년월일·소득은 민감 정보. 기기 안에서만 계산한다 (지자체 대상 발표의 강점) |

알려진 단점: 첫 실행에 엔진(약 15MB, 압축 전송 시 더 작음)을 받느라 3~6초 걸린다. 두 번째부터는 저장된 파일로 1초 안에 열린다.

## 파일

| 파일 | 하는 일 |
| --- | --- |
| `pwa/index.html` | 화면 뼈대 (상단 바, 탭 4개, 하단 탭 바, 정책 상세 시트) |
| `pwa/app.js` | 화면 그리기, 입력 기억(이 기기에만), 엔진 호출 |
| `pwa/worker.js` | Pyodide를 열고 `engine.service`를 불러오는 작업 스레드 |
| `pwa/sw.js` | 서비스 워커: 앱 파일을 기기에 저장 (오프라인 실행) |
| `pwa/style.css` | A안 '행정 문서형' 색·배지 (웹·소개 사이트와 같은 값) |
| `pwa/manifest.webmanifest`, `pwa/icons/` | 홈 화면 아이콘·이름 |
| `scripts/build_app.py` | 위 파일 + `engine.zip`(엔진·데이터·lark) + Pyodide 필요한 파일만 → `pwa/dist/` |

## 내 컴퓨터에서 실행

```bash
cd youth-policy-parser
uv run python scripts/build_app.py          # 처음 한 번 Pyodide(약 330MB)를 받아 캐시에 둔다
cd pwa/dist && python -m http.server 8000   # http://localhost:8000
```

- 반드시 `localhost`로 열어야 서비스 워커와 작업 스레드가 동작한다 (파일을 더블클릭해서 열면 안 됨).
- 시연 날짜를 고정하려면 주소 뒤에 `?as_of=2026-10-12`를 붙인다.
- 엔진(`engine/`)이나 정책 데이터(`data/`)를 고쳤다면 `build_app.py`를 다시 실행한다.

## 배포

`main`에 머지하면 `.github/workflows/pages.yml`이 소개 사이트(`site/`)와 앱을 함께 묶어 GitHub Pages에 올린다.

- 앱 주소: `https://<계정>.github.io/youth-policy-parser/app/`
- 엔진 해시가 바뀌면 서비스 워커 캐시 이름이 바뀌어, 사용자 기기도 새 데이터를 받는다.

## 휴대폰에 설치

- 아이폰: Safari로 앱 주소 열기 → 공유 → **홈 화면에 추가**
- 안드로이드: Chrome으로 앱 주소 열기 → 메뉴 → **앱 설치**

## 검증 방법

| 무엇 | 어떻게 |
| --- | --- |
| 엔진 입구 | `tests/test_service.py` (CI에서 자동) — 예시 인물 6명 판정이 엔진과 같은지, 오류가 문장으로 오는지 |
| 브라우저 안 결과가 서버와 같은지 | 개발 중 Node + Pyodide로 6명 전체 결과를 비교해 일치 확인. 차이는 최적 조합 '계산 방법' 표시뿐 (브라우저에는 PuLP가 없어 전수 탐색, 결과 금액·선택은 동일) |
| 화면 | 휴대폰 크기(390×844)에서 입력 → 판정 → 확인 질문 → 상세 → 더 받기 → 일정 → 오류 입력 → 오프라인 재실행 |

Pyodide 버전을 올릴 때는 `scripts/build_app.py`의 `PYODIDE_VERSION`을 바꾸고, 위 화면 점검을 다시 한다.
