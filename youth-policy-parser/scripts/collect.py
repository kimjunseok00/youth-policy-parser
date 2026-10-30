"""온통청년 청년정책 API 수집 → 원본 저장 + 검수용 초안 생성.

.env (youth-policy-parser 폴더, 커밋 금지):
    ONTONG_API_KEY=청년정책API_인증키

실행 (youth-policy-parser 폴더에서):
    uv run --env-file .env python scripts/collect.py --inspect      # 1) 응답 구조만 확인 (키는 가려서 출력)
    uv run --env-file .env python scripts/collect.py                # 2) 부산 + 전국 정책 수집 → 초안
    uv run --env-file .env python scripts/collect.py --scope all --max-pages 5

결과
    data/raw/ontong/<날짜>.json   응답 원본 (커밋하지 않음, .gitignore)
    data/drafts/<policy_id>.json  검수용 초안 (커밋해서 데이터 담당이 검수)
초안은 앱에 나오지 않는다. 검수 후 scripts/promote.py로 data/policies/에 옮긴다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest.ontong import describe, draft, find_items, find_total, wanted  # noqa: E402

DEFAULT_URL = "https://www.youthcenter.go.kr/go/ythip/getPlcy"
RAW_DIR = ROOT / "data" / "raw" / "ontong"
DRAFT_DIR = ROOT / "data" / "drafts"
POLICY_DIR = ROOT / "data" / "policies"


def mask(s: str, key: str) -> str:
    """출력·오류 메시지에 인증키가 찍히지 않게 가린다."""
    for k in {key, urllib.parse.quote(key, safe="")}:
        if k:
            s = s.replace(k, k[:4] + "****")
    return s


def fetch(url: str, key_param: str, key: str, params: dict) -> object:
    q = urllib.parse.urlencode({key_param: key, "rtnType": "json", **params})
    req = urllib.request.Request(f"{url}?{q}", headers={"User-Agent": "doenayo-collector"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON이 아닌 응답입니다 (앞부분): {body[:300]}") from e


def main() -> int:
    ap = argparse.ArgumentParser(description="온통청년 청년정책 수집")
    ap.add_argument("--inspect", action="store_true", help="응답 구조와 첫 정책의 필드만 출력")
    ap.add_argument("--scope", choices=["busan", "all"], default="busan")
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--keyword", default="", help="정책명 검색어 (plcyKywdNm)")
    args = ap.parse_args()

    key = os.environ.get("ONTONG_API_KEY", "").strip()
    url = os.environ.get("ONTONG_API_URL", DEFAULT_URL).strip()
    key_param = os.environ.get("ONTONG_KEY_PARAM", "apiKeyNm").strip()
    if not key:
        print("[오류] ONTONG_API_KEY가 없습니다. --env-file .env를 붙였는지 확인하세요.")
        return 1
    extra = {"plcyKywdNm": args.keyword} if args.keyword else {}

    try:
        if args.inspect:
            data = fetch(url, key_param, key, {"pageNum": 1, "pageSize": 2, **extra})
            print("== 응답 구조 (값 제외) ==")
            print("\n".join(describe(data)))
            items = find_items(data)
            print(f"\n정책 목록: {len(items)}건 찾음 / 전체 건수 필드: {find_total(data)}")
            if items:
                print("\n== 첫 정책의 필드 (값은 앞 40자) ==")
                for k, v in items[0].items():
                    print(f"{k}: {mask(str(v), key)[:40]!r}")
            return 0

        RAW_DIR.mkdir(parents=True, exist_ok=True)
        DRAFT_DIR.mkdir(parents=True, exist_ok=True)
        all_items: list[dict] = []
        total = None
        for page in range(1, args.max_pages + 1):
            data = fetch(
                url, key_param, key, {"pageNum": page, "pageSize": args.page_size, **extra}
            )
            items = find_items(data)
            total = total or find_total(data)
            all_items += items
            print(f"{page}쪽: {len(items)}건 (누적 {len(all_items)} / 전체 {total or '?'})")
            if len(items) < args.page_size or (total and len(all_items) >= total):
                break
            time.sleep(0.3)  # 서버에 부담을 주지 않게
    except urllib.error.HTTPError as e:
        print(f"[오류] HTTP {e.code}: {mask(e.read().decode('utf-8', 'replace')[:300], key)}")
        return 1
    except (urllib.error.URLError, RuntimeError, TimeoutError) as e:
        print(f"[오류] {mask(str(e), key)}")
        return 1

    raw_path = RAW_DIR / f"{date.today().isoformat()}.json"
    raw_path.write_text(json.dumps(all_items, ensure_ascii=False, indent=1), "utf-8")
    picked = [i for i in all_items if wanted(i, args.scope)]
    made = skipped = 0
    for item in picked:
        d = draft(item)
        pid = d["policy"]["policy_id"]
        if (POLICY_DIR / f"{pid}.json").exists():
            skipped += 1  # 이미 검수해서 반영한 정책은 덮어쓰지 않는다
            continue
        (DRAFT_DIR / f"{pid}.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=2) + "\n", "utf-8"
        )
        made += 1
    print(f"\n원본 {len(all_items)}건 저장: {raw_path.relative_to(ROOT)}")
    print(
        f"범위({args.scope}) {len(picked)}건 → 초안 {made}건 생성, 이미 반영된 {skipped}건 건너뜀"
    )
    print(
        f"다음: {DRAFT_DIR.relative_to(ROOT)}/ 의 review 항목을 공고문과 대조 → scripts/promote.py"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
