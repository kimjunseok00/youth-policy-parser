// 되나요 청년용 앱 (PWA) — 화면 로직
//
// 흐름: 엔진 준비(worker.js) → 내 정보 입력 → 판정 → 결과 / 더 받기 / 일정 탭
// 원칙
// - 판정은 전부 엔진(Python, engine/service.py)이 한다. 이 파일은 받은 JSON을 그리기만 한다.
// - 입력한 정보는 서버로 보내지 않는다. 다음에 다시 열 때 편하도록 이 기기(localStorage)에만 기억한다.
// - 이모티콘을 쓰지 않는다. 판정은 글자 배지(충족·불충족·확인 필요·참고)로 표시한다.
// - 화면에 넣는 모든 글자는 esc()를 거친다 (정책 데이터에 HTML이 섞여도 실행되지 않게).

const STORE_KEY = "doenayo.v1";
const BUSAN = "부산광역시";
const VERDICT = {
  충족: { cls: "pass", label: "충족" },
  불충족: { cls: "fail", label: "불충족" },
  확인필요: { cls: "unknown", label: "확인 필요" },
};
const FIX_TAG = { 행동: ["바꿀 수 있음", "blue"], 시간: ["시간이 지나면", "note"], "변경 어려움": ["변경 어려움", "note"] };
const EVENT_TAG = { "자격 발생": "pass", "자격 상실": "fail", "신청 마감": "unknown" };

const state = {
  meta: null, // 선택지·예시 인물·기준중위소득 (엔진이 준다)
  form: null, // 입력값 (소득은 '만 원' 단위)
  answers: {}, // 확인 질문 답 {질문: true/false}
  data: null, // 마지막 판정 결과
  filter: "all",
  withUnknown: false,
  persona: null,
  busy: false,
};
const asOfParam = new URLSearchParams(location.search).get("as_of"); // 시연용: ?as_of=2026-10-12

// ---------------------------------------------------------------------------
// 엔진 호출 (워커와 문자열로 주고받기)
// ---------------------------------------------------------------------------
const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
const pending = new Map();
let seq = 0;
const BOOT_STEPS = ["Python 실행 환경을 여는 중", "판정 엔진 부품을 불러오는 중", "정책 데이터를 불러오는 중"];

worker.onmessage = (e) => {
  const { id, ok, out, progress } = e.data;
  if (progress) {
    const i = BOOT_STEPS.indexOf(progress);
    $("#bootStep").textContent = progress;
    $("#bootBar").style.width = `${25 + i * 25}%`;
    return;
  }
  const p = pending.get(id);
  pending.delete(id);
  ok ? p.resolve(out) : p.reject(new Error(out));
};

function call(fn, arg = "") {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, fn, arg });
  });
}

// ---------------------------------------------------------------------------
// 도우미
// ---------------------------------------------------------------------------
function $(sel, root = document) {
  return root.querySelector(sel);
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
function won(n) {
  return n == null ? "금액 미정" : `${n.toLocaleString("ko-KR")}원`;
}
function man(n) {
  if (n == null) return "금액 미정";
  return n >= 10000 ? `${Math.round(n / 10000).toLocaleString("ko-KR")}만 원` : `${n.toLocaleString("ko-KR")}원`;
}
function badge(verdict) {
  const v = VERDICT[verdict];
  return `<span class="badge ${v.cls}">${v.label}</span>`;
}
function tag(text, cls = "note") {
  return `<span class="badge ${cls}">${esc(text)}</span>`;
}
function period(p) {
  if (!p.apply_start && !p.apply_end) return "상시 · 공고 확인";
  return `${p.apply_start ?? ""} ~ ${p.apply_end ?? ""}`;
}
function leaves(node) {
  return node.children?.length ? node.children.flatMap(leaves) : [node];
}
function load() {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY)) ?? {};
  } catch {
    return {};
  }
}
function save() {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify({ form: state.form, answers: state.answers }));
  } catch {
    /* 사생활 보호 모드 등에서는 기억하지 않고 넘어간다 */
  }
}

