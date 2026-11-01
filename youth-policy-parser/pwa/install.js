// 홈 화면 설치 안내
//
// 포스터의 QR은 주소만 열 수 있어서 '설치'를 대신해 주지 못한다.
// 그래서 QR로 처음 들어온 사람에게 이 앱 안에서 설치 방법을 보여 준다.
// - 안드로이드(크롬): 브라우저가 설치 가능하다고 알려 주면(beforeinstallprompt) '설치하기' 버튼으로 바로 설치
// - 아이폰(사파리): 웹앱은 버튼으로 설치할 수 없어서 '공유 → 홈 화면에 추가' 순서를 안내
// - 이미 설치해서 연 경우, 컴퓨터에서 연 경우: 아무것도 보이지 않는다.
// '닫기'를 누르면 7일 동안 다시 보이지 않는다.

const DISMISS_KEY = "doenayo.install.dismissed";
const QUIET_MS = 7 * 24 * 60 * 60 * 1000;

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
    box.hidden = true;
  });
  box.append(go, closeButton(box));
  box.hidden = false;
}

export function initInstall() {
  const box = document.querySelector("#install");
  if (!box || isStandalone() || recentlyDismissed()) return;

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault(); // 브라우저 기본 안내 대신 우리 화면에서 보여 준다
    showPrompt(box, e);
  });
  window.addEventListener("appinstalled", () => {
    box.hidden = true;
  });
  if (isIOS()) showIOS(box);
}
