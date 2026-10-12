"""DSL 파서: 문자열 → AST.

처리 단계
1. 구문 분석 (Lark, LALR): grammar.lark에 맞지 않으면 DSLSyntaxError
2. AST 변환 (Transformer): Lark 트리를 engine.nodes의 불변 객체로 바꾼다
3. 의미 검사: 문법은 맞지만 뜻이 틀린 경우(없는 학력 값, 나이 범위 역전 등) DSLSemanticError

사용:
    from engine.parser import parse
    tree = parse('age(19..34) AND region("부산광역시")')
"""

from __future__ import annotations

import json
from datetime import date
from functools import cache, lru_cache
from pathlib import Path

from lark import Lark, Token, Transformer, v_args
from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedInput, UnexpectedToken

from engine.nodes import (
    Age,
    And,
    Born,
    Comp,
    IncomeAbs,
    IncomePct,
    InSet,
    Manual,
    Node,
    Not,
    Or,
    Receiving,
    Region,
    Residence,
)
from engine.regions import SIDO, SIGUNGU_BY_SIDO
from engine.schemas import Education, Employment

GRAMMAR_PATH = Path(__file__).with_name("grammar.lark")

# in_set에서 허용하는 값: 프로필 스키마의 Enum과 반드시 같아야 판정이 가능하다.
ALLOWED_SET_VALUES: dict[str, set[str]] = {
    "education": {e.value for e in Education},
    "employment": {e.value for e in Employment},
}


class DSLError(ValueError):
    """DSL 관련 오류의 공통 부모. validate.py는 이것 하나만 잡으면 된다."""


class DSLSyntaxError(DSLError):
    """문법에 맞지 않는 문자열."""


class DSLSemanticError(DSLError):
    """문법은 맞지만 의미가 틀린 경우."""


def _unquote(token: Token) -> str:
    # ESCAPED_STRING은 JSON 문자열 규칙과 같으므로 json으로 안전하게 푼다.
    return json.loads(token)


@v_args(inline=True)
class _ToAST(Transformer):
    """Lark 파스 트리를 AST 노드로 바꾸면서 의미 검사를 한다.

    메서드 이름 = grammar.lark의 규칙(또는 별칭) 이름.
    """

    # ---- 논리 조합: 같은 종류가 중첩되면 평평하게 편다 (A AND (B AND C) → A AND B AND C)
    def and_(self, *children: Node) -> And:
        flat: list[Node] = []
        for c in children:
            flat.extend(c.children if isinstance(c, And) else [c])
        return And(tuple(flat))

    def or_(self, *children: Node) -> Or:
        flat: list[Node] = []
        for c in children:
            flat.extend(c.children if isinstance(c, Or) else [c])
        return Or(tuple(flat))

    def not_(self, child: Node) -> Node:
        # NOT NOT X → X (이중 부정 제거)
        return child.child if isinstance(child, Not) else Not(child)

    # ---- 조건 8종
    def age(self, lo: Token | None, hi: Token | None, mil: Token | None) -> Age:
        min_age = int(lo) if lo is not None else None
        max_age = int(hi) if hi is not None else None
        military = int(mil) if mil is not None else 0
        if min_age is None and max_age is None:
            raise DSLSemanticError("age(..)에는 최소 나이나 최대 나이 중 하나가 있어야 합니다.")
        if min_age is not None and max_age is not None and min_age > max_age:
            raise DSLSemanticError(f"age({min_age}..{max_age}): 최소 나이가 최대 나이보다 큽니다.")
        if military and max_age is None:
            raise DSLSemanticError("military=는 연령 상한(..N)이 있을 때만 쓸 수 있습니다.")
        if military > 120:
            raise DSLSemanticError(f"military={military}: 연장은 최대 120개월까지입니다.")
        return Age(min_age, max_age, military)

    def born(self, lo: Token | None, hi: Token | None) -> Born:
        try:
            start = date.fromisoformat(lo) if lo is not None else None
            end = date.fromisoformat(hi) if hi is not None else None
        except ValueError as e:
            raise DSLSemanticError(f"born(): 존재하지 않는 날짜입니다 ({e}).") from e
        if start is None and end is None:
            raise DSLSemanticError("born(..)에는 시작일이나 종료일 중 하나가 있어야 합니다.")
        if start and end and start > end:
            raise DSLSemanticError(f"born({start}..{end}): 시작일이 종료일보다 늦습니다.")
        return Born(start, end)

    def region(self, sido_tok: Token, sigungu_tok: Token | None) -> Region:
        sido = _unquote(sido_tok)
        if sido not in SIDO:
            raise DSLSemanticError(
                f'region("{sido}"): 시·도 이름은 정식 명칭이어야 합니다 (예: "부산광역시").'
            )
        sigungu = _unquote(sigungu_tok) if sigungu_tok is not None else None
        known = SIGUNGU_BY_SIDO.get(sido)
        if sigungu is not None and known is not None and sigungu not in known:
            raise DSLSemanticError(f'region("{sido}", "{sigungu}"): 없는 시·군·구입니다.')
        return Region(sido, sigungu)

    def residence(self, comp: Token, months: Token) -> Residence:
        return Residence(Comp(comp), int(months))

    def income_pct(self, scope: Token, comp: Token, pct: Token) -> IncomePct:
        return IncomePct(str(scope), Comp(comp), int(pct))

    def income_abs(self, scope: Token, comp: Token, won: Token) -> IncomeAbs:
        return IncomeAbs(str(scope), Comp(comp), int(won))

    def in_set(self, field: Token, *values: Token) -> InSet:
        vals = tuple(_unquote(v) for v in values)
        allowed = ALLOWED_SET_VALUES[str(field)]
        unknown = [v for v in vals if v not in allowed]
        if unknown:
            raise DSLSemanticError(f"{field}에 없는 값 {unknown}. 허용 값: {sorted(allowed)}")
        return InSet(str(field), vals)

    def receiving(self, name: Token) -> Receiving:
        return Receiving(_unquote(name))

    def manual(self, text: Token) -> Manual:
        return Manual(_unquote(text))