// 예시 인물(엔진 형식, 원 단위) → 입력값(만 원 단위)
function formFromProfile(p) {
  return {
    birth_date: p.birth_date,
    military_months: p.military_months ?? 0,
    sido: p.sido,
    sigungu: p.sigungu,
    residence_since: p.residence_since,
    education: p.education,
    employment: p.employment,
    household_size: p.household_size,
    personal_income: Math.round(p.personal_income_monthly / 10000),
    household_income: Math.round(p.household_income_monthly / 10000),
    current_benefits: [...(p.current_benefits ?? [])],
  };
}
function profileFromForm(f) {
  return {
    birth_date: f.birth_date,
    sido: f.sido,
    sigungu: (f.sigungu || "").trim(),
    residence_since: f.residence_since,
    education: f.education,
    employment: f.employment,
    personal_income_monthly: Math.round(Number(f.personal_income || 0) * 10000),
    household_size: Number(f.household_size),
    household_income_monthly: Math.round(Number(f.household_income || 0) * 10000),
    current_benefits: f.current_benefits,
    military_months: Number(f.military_months || 0),
  };
}

// ---------------------------------------------------------------------------
// 화면 전환
// ---------------------------------------------------------------------------
function show(view) {
  document.querySelectorAll("main > .view").forEach((v) => (v.hidden = v.dataset.view !== view));
  document.querySelectorAll(".tabbar button").forEach((b) => {
    if (b.dataset.tab === view) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
    b.disabled = b.dataset.tab !== "profile" && !state.data;
  });
  window.scrollTo({ top: 0 });
}

document.querySelector(".tabbar").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-tab]");
  if (b && !b.disabled) show(b.dataset.tab);
});

// ---------------------------------------------------------------------------
// 내 정보 (입력)
// ---------------------------------------------------------------------------
function options(list, current) {
  return list.map((v) => `<option ${v === current ? "selected" : ""}>${esc(v)}</option>`).join("");
}

function incomeHint() {
  const f = state.form;
  const base = state.meta.median_income.monthly[String(Math.min(8, Math.max(1, f.household_size)))];
  const pct = base ? (Number(f.household_income || 0) * 10000 * 100) / base : 0;
  return `기준중위소득의 약 ${pct.toFixed(0)}% (${state.meta.median_income.year}년, ${f.household_size}인 가구 기준)`;
}

