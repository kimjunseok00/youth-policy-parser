// 판정 엔진 워커: 브라우저 안에서 Python(Pyodide)으로 engine/service.py를 실행한다.
//
// 왜 워커인가: 엔진을 불러오는 몇 초 동안 화면(로딩 표시, 스크롤)이 멈추지 않게 하려고
//              메인 화면과 다른 스레드에서 Python을 돌린다.
// 주고받는 값: 문자열(JSON)만. {id, fn: "meta" | "judge", arg} → {id, ok, out}
//
// Pyodide 버전은 scripts/build_app.py의 PYODIDE_VERSION을 따른다 (빌드 때 pyodide/에 함께 복사됨).
import { loadPyodide } from "./pyodide/pyodide.mjs";

const BUILD = "__BUILD__"; // 빌드 때 엔진 zip 해시로 바뀐다 → 데이터가 바뀌면 새로 받음

function progress(step) {
  postMessage({ id: 0, progress: step });
}

const ready = (async () => {
  progress("Python 실행 환경을 여는 중");
  const py = await loadPyodide({ indexURL: new URL("./pyodide/", import.meta.url).href });

  progress("판정 엔진 부품을 불러오는 중");
  await py.loadPackage(["pydantic"], { messageCallback: () => {} });

  progress("정책 데이터를 불러오는 중");
  const res = await fetch(new URL(`./engine.zip?v=${BUILD}`, import.meta.url));
  if (!res.ok) throw new Error(`engine.zip을 받지 못했습니다 (${res.status})`);
  py.unpackArchive(await res.arrayBuffer(), "zip", { extractDir: "/home/pyodide/doenayo" });
  py.runPython('import sys; sys.path.insert(0, "/home/pyodide/doenayo")');
  return py.pyimport("engine.service");
})();

onmessage = async (event) => {
  const { id, fn, arg } = event.data;
  try {
    const svc = await ready;
    const out = fn === "meta" ? svc.meta_json() : svc.judge_json(arg);
    postMessage({ id, ok: true, out });
  } catch (err) {
    postMessage({ id, ok: false, out: String(err?.message ?? err) });
  }
};
