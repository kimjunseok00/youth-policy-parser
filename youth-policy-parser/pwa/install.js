// 홈 화면 설치 안내
//
// 포스터의 QR은 주소만 열 수 있어서 '설치'를 대신해 주지 못한다.
// 그래서 QR로 처음 들어온 사람에게 이 앱 안에서 설치 방법을 보여 준다.
// - 안드로이드(크롬): 브라우저가 설치 가능하다고 알려 주면(beforeinstallprompt) '설치하기' 버튼으로 바로 설치
// - 아이폰(사파리): 웹앱은 버튼으로 설치할 수 없어서 '공유 → 홈 화면에 추가' 순서를 안내
// - 이미 설치해서 연 경우, 컴퓨터에서 연 경우: 아무것도 보이지 않는다.
// '닫기'를 누르면 7일 동안 다시 보이지 않는다.
// 닫은 뒤에도 '내 정보' 화면 아래 '앱 설치 방법' 버튼(showInstallGuide)으로 언제든 다시 열 수 있다.

const DISMISS_KEY = "doenayo.install.dismissed";
const QUIET_MS = 7 * 24 * 60 * 60 * 1000;

// 안드로이드 크롬이 '설치 가능'이라고 알려 준 이벤트. 다시 보기 버튼에서도 쓰려고 기억해 둔다.
let deferredPrompt = null;

function isStandalone() {
  return window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
}

function isIOS() {
  const ua = navigator.userAgent;
  // 아이패드는 맥으로 위장하므로 터치 지점 수로 구별한다
  return /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function recentlyDismissed() {
  try {
    const t = Number(localStorage.getItem(DISMISS_KEY));
    return t > 0 && Date.now() - t < QUIET_MS;
  } catch {
    return false;
  }
}

function dismiss(box) {
  try {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  } catch {
    /* 저장이 막혀 있으면 이번 방문에서만 닫힌다 */
  }
  box.hidden = true;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function closeButton(box) {
  const btn = el("button", "install-close", "닫기");
  btn.type = "button";
  btn.addEventListener("click", () => dismiss(box));
  return btn;
}

function showIOS(box) {
  box.replaceChildren(
    el("p", "install-title", "홈 화면에 추가하면 앱처럼 쓸 수 있어요"),
    el("p", "install-desc", "인터넷 연결이 약해도 열리고, 다음부터는 아이콘 한 번으로 시작합니다."),
  );
  const steps = el("ol", "install-steps");
  for (const s of [
    "사파리 아래쪽의 공유 버튼(네모에 화살표)을 누릅니다. 보이지 않으면 오른쪽 아래 ··· 를 먼저 누르세요.",
    "'홈 화면에 추가'를 고릅니다.",
    "오른쪽 위 '추가'를 누르면 끝입니다.",
  ]) {
    steps.append(el("li", "", s));
  }
  box.append(steps, closeButton(box));
  box.hidden = false;
}

function showGeneric(box) {
  box.replaceChildren(
    el("p", "install-title", "홈 화면에 추가하는 방법"),
    el("p", "install-desc", "브라우저마다 메뉴 이름이 조금씩 다릅니다."),
  );
  const steps = el("ol", "install-steps");
  for (const s of [
    "아이폰: 사파리 공유 버튼(네모에 화살표) → '홈 화면에 추가' → '추가'",
    "안드로이드: 크롬 오른쪽 위 메뉴(점 3개) → '홈 화면에 추가' 또는 '앱 설치'",
  ]) {
    steps.append(el("li", "", s));
  }
  box.append(steps, closeButton(box));
  box.hidden = false;
}

function showInstalled(box) {
  box.replaceChildren(
    el("p", "install-title", "이미 앱으로 실행 중입니다"),
    el("p", "install-desc", "홈 화면의 '되나요' 아이콘으로 열려 있어서 따로 설치할 필요가 없습니다."),
  );
  box.append(closeButton(box));
  box.hidden = false;
}

function showPrompt(box, deferred) {
  box.replaceChildren(
    el("p", "install-title", "앱으로 설치해서 쓰세요"),
    el("p", "install-desc", "홈 화면에 아이콘이 생기고, 인터넷 연결이 약해도 열립니다."),
  );
  const go = el("button", "btn install-go", "설치하기");
  go.type = "button";
  go.addEventListener("click", async () => {
    deferred.prompt();
    await deferred.userChoice.catch(() => {});
    deferredPrompt = null; // 한 번 쓴 설치 이벤트는 다시 쓸 수 없다
    box.hidden = true;
  });
  box.append(go, closeButton(box));
  box.hidden = false;
}

export function initInstall() {
  const box = document.querySelector("#install");
  if (!box) return;

  // 설치 이벤트는 '닫기'를 눌렀어도 기억해 둔다 (다시 보기 버튼에서 바로 설치할 수 있게)
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault(); // 브라우저 기본 안내 대신 우리 화면에서 보여 준다
    deferredPrompt = e;
    if (!isStandalone() && !recentlyDismissed()) showPrompt(box, e);
  });
  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    box.hidden = true;
  });
  if (isIOS() && !isStandalone() && !recentlyDismissed()) showIOS(box);
}

// '앱 설치 방법' 버튼: 7일 숨김과 상관없이 지금 환경에 맞는 안내를 다시 보여 준다.
export function showInstallGuide() {
  const box = document.querySelector("#install");
  if (!box) return;
  if (isStandalone()) showInstalled(box);
  else if (deferredPrompt) showPrompt(box, deferredPrompt);
  else if (isIOS()) showIOS(box);
  else showGeneric(box);
  window.scrollTo({ top: 0, behavior: "smooth" });
}
