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

from ingest.ontong import (  # noqa: E402
    describe,
    draft,
    find_items,
    find_total,
    is_open,
    wanted,
)

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


RETRY_WAITS = (5, 20, 60)  # 초. 일시적 403/429/5xx·네트워크 오류 때 기다렸다 다시 시도


def fetch_retry(url: str, key_param: str, key: str, params: dict) -> object:
    """일시적 오류(403·429·5xx·네트워크)는 간격을 늘려 재시도한다. 마지막 실패는 그대로 올린다."""
    for wait in (*RETRY_WAITS, None):
        try:
            return fetch(url, key_param, key, params)
        except urllib.error.HTTPError as e:
            if wait is None or e.code not in (403, 429, 500, 502, 503, 504):
                raise
            why = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError) as e:
            if wait is None:
                raise
            why = type(e).__name__
        print(f"  {why} - {wait}초 뒤 재시도")
        time.sleep(wait)
    raise RuntimeError("unreachable")


def write_drafts(all_items: list[dict], scope: str, include_closed: bool, raw_path: Path) -> int:
    """범위·신청 가능 여부로 거른 정책을 검수용 초안으로 저장한다."""
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    in_scope = [i for i in all_items if wanted(i, scope)]
    picked = in_scope if include_closed else [i for i in in_scope if is_open(i)]
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
    print(f"\n원본 {len(all_items)}건: {raw_path.relative_to(ROOT)}")
    print(f"범위({scope}) {len(in_scope)}건 중 신청 가능 {len(picked)}건")
    print(f"→ 초안 {made}건 생성, 이미 반영된 {skipped}건 건너뜀")
    print(
        f"다음: {DRAFT_DIR.relative_to(ROOT)}/ 의 review 항목을 공고문과 대조 → scripts/promote.py"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="온통청년 청년정책 수집")
    ap.add_argument("--inspect", action="store_true", help="응답 구조와 첫 정책의 필드만 출력")
    ap.add_argument("--scope", choices=["busan", "all"], default="busan")
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--resume", action="store_true", help="오늘 저장된 원본이 있으면 이어서 수집")
    ap.add_argument(
        "--from-raw",
        action="store_true",
        help="API를 부르지 않고 저장된 최신 원본으로 초안만 다시 만든다",
    )
    ap.add_argument(
        "--include-closed", action="store_true", help="마감된 정책도 초안으로 만든다 (기본: 제외)"
    )
    ap.add_argument("--keyword", default="", help="정책명 검색어 (plcyKywdNm)")
    args = ap.parse_args()

    key = os.environ.get("ONTONG_API_KEY", "").strip()
    url = os.environ.get("ONTONG_API_URL", DEFAULT_URL).strip()
    key_param = os.environ.get("ONTONG_KEY_PARAM", "apiKeyNm").strip()
    if not key and not args.from_raw:
        print("[오류] ONTONG_API_KEY가 없습니다. --env-file .env를 붙였는지 확인하세요.")
        return 1
    extra = {"plcyKywdNm": args.keyword} if args.keyword else {}

    if args.from_raw:
        files = sorted(RAW_DIR.glob("*.json"))
        if not files:
            print("[오류] 저장된 원본이 없습니다. 먼저 collect.py를 실행하세요.")
            return 1
        raw_path = files[-1]
        all_items = json.loads(raw_path.read_text("utf-8"))
        return write_drafts(all_items, args.scope, args.include_closed, raw_path)

    if args.inspect:
        try:
            data = fetch_retry(url, key_param, key, {"pageNum": 1, "pageSize": 2, **extra})
        except (urllib.error.URLError, RuntimeError, TimeoutError) as e:
            print(f"[오류] {mask(str(e), key)}")
            return 1
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
    raw_path = RAW_DIR / f"{date.today().isoformat()}.json"
    all_items: list[dict] = []
    if args.resume and raw_path.exists():
        all_items = json.loads(raw_path.read_text("utf-8"))
        print(f"이어받기: 저장된 {len(all_items)}건에서 계속")
    total = None
    failed = False
    page = len(all_items) // args.page_size + 1
    while page <= args.max_pages:
        try:
            data = fetch_retry(
                url, key_param, key, {"pageNum": page, "pageSize": args.page_size, **extra}
            )
        except (urllib.error.URLError, RuntimeError, TimeoutError) as e:
            code = f"HTTP {e.code}: " if isinstance(e, urllib.error.HTTPError) else ""
            body = e.read().decode("utf-8", "replace")[:200] if code else str(e)
            print(f"[오류] {page}쪽 {code}{mask(body, key)}")
            failed = True
            break
        items = find_items(data)
        total = total or find_total(data)
        all_items += items
        # 쪽마다 저장: 중간에 실패해도 받은 데이터는 남는다
        raw_path.write_text(json.dumps(all_items, ensure_ascii=False, indent=1), "utf-8")
        print(f"{page}쪽: {len(items)}건 (누적 {len(all_items)} / 전체 {total or '?'})")
        if not items or (total and len(all_items) >= total):
            break
        page += 1
        time.sleep(1.0)  # 서버에 부담을 주지 않게

    code = write_drafts(all_items, args.scope, args.include_closed, raw_path)
    if failed:
        print("\n수집이 중간에 멈췄습니다. 잠시 뒤 이어서 받으세요:")
        print("  uv run --env-file .env python scripts/collect.py --resume")
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main())
