// 서비스 워커: 앱 파일을 기기에 저장해 두 번째 실행부터 빠르게, 오프라인에서도 열리게 한다.
//
// - 설치될 때 앱 파일 전부(엔진·Pyodide 포함, 약 15MB)를 미리 저장한다.
// - 캐시 이름에 빌드 해시가 들어 있어서, 정책 데이터나 화면이 바뀌어 다시 배포하면
//   새 캐시를 만들고 옛 캐시는 지운다.
// - 저장 전략: 저장된 것이 있으면 그것을 쓰고(cache-first), 없으면 네트워크에서 받는다.
//   단, 화면 첫 문서(index.html)는 네트워크를 먼저 시도해 새 버전을 빨리 반영한다.
const CACHE = "doenayo-__BUILD__";
const FILES = __FILES__; // 빌드 때 dist 안의 파일 목록으로 바뀐다

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(FILES))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return; // 글꼴 CDN 등은 브라우저 기본 동작

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put("./", copy));
          return res;
        })
        .catch(() => caches.match("./")),
    );
    return;
  }
  event.respondWith(
    caches.match(req, { ignoreSearch: true }).then((hit) => hit || fetch(req)),
  );
});