function renderProfile() {
  const { meta, form: f } = state;
  const o = meta.options;
  const sigungu =
    f.sido === BUSAN
      ? `<select name="sigungu">${options(o.busan_sigungu, f.sigungu)}</select>`
      : `<input type="text" name="sigungu" value="${esc(f.sigungu)}" placeholder="예: 강남구">`;

  $('[data-view="profile"]').innerHTML = `
    <div class="lead">
      <h1>청년정책, 나도 되나요?</h1>
      <p>정보를 넣으면 정책마다 되는지, 안 되면 왜 안 되는지 알려 드립니다.</p>
    </div>

    <p class="section-title">예시 인물로 채우기</p>
    <div class="chips" role="group" aria-label="예시 인물">
      ${meta.personas
        .map((p, i) => `<button type="button" class="chip" data-persona="${i}" aria-pressed="${state.persona === i}">${esc(p.label)}</button>`)
        .join("")}
    </div>

    <form id="profileForm" class="stack" novalidate>
      <div class="card">
        <h2>나이와 거주</h2>
        <div class="row2">
          <label class="field"><span>생년월일</span><input type="date" name="birth_date" value="${esc(f.birth_date)}" required></label>
          <label class="field"><span>군 복무</span>
            <div class="unit"><input type="number" name="military_months" inputmode="numeric" min="0" max="72" value="${f.military_months}"><em>개월</em></div>
          </label>
        </div>
        <label class="field"><span>거주 시·도</span><select name="sido">${options(o.sido, f.sido)}</select></label>
        <label class="field"><span>시·군·구</span>${sigungu}</label>
        <label class="field"><span>지금 주소로 전입한 날</span><input type="date" name="residence_since" value="${esc(f.residence_since)}" required>
          <small>거주 기간 조건(예: 6개월 이상)을 판정하는 데 씁니다.</small></label>
      </div>

      <div class="card">
        <h2>학업과 일</h2>
        <label class="field"><span>학력·재학 상태</span><select name="education">${options(o.education, f.education)}</select></label>
        <label class="field"><span>취업 상태</span><select name="employment">${options(o.employment, f.employment)}</select></label>
      </div>

      <div class="card">
        <h2>소득</h2>
        <div class="field"><span>가구원 수</span>
          <div class="stepper">
            <button type="button" data-step="-1" aria-label="가구원 수 줄이기">−</button>
            <output name="household_size_out">${f.household_size}명</output>
            <button type="button" data-step="1" aria-label="가구원 수 늘리기">+</button>
          </div>
          <small>부모님과 따로 산다면 본인 가구만 셉니다.</small>
        </div>
        <label class="field"><span>본인 월소득 (세전)</span>
          <div class="unit"><input type="number" name="personal_income" inputmode="numeric" min="0" step="10" value="${f.personal_income}"><em>만 원</em></div></label>
        <label class="field"><span>가구 월소득 (본인 포함)</span>
          <div class="unit"><input type="number" name="household_income" inputmode="numeric" min="0" step="10" value="${f.household_income}"><em>만 원</em></div>
          <span class="hint" id="incomeHint">${incomeHint()}</span></label>
      </div>

      <div class="card">
        <h2>지금 받고 있는 지원</h2>
        <div class="checks">
          ${o.benefits
            .map(
              (b) => `<label class="check"><input type="checkbox" name="current_benefits" value="${esc(b)}" ${f.current_benefits.includes(b) ? "checked" : ""}>${esc(b)}</label>`,
            )
            .join("")}
        </div>
        <small class="muted">같이 받을 수 없는 정책(중복수혜)을 가려내는 데 씁니다.</small>
      </div>

      <div id="formError"></div>
      <p class="foot">입력한 정보는 이 기기 안에서만 계산하고 어디에도 보내지 않습니다.<br>
        <a href="../">서비스 소개</a> · <a href="../privacy.html">개인정보처리방침</a> · <a href="../terms.html">이용약관</a></p>
    </form>
    <div class="cta-bar"><button class="btn" type="submit" form="profileForm" id="judgeBtn">판정하기</button></div>
  `;
}

// 입력이 바뀔 때마다 state.form을 갱신 (다시 그리지 않으므로 입력 중 커서가 튀지 않는다)
function readForm(form) {
  const fd = new FormData(form);
  state.form = {
    ...state.form,
    birth_date: fd.get("birth_date"),
    military_months: Number(fd.get("military_months") || 0),
    sido: fd.get("sido"),
    sigungu: fd.get("sigungu") ?? state.form.sigungu,
    residence_since: fd.get("residence_since"),
    education: fd.get("education"),
    employment: fd.get("employment"),
    personal_income: Number(fd.get("personal_income") || 0),
    household_income: Number(fd.get("household_income") || 0),
    current_benefits: fd.getAll("current_benefits"),
  };
}

