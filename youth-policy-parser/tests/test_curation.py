"""data/curation/*.json: 사람이 검수해 옮긴 값이 스키마와 DSL 문법을 통과하는지 (초안 파일이 없어도 검사한다)."""

import json
from pathlib import Path

import pytest

from engine.parser import parse
from engine.schemas import Policy

FILES = sorted((Path(__file__).resolve().parents[1] / "data" / "curation").glob("*.json"))
BASE = {
    "policy_id": "ontong-test",
    "name": "테스트",
    "agency": "테스트",
    "region": "부산광역시",
    "amount_text": "테스트",
    "source_url": "https://example.com",
    "eligibility_text": "테스트",
}


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_curation_entries_are_valid(path):
    edits = json.loads(path.read_text("utf-8"))
    assert edits
    for plcy_no, e in edits.items():
        assert plcy_no.isdigit(), plcy_no
        pol = Policy.model_validate({**BASE, **{k: v for k, v in e.items() if k != "review"}})
        parse(pol.condition_dsl or "")
