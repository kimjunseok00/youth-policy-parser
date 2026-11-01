"""data/curation/<batch>.json → docs/review_<batch>.md (데이터 담당용 공식 페이지 확인 체크리스트).

    uv run python scripts/review_doc.py data/curation/batch2.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    src = Path(sys.argv[1]).resolve()
    edits = json.loads(src.read_text("utf-8"))
    rows = [
        f"# 검수 체크리스트 — {src.stem}",
        "",
        "온통청년 API 본문을 읽고 조건식과 금액을 채운 **2차 출처** 정책입니다. 아래 항목을 공식 페이지에서 확인한 뒤",
        f"`{src.relative_to(ROOT)}`의 `review`를 비우고 `scripts/promote.py`로 승격합니다. 확인 못 한 정책은 승격하지 않습니다.",
        "",
        "| 정책 | 공식 페이지 | 확인할 항목 |",
        "| --- | --- | --- |",
    ]
    for no, e in edits.items():
        d = json.loads((ROOT / "data" / "drafts" / f"ontong-{no}.json").read_text("utf-8"))
        raw = d["raw"]
        urls = {d["policy"]["source_url"], raw.get("aplyUrlAddr", "").strip(), raw.get("refUrlAddr1", "").strip()}
        urls = sorted(u for u in urls if u)
        todo = "<br>".join("· " + x for x in e["review"])
        rows.append(f"| {d['policy']['name']} | {'<br>'.join(urls)} | {todo} |")
    out = ROOT / "docs" / f"review_{src.stem}.md"
    out.write_text("\n".join(rows) + "\n", "utf-8")
    print(f"저장: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