const profileView = $('[data-view="profile"]');
profileView.addEventListener("input", (e) => {
  const form = e.target.form;
  if (!form) return;
  readForm(form);
  state.persona = null;
  if (e.target.name === "sido") {
    state.form.sigungu = state.form.sido === BUSAN ? state.meta.options.busan_sigungu[0] : "";
    renderProfile();
  }
  const hint = $("#incomeHint");
  if (hint) hint.textContent = incomeHint();
  save();
});
profileView.addEventListener("click", (e) => {
  const chip = e.target.closest("[data-persona]");
  if (chip) {
    const i = Number(chip.dataset.persona);
    state.persona = i;
    state.form = formFromProfile(state.meta.personas[i].profile);
    state.answers = {};
    renderProfile();
    judge();
    return;
  }
  const step = e.target.closest("[data-step]");
  if (step) {
    state.form.household_size = Math.min(12, Math.max(1, state.form.household_size + Number(step.dataset.step)));
    $('output[name="household_size_out"]').textContent = `${state.form.household_size}명`;
    $("#incomeHint").textContent = incomeHint();
    save();
  }
});
profileView.addEventListener("submit", (e) => {
  e.preventDefault();
  readForm(e.target);
  judge();
});

// ---------------------------------------------------------------------------
// 판정
// ---------------------------------------------------------------------------
async function judge({ keepView = false } = {}) {
  if (state.busy) return;
  const f = state.form;
  const err = $("#formError");
  if (!f.birth_date || !f.residence_since || !String(f.sigungu || "").trim()) {
    if (err) err.innerHTML = `<div class="alert">생년월일, 전입한 날, 시·군·구를 입력해 주세요.</div>`;
    show("profile");
    return;
  }
  state.busy = true;
  const btn = $("#judgeBtn");
  if (btn) (btn.disabled = true), (btn.textContent = "판정하는 중");
  try {
    const out = JSON.parse(
      await call("judge", JSON.stringify({ profile: profileFromForm(f), answers: state.answers, as_of: asOfParam })),
    );
    if (out.error) {
      if (err) err.innerHTML = `<div class="alert">입력을 확인해 주세요: ${esc(out.error)}</div>`;
      show("profile");
      return;
    }
    if (err) err.innerHTML = "";
    state.data = out;
    save();
    renderResult();
    renderMore();
    renderSchedule();
    if (!keepView) show("result");
  } catch (e) {
    if (err) err.innerHTML = `<div class="alert">판정 중 문제가 생겼습니다. 새로고침 후 다시 시도해 주세요. (${esc(e.message)})</div>`;
  } finally {
    state.busy = false;
    if (btn) (btn.disabled = false), (btn.textContent = "판정하기");
  }
}

// ---------------------------------------------------------------------------
// 결과
// ---------------------------------------------------------------------------
function cardWhy(p) {
  const ls = leaves(p.reason);
  if (p.verdict === "불충족") {
    const miss = ls.find((l) => l.verdict === "불충족" && !l.notice);
    return miss ? `안 되는 이유: ${esc(miss.label)}${miss.detail ? ` (${esc(miss.detail)})` : ""}` : "";
  }
  if (p.verdict === "확인필요") {
    const n = ls.filter((l) => l.verdict === "확인필요").length;
    return `확인할 조건 ${n}개 · 기대 수령액 약 ${man(p.expected_krw)}`;
  }
  const notes = ls.filter((l) => l.notice).length;
  return notes ? `모든 조건 충족 · 공고문에서 확인할 것 ${notes}개` : "모든 조건 충족";
}

function policyCard(p) {
  const v = VERDICT[p.verdict];
  return `
    <button type="button" class="policy ${v.cls}" data-policy="${esc(p.policy_id)}">
      <svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>
      <span class="top">${badge(p.verdict)}${p.is_open ? "" : tag("신청 기간 아님")}</span>
      <span class="name">${esc(p.policy_name)}</span>
      <span class="meta"><span class="money">${man(p.amount_krw)}</span> · ${esc(p.agency)} · ${esc(period(p))}</span>
      <span class="why">${cardWhy(p)}</span>
    </button>`;
}

