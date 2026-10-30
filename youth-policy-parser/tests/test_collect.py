"""scripts/collect.py 전체 흐름: 가짜 API 서버로 쪽 넘김 → 원본 저장 → 초안 생성 → 키 가리기."""

import http.server
import importlib.util
import json
import threading
import urllib.parse
from pathlib import Path

import pytest

from tests.test_ingest import ITEM, NATION

KEY = "SECRETKEY123456"
SEEN: list[dict] = []


class FakeApi(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
        SEEN.append(q)
        page = int(q["pageNum"])
        items = {
            1: [ITEM, {**ITEM, "plcyNo": "2", "zipCd": NATION}],
            2: [{**ITEM, "plcyNo": "3", "zipCd": "11110"}],  # 서울 정책 → 제외
        }.get(page, [])
        body = json.dumps({"result": {"pagging": {"totCount": 3}, "youthPolicyList": items}})
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *a):
        pass


@pytest.fixture
def collect(tmp_path, monkeypatch):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeApi)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    path = Path(__file__).resolve().parents[1] / "scripts" / "collect.py"
    spec = importlib.util.spec_from_file_location("collect", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(mod, "DRAFT_DIR", tmp_path / "drafts")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    monkeypatch.setenv("ONTONG_API_KEY", KEY)
    monkeypatch.setenv("ONTONG_API_URL", f"http://127.0.0.1:{srv.server_port}/go/ythip/getPlcy")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    SEEN.clear()
    yield mod, tmp_path
    srv.shutdown()


def test_collect_pages_and_writes_busan_and_national_drafts(collect, monkeypatch, capsys):
    mod, tmp = collect
    monkeypatch.setattr("sys.argv", ["collect.py", "--page-size", "2"])
    assert mod.main() == 0
    assert [q["pageNum"] for q in SEEN] == ["1", "2"]
    assert all(q["apiKeyNm"] == KEY and q["rtnType"] == "json" for q in SEEN)
    drafts = sorted(p.name for p in (tmp / "drafts").glob("*.json"))
    assert drafts == ["ontong-2.json", "ontong-20260301005400110001.json"]
    assert len(json.loads(next((tmp / "raw").glob("*.json")).read_text())) == 3
    assert KEY not in capsys.readouterr().out


def test_inspect_masks_key(collect, monkeypatch, capsys):
    mod, _ = collect
    monkeypatch.setattr("sys.argv", ["collect.py", "--inspect"])
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "youthPolicyList: list" in out and "plcyNm" in out and KEY not in out
