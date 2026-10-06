"""DSL의 추상 구문 트리(AST) 노드.

파서는 문자열을 이 노드들로 바꾸고, 평가기(2주차)는 이 노드들을 프로필과 비교한다.
모든 노드는 불변(frozen)이라 비교(==)와 해시가 가능하다. 테스트에서 "파싱 → 다시 문자열 → 파싱"
결과가 같은지(왕복 일치) 확인하는 데 쓴다.

각 조건 노드는 CATEGORY(8종 조건 유형)를 가진다. 탈락 사유 설명, 반사실 가이드("바꿀 수 있는
조건인가?"), 데이터 품질 집계(유형별 파싱 비율)에 모두 이 분류를 사용한다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Category(StrEnum):
    """정책 조건 유형 8종."""

    AGE = "연령"
    INCOME = "소득"
    REGION = "거주"
    EDUCATION = "학력"
    EMPLOYMENT = "취업상태"
    PERIOD = "기간"
    DUPLICATE = "중복수혜"
    OTHER = "기타"


class Comp(StrEnum):
    LE = "<="
    GE = ">="
    EQ = "=="
    LT = "<"
    GT = ">"

    def check(self, left: float, right: float) -> bool:
        """비교 연산 실행. (평가기에서 사용)"""
        return {
            Comp.LE: left <= right,
            Comp.GE: left >= right,
            Comp.EQ: left == right,
            Comp.LT: left < right,
            Comp.GT: left > right,
        }[self]


def _q(text: str) -> str:
    """문자열을 DSL 따옴표 문자열로 만든다. (한글은 그대로, 특수문자만 이스케이프)"""
    return json.dumps(text, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 논리 조합 노드
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class And:
    children: tuple[Node, ...]

    def to_dsl(self) -> str:
        return " AND ".join(_wrap(c, And) for c in self.children)


@dataclass(frozen=True)
class Or:
    children: tuple[Node, ...]

    def to_dsl(self) -> str:
        return " OR ".join(_wrap(c, Or) for c in self.children)


@dataclass(frozen=True)
class Not:
    child: Node

    def to_dsl(self) -> str:
        inner = self.child.to_dsl()
        return f"NOT {inner}" if not isinstance(self.child, (And, Or)) else f"NOT ({inner})"


def _wrap(child: Node, parent: type) -> str:
    """우선순위가 낮은 자식(AND 안의 OR)만 괄호로 감싼다."""
    text = child.to_dsl()
    if parent is And and isinstance(child, Or):
        return f"({text})"
    return text


# ---------------------------------------------------------------------------
# 조건(술어) 노드 8종
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Age:
    min_age: int | None
    max_age: int | None
    CATEGORY = Category.AGE

    def to_dsl(self) -> str:
        lo = "" if self.min_age is None else str(self.min_age)
        hi = "" if self.max_age is None else str(self.max_age)
        return f"age({lo}..{hi})"


@dataclass(frozen=True)
class Born:
    start: date | None
    end: date | None
    CATEGORY = Category.AGE

    def to_dsl(self) -> str:
        lo = "" if self.start is None else self.start.isoformat()
        hi = "" if self.end is None else self.end.isoformat()
        return f"born({lo}..{hi})"


@dataclass(frozen=True)
class Region:
    sido: str
    sigungu: str | None = None
    CATEGORY = Category.REGION

    def to_dsl(self) -> str:
        if self.sigungu is None:
            return f"region({_q(self.sido)})"
        return f"region({_q(self.sido)}, {_q(self.sigungu)})"


@dataclass(frozen=True)
class Residence:
    comp: Comp
    months: int
    CATEGORY = Category.PERIOD

    def to_dsl(self) -> str:
        return f"residence_months {self.comp} {self.months}"


@dataclass(frozen=True)
class IncomePct:
    scope: str  # "personal" | "household"
    comp: Comp
    pct: int
    CATEGORY = Category.INCOME

    def to_dsl(self) -> str:
        return f"income_pct({self.scope}) {self.comp} {self.pct}"


@dataclass(frozen=True)
class IncomeAbs:
    scope: str
    comp: Comp
    won: int
    CATEGORY = Category.INCOME

    def to_dsl(self) -> str:
        return f"income({self.scope}) {self.comp} {self.won}"


@dataclass(frozen=True)
class InSet:
    field: str  # "education" | "employment"
    values: tuple[str, ...]

    @property
    def CATEGORY(self) -> Category:  # noqa: N802 (다른 노드와 같은 이름으로 접근하기 위함)
        return Category.EDUCATION if self.field == "education" else Category.EMPLOYMENT

    def to_dsl(self) -> str:
        return f"{self.field} in [{', '.join(_q(v) for v in self.values)}]"


@dataclass(frozen=True)
class Receiving:
    benefit: str
    CATEGORY = Category.DUPLICATE

    def to_dsl(self) -> str:
        return f"receiving({_q(self.benefit)})"


@dataclass(frozen=True)
class Manual:
    text: str
    CATEGORY = Category.OTHER

    def to_dsl(self) -> str:
        return f"manual({_q(self.text)})"


Predicate = Age | Born | Region | Residence | IncomePct | IncomeAbs | InSet | Receiving | Manual
Node = And | Or | Not | Predicate


def iter_predicates(node: Node):
    """트리 안의 모든 조건 노드를 순서대로 돌려준다. (유형별 집계, 반사실 후보 찾기에 사용)"""
    if isinstance(node, (And, Or)):
        for c in node.children:
            yield from iter_predicates(c)
    elif isinstance(node, Not):
        yield from iter_predicates(node.child)
    else:
        yield node