@cache
def _lark() -> Lark:
    """문법 파일을 한 번만 읽어 파서를 만든다. (LALR: 빠르고, 문법 모호성을 미리 잡아준다)"""
    return Lark(GRAMMAR_PATH.read_text(encoding="utf-8"), parser="lalr", maybe_placeholders=True)


@lru_cache(maxsize=1024)
def parse(text: str) -> Node:
    """DSL 문자열을 AST로 바꾼다. 실패하면 위치와 이유를 담은 DSLError를 던진다.

    AST는 불변 객체라 같은 문자열의 결과를 캐시해도 안전하다 (리포트처럼 수백 번 판정할 때 빠름).
    """
    try:
        tree = _lark().parse(text)
    except UnexpectedInput as e:
        raise DSLSyntaxError(_describe(e, text)) from e
    try:
        return _ToAST().transform(tree)
    except Exception as e:  # Transformer는 내부 예외를 VisitError로 감싼다
        cause = getattr(e, "orig_exc", e)
        if isinstance(cause, DSLError):
            raise cause from None
        raise


def _describe(e: UnexpectedInput, text: str) -> str:
    """사람이 읽을 수 있는 한국어 오류 메시지. 데이터 담당이 고칠 위치를 바로 찾게 한다."""
    context = e.get_context(text, span=30).rstrip()
    ended_early = isinstance(e, UnexpectedEOF) or (
        isinstance(e, UnexpectedToken) and e.token.type == "$END"
    )
    if ended_early:
        reason = "문장이 중간에 끝났습니다 (괄호나 따옴표가 닫히지 않았을 수 있음)"
    elif isinstance(e, UnexpectedCharacters):
        reason = f"'{text[e.pos_in_stream]}' 문자를 이해할 수 없습니다"
    elif isinstance(e, UnexpectedToken):
        expected = ", ".join(sorted(e.expected)[:6])
        reason = f"'{e.token}'이(가) 올 자리가 아닙니다 (기대: {expected})"
    else:
        reason = "문법 오류"
    return f"{e.line}행 {e.column}열: {reason}\n{context}"
