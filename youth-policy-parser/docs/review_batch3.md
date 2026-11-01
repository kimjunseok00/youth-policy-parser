# 검수 체크리스트 — batch3

온통청년 API 본문을 읽고 조건식과 금액을 채운 **2차 출처** 정책입니다. 아래 항목을 공식 페이지에서 확인한 뒤
`data/curation/batch3.json`의 `review`를 비우고 `scripts/promote.py`로 승격합니다. 확인 못 한 정책은 승격하지 않습니다.

| 정책 | 공식 페이지 | 확인할 항목 |
| --- | --- | --- |
| 청년특화주택 공급 | https://www.myhome.go.kr/hws/portal/main/getMgtMainPage.do | · 소득 기준 150%+20%p의 적용 대상(1인 가구 본인)과 비율 170% 해석<br>· 모집 중인 단지·지역 (myhome.go.kr)<br>· 대학생 신청 시 별도 소득 기준 여부 |
| 기숙사형 청년주택 공급 | https://www.myhome.go.kr/hws/portal/main/getMgtMainYhsPage.do | · '월평균 소득 100%'가 도시근로자 월평균 소득인지 기준중위소득인지 — 불명확해서 manual로 둠<br>· 순위는 우선순위인지 자격 한계인지<br>· 현재 모집 단지 (myhome.go.kr) |
| (문체부) 청년예술인 예술활동 적립계좌 | https://www.artloan.kr/notice/savingsAccount.do<br>https://www.artloan.kr/notice/savingsAccountProcess.do | · 3,692만 원이 어떤 소득(종합소득 소득금액 합계)인지와 올해 기준값<br>· 신청 기간 — API는 상시지만 공지 기간 내 신청 (artloan.kr)<br>· 이전 회차 참여자 재신청 가능 여부 |
| 청년미래플러스 | https://hrdkorea.or.kr | · 운영기관 7곳과 모집 일정 (hrdkorea.or.kr 공지)<br>· 군 복무 연장의 정확한 산식 (최고 39세)<br>· 재직청년 프로그램의 재학 제한 여부 |
| k-뉴딜 아카데미 | https://www.work24.go.kr/cm/c/f/1100/selecSystInfo.do?currentPageNo=1&recordCountPerPage=10&systId=SI00000512&systClId=SC00000391 | · 고용24에서 개설된 아카데미 목록과 기업별 모집 기간<br>· 휴학생 참여 요건 (졸업예정자 외 장기휴학 증명)<br>· 신청 기간 2026-07-07~2026-12-31 은 사업 기간인지 접수 기간인지 |
| 청년도약 인재양성 부트캠프 | https://www.nais.or.kr/<br>https://www.nais.or.kr/member/login | · '비재학생'에 휴학생이 포함되는지 (nais.or.kr)<br>· 대학별 모집 일정과 지원 내용(수당 유무)<br>· 신청 기간 2026-07-07~2028-02-29 의 의미(사업 기간 추정) |
| 중앙행정기관 청년인턴 운영 | https://www.2030db.go.kr/user/youthIntern/selectYouthInternList.do | · 인턴 급여·기간 (2030db.go.kr 모집공고)<br>· 재학생·졸업예정자 참여 가능 여부<br>· 군 복무 연장 여부 |
| 취업 후 상환 학자금대출_생활비대출 | https://www.kosaf.go.kr/ko/tuition.do?pg=tuition04_01_01<br>https://www.kosaf.go.kr/ko/tuition.do?pg=tuition04_01_01&ttab1=2 | · 신청 기간 2026-07-01~2026-11-17 (2학기) — 지금 접수 중인지 (kosaf.go.kr)<br>· 선취업 후학습자 연령(만 45세) 반영 방식<br>· 휴학생 대출 가능 여부 |
| 취업 후 상환 학자금대출_등록금대출 | https://www.kosaf.go.kr/ko/tuition.do?pg=tuition04_01_01<br>https://www.kosaf.go.kr/ko/tuition.do?pg=tuition04_01_01&ttab1=2 | · 신청 기간 2026-07-01~2026-11-17 (2학기) — 지금 접수 중인지 (kosaf.go.kr)<br>· 등록금 대출의 소득·성적 요건(API에 소득 기준 없음)<br>· 휴학생 대출 가능 여부 |
| 청년 특례 채무조정 | https://www.ccrs.or.kr/cms/com/index.do?MENU_ID=1940 | · 소득 요건(최저생계비 이상 등) 문구의 정확한 의미 (ccrs.or.kr)<br>· 재직 중인 청년의 이용 가능 여부 (원문은 대학생·미취업 청년)<br>· API 하한 연령 19세 vs 본문 '만 34세 이하' |
