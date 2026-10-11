"""혜택 이름 사전.

DSL의 receiving("이름")과 프로필의 current_benefits는 '같은 문자열'이어야 판정이 된다.
그래서 이름을 한 곳(data/reference/benefits.json)에서 관리하고,
화면은 이 목록을 선택지로, validate.py는 이 목록으로 데이터를 검사한다.
"""

import json
from pathlib import Path

BENEFITS_PATH = Path(__file__).resolve().parent.parent / "data" / "reference" / "benefits.json"

BENEFIT_NAMES: tuple[str, ...] = tuple(
    json.loads(BENEFITS_PATH.read_text(encoding="utf-8"))["names"]
)
