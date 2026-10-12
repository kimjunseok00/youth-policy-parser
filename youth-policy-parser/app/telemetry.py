"""익명 통계 저장 (사용자가 동의한 경우에만).

- 저장 내용은 engine/anonymize.py의 anonymize() 결과뿐이다 (개인 식별 정보 없음).
- 저장소는 Supabase(무료)를 쓴다. .streamlit/secrets.toml(또는 Streamlit Cloud의 Secrets)에
  아래 값이 있을 때만 켜지고, 없으면 아무것도 저장하지 않는다.

    [telemetry]
    supabase_url = "https://<프로젝트>.supabase.co"
    insert_key = "sb_publishable_..."   # 쓰기 전용 (테이블 정책으로 insert만 허용)
    read_key = "sb_secret_..."          # 리포트 읽기용. 서버(Streamlit Secrets)에만 둔다
    table = "events"

- 저장 실패는 화면에 영향을 주지 않는다 (판정 결과가 통계 저장 때문에 막히면 안 된다).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

log = logging.getLogger(__name__)
TIMEOUT = 5  # 초. 저장소가 느려도 화면이 오래 멈추지 않게


@dataclass(frozen=True)
class TelemetryConfig:
    url: str
    insert_key: str
    read_key: str | None
    table: str = "events"

    @property
    def endpoint(self) -> str:
        return f"{self.url.rstrip('/')}/rest/v1/{self.table}"


def load_config(secrets) -> TelemetryConfig | None:
    """Streamlit secrets에서 설정을 읽는다. 없거나 불완전하면 None (= 수집 꺼짐)."""
    try:
        sec = secrets["telemetry"]
        return TelemetryConfig(
            url=sec["supabase_url"],
            insert_key=sec["insert_key"],
            read_key=sec.get("read_key"),
            table=sec.get("table", "events"),
        )
    except Exception:  # secrets 파일이 없으면 Streamlit이 예외를 던진다
        return None


def _request(req: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def record(config: TelemetryConfig | None, row: dict, send=_request) -> bool:
    """익명 요약 1건 저장. 성공하면 True. (send는 테스트에서 바꿔 끼우기 위한 인자)"""
    if config is None:
        return False
    req = urllib.request.Request(
        config.endpoint,
        data=json.dumps({"payload": row}, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            # 새 Supabase 키는 apikey 헤더로만 보낸다 (Authorization: Bearer 아님)
            "apikey": config.insert_key,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        send(req)
        return True
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        log.warning("익명 통계 저장 실패: %s", e)
        return False


def fetch_rows(config: TelemetryConfig | None, limit: int = 5000, send=_request) -> list[dict]:
    """리포트용으로 저장된 익명 요약을 읽는다. 읽기 키가 없거나 실패하면 빈 목록."""
    if config is None or not config.read_key:
        return []
    req = urllib.request.Request(
        f"{config.endpoint}?select=payload&order=id.desc&limit={limit}",
        headers={"apikey": config.read_key},
    )
    try:
        return [item["payload"] for item in json.loads(send(req))]
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as e:
        log.warning("익명 통계 읽기 실패: %s", e)
        return []
