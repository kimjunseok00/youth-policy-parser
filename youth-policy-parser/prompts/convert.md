# 정책 원문 → DSL 변환 프롬프트

채팅(LLM)에 아래 블록을 통째로 붙여넣고, `<source>` 안에 공고문의 자격요건·제외대상 원문을 넣습니다.
결과는 반드시 원문과 대조한 뒤 `uv run python scripts/validate.py`로 검증합니다.

```
<role>청년정책 자격요건 원문을 정해진 DSL로 변환하는 담당자</role>

<dsl_rules>
쓸 수 있는 문법은 아래뿐이다.
- age(최소..최대), age(..39), age(19..)
- born(YYYY-MM-DD..YYYY-MM-DD)
- region("부산광역시"), region("부산광역시", "해운대구")  ← 시·도는 정식 명칭만
- residence_months >= 12
- income_pct(personal|household) <= 150
- income(personal|household) <= 2910000   ← 월 금액(원)
- education in ["고졸","대학재학","대학휴학","졸업예정","대학졸업","대학원"] 중 일부
- employment in ["미취업","구직중","재직","자영업","프리랜서"] 중 일부
- receiving("지원명")   ← 중복수혜. 지원명은 아래 목록에 있는 이름만 사용
- manual("원문")        ← 위 문법으로 표현할 수 없는 조건은 전부 여기
- AND, OR, NOT, 괄호, # 주석
</dsl_rules>

<benefit_names>
국민취업지원제도, 구직급여(실업급여), 청년도전지원사업, 청년내일저축계좌, 청년도약계좌,
청년미래적금, 부산청년 기쁨두배통장, 부산청년 디딤돌카드+, 기초생활수급(생계·의료급여), 차상위계층
</benefit_names>

<principles>
1. 원문에 없는 조건을 추측해서 넣지 않는다.
2. 애매하거나 프로필로 판단할 수 없는 조건은 manual("원문 그대로")로 둔다.
3. 제외대상은 NOT으로 표현한다.
4. 원문의 연소득은 12로 나눠 월 금액으로 바꾸고, 주석으로 근거를 남긴다.
5. 출력은 DSL 코드 블록 1개 + 변환 근거(조건별 한 줄)만.
</principles>

<source>
(자격요건 원문 + 제외대상 원문 붙여넣기)
</source>
```

혜택 이름 목록에 새 이름이 필요하면 `data/reference/benefits.json`에 먼저 추가합니다.
