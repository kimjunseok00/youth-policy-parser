"""공식 페이지 확인을 마친 정책을 '확인 완료'로 표시하고 앱에 나오게(승격) 한다.

    uv run python scripts/approve.py 20250616005400110940 20250616005400110939
    uv run python scripts/approve.py --all --unverified    # 확인 전 정책까지 전부 (2차 출처 그대로)

하는 일 (정책마다)
1. data/curation/*.json 에서 그 정책의 review 를 []로 비운다 (확인 완료 기록)
2. 초안(data/drafts/)에 반영하고 data/policies/ 로 승격한다. 금액이 없는 정책(대출·주택 공급)도 허용
끝나면 validate.py → update_snapshot.py → pytest 순서로 확인한다.
확인하지 않은 정책을 --all --unverified 로 올리면 앱에는 확인된 정보처럼 보이니 주의한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import curate  # noqa: E402
from promote import promote  # noqa: E402

CURATION = ROOT / "data" / "curation"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("numbers", nargs="*", help="정책번호(plcyNo) 또는 ontong-정책번호")
    ap.add_argument("--all", action="store_true", help="curation 에 있는 모든 정책")
    ap.add_argument(
        "--unverified", action="store_true", help="--all 과 함께: 공식 확인 없이 승격함을 인정"
    )
    ap.add_argument("--dry-run", action="store_true", help="파일을 바꾸지 않고 대상만 보여 줌")
    args = ap.parse_args()

    files = {f: json.loads(f.read_text("utf-8")) for f in sorted(CURATION.glob("*.json"))}
    known = {no: f for f, edits in files.items() for no in edits}
    if args.all:
        if not args.unverified:
            print("[멈춤] --all 은 공식 확인 없이 전부 올립니다. 그래도 하려면 --unverified 를 붙이세요.")
            return 1
        wanted = list(known)
    else:
        wanted = [n.removeprefix("ontong-") for n in args.numbers]
    if not wanted:
        print(__doc__)
        return 1
    missing = [n for n in wanted if n not in known]
    if missing:
        print(f"[오류] curation 에 없는 정책번호: {', '.join(missing)}")
        return 1
    if args.dry_run:
        for n in wanted:
            print(f"[대상] {n}  ({known[n].name})")
        return 0

    bad = 0
    for n in wanted:
        f = known[n]
        files[f][n]["review"] = []
        f.write_text(json.dumps(files[f], ensure_ascii=False, indent=1) + "\n", "utf-8")
    for f in {known[n] for n in wanted}:  # 초안에 반영 (review 도 함께 비워짐)
        only = {n: files[f][n] for n in wanted if n in files[f]}
        tmp = f.with_suffix(".approve.tmp")
        tmp.write_text(json.dumps(only, ensure_ascii=False), "utf-8")
        sys.argv = ["curate.py", str(tmp)]
        bad += curate.main()
        tmp.unlink(missing_ok=True)
    for n in wanted:
        bad += promote(ROOT / "data" / "drafts" / f"ontong-{n}.json", no_amount=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
