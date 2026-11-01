# 검수 체크리스트 — 배치 1 (부산 10건)

온통청년 API 본문을 읽고 조건식과 금액을 채운 **2차 출처** 정책입니다. 아래 항목을 공식 페이지에서 확인한 뒤
`data/curation/batch1.json`의 `review`를 비우고 `scripts/promote.py`로 승격합니다. 확인 못 한 정책은 승격하지 않습니다.

| 정책 | 공식 페이지 | 확인할 항목 |
| --- | --- | --- |
| 부산 청년 중개보수 및 이사비 지원 | https://young.busan.go.kr/index.nm<br>https://young.busan.go.kr/index.nm?menuCd=271 | · 신청 8/1~12/31 확인 (young.busan.go.kr)<br>· 소득 120%의 가구 범위(본인/가구)<br>· '일하는 청년' 요건의 정확한 범위(재직·자영업 등)<br>· '유사사업'이 어떤 사업인지(청년월세 등) |
| 부산 청년 맞춤형 민간임대주택 공급(희망더함주택) | https://www.busan.go.kr/depart/dreamhouse | · 별표1의 소득·자산 기준을 읽고 manual을 조건식으로 나눌 수 있는지<br>· 입주 지역 요건(부산 거주자 우선 등)<br>· 신청 가능한 단지가 지금 있는지 (민간사업자 모집공고) |
| 부산 평생함께 청년모두가 주거비 지원사업 | https://plus.gov.kr/<br>https://www.busan.go.kr/depart/house0204 | · 소득 기준(도시근로자 월평균 소득 100%)의 올해 금액표<br>· 모집 시기: 상시인지 연 1회인지 (정부24)<br>· 청년 하한 연령 18세/19세 (API 18, 본문 19) |
| 부산 전세보증금 반환보증 보증료 지원 | https://www.busan.go.kr/depart/reguarantee01<br>www.khug.or.kr/jeonse/index.js | · 연소득 5천/6천/7.5천만 원의 기준 연도(근로소득 총급여인지)<br>· 예산 소진 여부 — 접수 중인지 구·군청에 확인 (khug.or.kr, busan.go.kr/depart/reguarantee01)<br>· 신혼부부 보증료 할인 가입자 예외 문구 |
| 부산 행복주택 및 통합공공임대주택 | https://young.busan.go.kr/dwjob/list.nm?menuCd=223 | · 모집공고별 소득·자산 기준(본문은 '본문 참고')<br>· 부산 거주 요건 여부<br>· 현재 모집 중인 단지 |
| 부산 신혼부부 럭키7하우스 지원사업 | https://www.busan.go.kr/depart/house0203<br>plus.gov.kr | · 혼인 기간(7년 이내인지)과 연령 제한 (API는 18~39, 평생함께 사업은 신혼부부 연령 무관)<br>· 공급 호수 300호 소진 여부와 2026년 이후 지속 여부<br>· 월임대료 지원 금액 상한 (정부24 '신혼부부 럭키7하우스 지원 신청') |
| 부산청년 취업성공풀(Full) 패키지 지원 | https://busanjob.net | · 학력 요건(API schoolCd 기준 고졸·대졸 등)을 원문으로 확인 — 초안에서는 뺌<br>· 100만 원이 청년 본인에게 지급되는 몫인지, 기업 몫이 섞였는지<br>· busanjob.net 참여 방법·모집 시기 |
| 부산 지역인재 장학금 지원 | https://young.busan.go.kr/index.nm?menuCd=164 | · IT·상경 분야에 해당하는 학과 범위<br>· 학업 성적·소득 등 선발 기준(API에 없음)<br>· 거주지 요건 여부 — 초안은 부산 거주를 요구하지 않음<br>· 신청 시기 (young.busan.go.kr) |
| 부산 취업연수생 고용사업 | https://busanjob.net/yjob/view.do?no=1118<br>https://young.busan.go.kr/index.nm?menuCd=161 | · 연수 급여(월 금액·기간)<br>· 거주 요건: 부산 주민등록 여부<br>· 모집 시기와 선발 방식 (청년부산잡스) |
| 부산 청년 생활인구 유입 활성화(부산온나청년패스) | https://young.busan.go.kr/index.nm?menuCd=269 | · 제휴시설 목록과 할인율<br>· 발급 방식·유효 기간 |