function renderResult() {
  const { data } = state;
  const results = data.result.results;
  const count = (v) => results.filter((r) => r.verdict === v).length;
  const plan = state.withUnknown ? data.plan_with_unknown : data.plan;
  const shown = state.filter === "all" ? results : results.filter((r) => r.verdict === state.filter);
  const qs = data.questions;

  $('[data-view="result"]').innerHTML = `
    <div class="card summary accent">
      <div class="label">${state.withUnknown ? "확인 필요까지 포함하면 최대" : "지금 함께 받을 수 있는 최대"}</div>
      <div class="amount">${man(plan.total_krw)}</div>
      <div class="seg" role="group" aria-label="계산 범위">
        <button type="button" data-plan="0" aria-pressed="${!state.withUnknown}">충족 정책만</button>
        <button type="button" data-plan="1" aria-pressed="${state.withUnknown}">확인 필요 포함</button>
      </div>
      ${
        plan.selected.length
          ? `<ul class="plan-list">
              ${plan.selected.map((r) => `<li><span>${badge(r.verdict)} ${esc(r.policy_name)}</span><b>${man(r.amount_krw)}</b></li>`).join("")}
              ${plan.excluded.map((x) => `<li><span class="out">제외: ${esc(x.policy_name)} — ${esc(x.because_of)}와 같이 받을 수 없음</span></li>`).join("")}
            </ul>`
          : `<p class="small muted" style="margin:12px 0 0">지금 신청할 수 있는 정책이 없습니다. '확인 필요 포함'을 눌러 보세요.</p>`
      }
      <div class="counts" style="margin-top:14px">
        <div class="c-pass"><b>${count("충족")}</b><span>충족</span></div>
        <div class="c-unknown"><b>${count("확인필요")}</b><span>확인 필요</span></div>
        <div class="c-fail"><b>${count("불충족")}</b><span>불충족</span></div>
      </div>
    </div>

    ${
      qs.length || Object.keys(state.answers).length
        ? `<div class="card">
            <h2>확인 질문 ${qs.length}개</h2>
            <p class="small muted" style="margin:-6px 0 12px">답하면 '확인 필요'가 충족 또는 불충족으로 바로 바뀝니다.</p>
            ${qs
              .map(
                (q, i) => `<div class="question">
                  <p>${esc(q.text)}</p>
                  <div class="seg" role="group" aria-label="답">
                    <button type="button" data-q="${i}" data-a="yes">예</button>
                    <button type="button" data-q="${i}" data-a="no">아니오</button>
                    <button type="button" data-q="${i}" data-a="skip" aria-pressed="true">모름</button>
                  </div>
                  <span class="small muted">관련 정책: ${q.policies.map(esc).join(", ")}</span>
                </div>`,
              )
              .join("")}
            ${
              Object.keys(state.answers).length
                ? `<p class="small muted" style="margin:10px 0 0">이미 답한 질문 ${Object.keys(state.answers).length}개가 반영되어 있습니다.
                   <button type="button" class="chip" data-reset-answers style="margin-left:6px">답 지우기</button></p>`
                : ""
            }
          </div>`
        : ""
    }

    <div class="seg" role="group" aria-label="판정별로 보기">
      ${[
        ["all", `전체 ${results.length}`],
        ["충족", `충족 ${count("충족")}`],
        ["확인필요", `확인 필요 ${count("확인필요")}`],
        ["불충족", `불충족 ${count("불충족")}`],
      ]
        .map(([k, label]) => `<button type="button" data-filter="${k}" aria-pressed="${state.filter === k}">${label}</button>`)
        .join("")}
    </div>
    ${shown.length ? shown.map(policyCard).join("") : `<p class="empty">해당하는 정책이 없습니다.</p>`}
    <p class="foot">판정 기준일 ${esc(data.as_of)} · 결과는 참고용이며, 최종 자격은 공고문과 담당 기관에서 확인하세요.</p>
  `;
}

