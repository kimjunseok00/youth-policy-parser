"""청년용 앱(PWA) 빌드: pwa/ 화면 + 판정 엔진 + 브라우저용 Python(Pyodide)을 한 폴더로 묶는다.

    uv run python scripts/build_app.py              # → pwa/dist/
    uv run python scripts/build_app.py --out ../_site/app

만드는 것
- dist/                     pwa/의 화면 파일 (index.html, app.js, worker.js, sw.js, ...)
- dist/engine.zip           engine/ 코드 + data/ 정책·기준표 + lark(순수 Python 파서 라이브러리)
- dist/pyodide/             Pyodide 핵심 파일 + pydantic 등 필요한 패키지만 (전체 배포판은 330MB라 골라 담는다)

왜 이렇게 하나
- 판정 로직을 자바스크립트로 다시 만들지 않고, 지자체용 웹과 '같은 Python 코드'를 브라우저에서 돌린다.
- Pyodide를 외부 CDN에서 받지 않고 같이 배포한다 → 외부 서비스가 막혀도 앱이 동작하고,
  서비스 워커가 한 번 저장하면 오프라인에서도 열린다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

import lark

ROOT = Path(__file__).resolve().parent.parent
PWA_SRC = ROOT / "pwa"
PYODIDE_VERSION = "314.0.7"  # 바꿀 때는 pwa/worker.js 주석과 docs/app.md도 함께 확인
PYODIDE_URL = (
    "https://github.com/pyodide/pyodide/releases/download/"
    f"{PYODIDE_VERSION}/pyodide-{PYODIDE_VERSION}.tar.bz2"
)
CACHE = Path.home() / ".cache" / "doenayo"
CORE_FILES = [
    "pyodide.mjs",
    "pyodide.asm.mjs",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
]
PACKAGES = ["pydantic"]  # 엔진이 쓰는 것 중 Pyodide 빌드가 필요한 패키지 (의존성은 자동 포함)


def download_pyodide() -> Path:
    """Pyodide 배포판을 한 번만 내려받아 캐시에 둔다 (CI에서는 actions/cache로 재사용)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"pyodide-{PYODIDE_VERSION}.tar.bz2"
    if not target.exists():
        print(f"Pyodide {PYODIDE_VERSION} 내려받는 중 (약 330MB, 처음 한 번만)…")
        tmp = target.with_suffix(".part")
        with urllib.request.urlopen(PYODIDE_URL, timeout=600) as r, tmp.open("wb") as f:
            shutil.copyfileobj(r, f)
        tmp.rename(target)
    return target


def needed_wheels(lock: dict, names: list[str]) -> list[str]:
    """pyodide-lock.json에서 패키지와 그 의존성의 파일 이름을 모은다."""
    pkgs = lock["packages"]
    seen: set[str] = set()
    stack = [n.lower().replace("_", "-") for n in names]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        stack += [d.lower().replace("_", "-") for d in pkgs[name]["depends"]]
    return sorted(pkgs[n]["file_name"] for n in seen)


def copy_pyodide(out: Path) -> list[str]:
    archive = download_pyodide()
    dest = out / "pyodide"
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:bz2") as tar:
        lock = json.load(tar.extractfile("pyodide/pyodide-lock.json"))  # type: ignore[arg-type]
        files = CORE_FILES + needed_wheels(lock, PACKAGES)
        for name in files:
            member = tar.getmember(f"pyodide/{name}")
            with tar.extractfile(member) as src, (dest / name).open("wb") as dst:  # type: ignore[union-attr]
                shutil.copyfileobj(src, dst)
    return files


def build_engine_zip(out: Path) -> str:
    """engine/ + data/ + lark를 zip 하나로. 앱은 이 파일을 브라우저 안의 가상 디스크에 푼다."""
    target = out / "engine.zip"
    lark_dir = Path(lark.__file__).parent
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((ROOT / "engine").glob("*")):
            if f.suffix in {".py", ".lark"}:
                z.write(f, f"engine/{f.name}")
        for f in sorted((ROOT / "data").rglob("*.json")):
            rel = f.relative_to(ROOT)
            if rel.parts[1] in {"policies", "reference"} or rel.name == "personas.json":
                z.write(f, str(rel))
        for f in sorted(lark_dir.rglob("*")):
            if f.is_file() and f.suffix in {".py", ".lark"}:
                z.write(f, f"lark/{f.relative_to(lark_dir)}")
    return hashlib.sha256(target.read_bytes()).hexdigest()[:12]


def build(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(PWA_SRC, out, ignore=shutil.ignore_patterns("dist", "*.md"))
    files = copy_pyodide(out)
    digest = build_engine_zip(out)

    # 서비스 워커 캐시 이름에 엔진 해시를 넣는다 → 정책 데이터가 바뀌면 사용자 기기의 캐시도 새로 받는다
    sw = out / "sw.js"
    sw.write_text(sw.read_text("utf-8").replace("__BUILD__", digest), "utf-8")
    worker = out / "worker.js"
    worker.write_text(worker.read_text("utf-8").replace("__BUILD__", digest), "utf-8")

    # 서비스 워커가 설치될 때 미리 저장할 파일 목록 (오프라인 실행용)
    files_list = ["./"] + sorted(
        str(f.relative_to(out)).replace("\\", "/")
        for f in out.rglob("*")
        if f.is_file() and f.name != "sw.js"
    )
    sw.write_text(sw.read_text("utf-8").replace("__FILES__", json.dumps(files_list)), "utf-8")

    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(
        f"앱 빌드 완료: {out}  (엔진 {digest}, Pyodide 파일 {len(files)}개, 전체 {size / 1e6:.1f}MB)"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=PWA_SRC / "dist")
    args = ap.parse_args()
    build(args.out.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
