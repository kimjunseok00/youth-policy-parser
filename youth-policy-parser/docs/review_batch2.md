# 검수 체크리스트 — batch2

온통청년 API 본문을 읽고 조건식과 금액을 채운 **2차 출처** 정책입니다. 아래 항목을 공식 페이지에서 확인한 뒤
`data/curation/batch2.json`의 `review`를 비우고 `scripts/promote.py`로 승격합니다. 확인 못 한 정책은 승격하지 않습니다.

| 정책 | 공식 페이지 | 확인할 항목 |
| --- | --- | --- |
| 부산 청년 신용회복 지원 | https://young.busan.go.kr/index.nm?menuCd=54 | · 연체예방비용 지원 금액·한도 (부산신용보증재단)<br>· 재무상담·경제교육의 별도 소득·신용 요건 유무<br>· 채무조정 지원의 대상 채무 범위 |
| 부산 청년문화육성 지원 | https://young.busan.go.kr/index.nm?menuCd=235 | · 사업별 공모 일정·지원 금액 (부산문화재단 공고)<br>· 신청 자격이 예술가로 한정되는 사업과 일반 청년 참여 사업의 구분<br>· '부산 청년'의 거주 요건 |
| 청년 주택드림 디딤돌 대출 | https://enhuf.molit.go.kr<br>https://nhuf.molit.go.kr/FP/FP05/FP0503/FP05030901.jsp | · 연소득 7,000만 원이 부부합산인지 본인인지<br>· 신혼 가구의 소득 기준<br>· 금리·한도 최신 값 (nhuf.molit.go.kr)<br>· 기존 정책 '청년 주택드림 청약통장'과 함께 보여줄지 |
| 청년전용 저리대출상품 운영 | https://enhuf.molit.go.kr/<br>https://nhuf.molit.go.kr/FP/FP05/FP0502/FP05020301.jsp | · 무주택·세대주·순자산 요건 (API 본문에 없음 → nhuf.molit.go.kr)<br>· 부부합산 소득 기준 여부<br>· 임차보증금 상한 |
| 청년전용 보증부 월세대출 | http://nhuf.molit.go.kr/FP/FP05/FP0502/FP05020701.jsp<br>https://nhuf.molit.go.kr/FP/FP05/FP0502/FP05020701.jsp | · 무주택·세대주·순자산 요건 (API 본문에 없음 → nhuf.molit.go.kr)<br>· 부부합산 소득 기준 여부<br>· 기존 '청년월세 지원'(월세 한시 지원)과 중복 수혜 가능 여부 |
| 청년 전월세 대출보증 | www.hf.go.kr | · 상세 조건은 시중은행·한국주택금융공사에서 확인하라고만 안내됨 (hf.go.kr)<br>· 대출 상품(버팀목·월세대출 등)과의 관계 |
| 청년 국가기술자격 응시료 지원 사업 | https://www.q-net.or.kr/man001.do?gSite=Q&gIntro=Y<br>https://www.q-net.or.kr/man004.do?id=man00402&gSite=Q&gId= | · 내년(2027년) 기준 출생연도 — 해마다 달라짐<br>· 연 3회 한도와 예산 소진 여부 (q-net.or.kr)<br>· 응시료 50% 금액 예시를 넣을지 |
| 청년 자금지원을 위한 햇살론유스 운영 | https://www.kinfa.or.kr/financialProduct/hessalLoanYoos.do | · 대상 유형(대학(원)생·미취업·중소기업 재직 등)과 대출 한도·금리 (kinfa.or.kr)<br>· 연소득 3,500만 원 기준이 총급여인지 |
| 청년 미래이음 대출 | https://www.kinfa.or.kr | · '미소금융 청년 미래이음 대출'(서민금융진흥원, 별도 항목)과 같은 상품인지<br>· 취·창업 1년 이내의 기준<br>· 신용평점·근로장려금 요건 확인 방법 (kinfa.or.kr) |
| K-패스 (청년 30% 환급) | https://www.gov.kr/portal/rcvfvrSvc/dtlEx/161300000104 | · 부산 지역 추가 혜택(동백패스 등)을 따로 넣을지<br>· 청년 연령에 군 복무 연장이 있는지<br>· K-패스 카드 발급·회원가입 안내 (korea-pass.kr) |