$('[data-view="result"]').addEventListener("click", (e) => {
  const t = e.target.closest("button");
  if (!t) return;
  if (t.dataset.policy) return openPolicy(t.dataset.policy);
  if (t.dataset.filter) {
    state.filter = t.dataset.filter;
    return renderResult();
  }
  if (t.dataset.plan) {
    state.withUnknown = t.dataset.plan === "1";
    return renderResult();
  }
  if (t.hasAttribute("data-reset-answers")) {
    state.answers = {};
    return judge({ keepView: true });
  }
  if (t.dataset.q) {
    const q = state.data.questions[Number(t.dataset.q)].text;
    if (t.dataset.a === "skip") delete state.answers[q];
    else state.answers[q] = t.dataset.a === "yes";
    judge({ keepView: true });
  }
});

// ---------------------------------------------------------------------------
// 정책 상세 (아래에서 올라오는 시트)
// ---------------------------------------------------------------------------
function reasonTree(node, depth = 0) {
  if (node.children?.length) {
    const head = depth === 0 ? "" : `<li class="group">${esc(node.label)}</li>`;
    return `${head}<li style="grid-template-columns:1fr"><ul class="reasons" style="${depth ? "padding-left:12px;border-left:2px solid var(--line)" : ""}">
      ${node.children.map((c) => reasonTree(c, depth + 1)).join("")}</ul></li>`;
  }
  const b = node.notice ? tag("참고") : badge(node.verdict);
  return `<li>${b}<span>${esc(node.label)}${node.detail ? `<span class="d">${esc(node.detail)}</span>` : ""}</span></li>`;
}

function openPolicy(id) {
  const p = state.data.result.results.find((r) => r.policy_id === id);
  if (!p) return;
  const sheet = $("#sheet");
  $("#sheetTitle").textContent = p.policy_name;
  const quote = p.reason.source_quote && p.reason.source_quote !== "-" ? p.reason.source_quote : "";
  $("#sheetBody").innerHTML = `
    <div>${badge(p.verdict)} ${p.is_open ? "" : tag("신청 기간 아님")}</div>
    <dl class="facts">
      <dt>금액</dt><dd>${won(p.amount_krw)}${p.amount_text ? `<br><span class="small muted">${esc(p.amount_text)}</span>` : ""}</dd>
      <dt>기관</dt><dd>${esc(p.agency)}</dd>
      <dt>신청 기간</dt><dd>${esc(period(p))}</dd>
      ${p.verdict === "확인필요" ? `<dt>기대 수령액</dt><dd>약 ${man(p.expected_krw)}<br><span class="small muted">확인할 조건 하나당 가능성을 절반으로 보는 단순 추정</span></dd>` : ""}
    </dl>
    <div>
      <p class="section-title" style="margin:0 0 8px">조건별 판정</p>
      <ul class="reasons">${reasonTree(p.reason)}</ul>
    </div>
    ${quote ? `<div><p class="section-title" style="margin:0 0 8px">자격요건 원문</p><div class="quote">${esc(quote)}</div></div>` : ""}
    ${p.source_url ? `<a class="btn ghost" href="${esc(p.source_url)}" target="_blank" rel="noopener" style="text-align:center;text-decoration:none;line-height:28px">공고 출처 보기</a>` : ""}
  `;
  sheet.hidden = false;
  $(".icon-btn", sheet).focus();
}
function closeSheet() {
  $("#sheet").hidden = true;
}
$("#sheet").addEventListener("click", (e) => {
  if (e.target.closest("[data-close]")) closeSheet();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeSheet();
});

// ---------------------------------------------------------------------------
// 더 받기 (이것만 바꾸면 · 조건 하나만 어긋난 정책)
// ---------------------------------------------------------------------------
function renderMore() {
  const { suggestions, near_misses } = state.data;
  const order = { 행동: 0, 시간: 1, "변경 어려움": 2 };
  const misses = [...near_misses].sort((a, b) => order[a.fixable_by] - order[b.fixable_by] || (b.amount_krw ?? 0) - (a.amount_krw ?? 0));

  $('[data-view="more"]').innerHTML = `
    <div class="lead"><h1>이것만 바꾸면</h1><p>행동 하나로 새로 받을 수 있는 정책을 계산했습니다. 잃는 정책도 함께 보여 드립니다.</p></div>
    ${
      suggestions.length
        ? suggestions
            .slice(0, 5)
            .map(
              (s) => `<div class="card tip">
                <span class="head">${esc(s.action)}</span>
                <span><span class="gain">+${man(s.gained_amount_krw)}</span> · 새로 ${s.gained.length}건</span>
                <span class="small muted">${s.gained.map(esc).join(", ")}</span>
                ${s.lost.length ? `<span class="loss">대신 잃는 정책: ${s.lost.map(esc).join(", ")} (−${man(s.lost_amount_krw)})</span>` : ""}
              </div>`,
            )
            .join("")
        : `<div class="card empty">지금 정보에서 행동 하나로 새로 받을 수 있는 정책은 없습니다.</div>`
    }
    <p class="section-title">조건 하나만 어긋난 정책</p>
    ${
      misses.length
        ? `<div class="card"><ul class="list">
            ${misses
              .map((m) => {
                const [t, c] = FIX_TAG[m.fixable_by] ?? [m.fixable_by, "note"];
                return `<li><span class="t">${esc(m.policy_name)} <span class="small muted">${man(m.amount_krw)}</span></span>
                  <span class="small">${esc(m.condition)} · ${esc(m.gap)}</span><span>${tag(t, c)}</span></li>`;
              })
              .join("")}
          </ul></div>`
        : `<div class="card empty">조건 하나 차이로 놓친 정책은 없습니다.</div>`
    }
  `;
}

// ---------------------------------------------------------------------------
// 일정 (자격이 생기는 날 · 사라지는 날 · 마감)
// ---------------------------------------------------------------------------
function renderSchedule() {
  const events = state.data.timeline;
  $('[data-view="schedule"]').innerHTML = `
    <div class="lead"><h1>앞으로의 일정</h1><p>나이·거주 기간 때문에 자격이 생기거나 사라지는 날, 마감이 가까운 정책입니다.</p></div>
    ${
      events.length
        ? `<div class="card"><ul class="list">
            ${events
              .map((e) => {
                const [y, m, d] = e.on.split("-");
                return `<li class="event">
                  <div class="date"><b>${Number(m)}.${Number(d)}</b><span>${y}</span></div>
                  <div><span>${tag(e.kind, EVENT_TAG[e.kind] ?? "note")}</span>
                    <div class="t" style="margin-top:4px">${esc(e.policy_name)} <span class="small muted">${man(e.amount_krw)}</span></div>
                    <div class="small muted">${esc(e.detail)}</div></div>
                </li>`;
              })
              .join("")}
          </ul></div>`
        : `<div class="card empty">앞으로 3년 안에 자격이 바뀌거나 60일 안에 마감되는 정책이 없습니다.</div>`
    }
  `;
}

// ---------------------------------------------------------------------------
// 시작
// ---------------------------------------------------------------------------
async function start() {
  try {
    state.meta = JSON.parse(await call("meta"));
  } catch (e) {
    $("#bootStep").textContent = "판정 엔진을 열지 못했습니다";
    $(".boot-note").textContent = `인터넷 연결을 확인한 뒤 새로고침해 주세요. (${e.message})`;
    return;
  }
  $("#bootBar").style.width = "100%";
  $("#asOf").textContent = `기준일 ${asOfParam ?? state.meta.as_of}`;
  const saved = load();
  state.form = saved.form ?? formFromProfile(state.meta.personas[0].profile);
  state.answers = saved.answers ?? {};
  if (!saved.form) state.persona = 0;
  renderProfile();
  document.querySelector(".tabbar").hidden = false;
  show("profile");
}

if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
  navigator.serviceWorker.register("sw.js").catch(() => {
    /* 저장 기능 없이도 앱은 동작한다 */
  });
}
start();
