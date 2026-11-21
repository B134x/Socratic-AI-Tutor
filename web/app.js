"use strict";

const UI = {
  en: {
    pageTitle: "TUNTAS: practice with gates",
    skip: "Skip to the exercise",
    tagline: "Quadratic equations, one step at a time",
    teacherLink: "Teacher view",
    startTitle: "Start with your own problem",
    classCode: "Class code",
    learnerCode: "Your learner code",
    codeHelp: "Given by your teacher: 2 to 20 letters, digits, - or _.",
    problemLabel: "Your equation",
    problemHelp: "For example x^2 - 5x + 6 = 0. TUNTAS coaches x² + bx + c = 0 with whole-number answers.",
    startBtn: "Start",
    stepsTitle: "Your problem",
    tutorTitle: "Tutor",
    answerLabel: "Your answer",
    you: "You",
    checkBtn: "Check answer",
    continueBtn: "Continue with new numbers",
    newBtn: "Start a new problem",
    masteryTitle: "Mastery (BKT)",
    masteryNote: "Dashed line: gate threshold {thr}. Only unaided, checked answers move a bar.",
    hintsNote: "Hints used: {n}. The final answer is never shown.",
    hintBtn: "Ask for a hint ({n} left)",
    noHints: "No hints left",
    checking: "Checking…",
    starting: "Starting…",
    loadingSession: "Loading your session…",
    passed: "passed",
    belowGate: "below the gate",
    status: { done: "done", current: "now", locked: "locked", skipped: "skipped, already mastered" },
    help: {
      pair: "Two whole numbers with a comma, like 4, -1.",
      expression: "Use ^ for powers, for example (x + 1)(x - 4).",
      roots: "Both values of x, like 2, 5.",
    },
    fieldMissing: "Fill in {field}.",
    fieldCode: "{field} must be 2 to 20 letters, digits, - or _.",
    errors: {
      network: "Could not reach the TUNTAS server. Check that it is running, then try again.",
      timeout: "The server took too long to answer. Try again.",
      out_of_scope: "TUNTAS can coach equations like x² + bx + c = 0 with whole-number answers, for example x^2 - 5x + 6 = 0.",
      unreadable_problem: "That could not be read as an equation. Try something like x^2 - 5x + 6 = 0.",
      invalid_code: "Class and learner codes use 2 to 20 letters, digits, - or _.",
      invalid_answer: "Type an answer first.",
      session_not_found: "That session no longer exists. Start a new problem.",
      default: "Something went wrong. Try again.",
    },
  },
  id: {
    pageTitle: "TUNTAS: latihan bergerbang",
    skip: "Langsung ke latihan",
    tagline: "Persamaan kuadrat, selangkah demi selangkah",
    teacherLink: "Tampilan guru",
    startTitle: "Mulai dengan soalmu sendiri",
    classCode: "Kode kelas",
    learnerCode: "Kode siswamu",
    codeHelp: "Diberikan gurumu: 2 sampai 20 huruf, angka, - atau _.",
    problemLabel: "Persamaanmu",
    problemHelp: "Contoh x^2 - 5x + 6 = 0. TUNTAS membimbing x² + bx + c = 0 dengan jawaban bilangan bulat.",
    startBtn: "Mulai",
    stepsTitle: "Soalmu",
    tutorTitle: "Tutor",
    answerLabel: "Jawabanmu",
    you: "Kamu",
    checkBtn: "Periksa jawaban",
    continueBtn: "Lanjut dengan angka baru",
    newBtn: "Mulai soal baru",
    masteryTitle: "Penguasaan (BKT)",
    masteryNote: "Garis putus-putus: ambang gerbang {thr}. Hanya jawaban mandiri yang sudah diperiksa yang menggerakkan bar.",
    hintsNote: "Petunjuk dipakai: {n}. Jawaban akhir tidak pernah ditampilkan.",
    hintBtn: "Minta petunjuk (sisa {n})",
    noHints: "Petunjuk habis",
    checking: "Memeriksa…",
    starting: "Memulai…",
    loadingSession: "Memuat sesimu…",
    passed: "lulus",
    belowGate: "di bawah gerbang",
    status: { done: "selesai", current: "sekarang", locked: "terkunci", skipped: "dilewati, sudah dikuasai" },
    help: {
      pair: "Dua bilangan bulat dipisah koma, seperti 4, -1.",
      expression: "Pakai ^ untuk pangkat, misalnya (x + 1)(x - 4).",
      roots: "Kedua nilai x, seperti 2, 5.",
    },
    fieldMissing: "Isi {field}.",
    fieldCode: "{field} harus 2 sampai 20 huruf, angka, - atau _.",
    errors: {
      network: "Server TUNTAS tidak bisa dihubungi. Pastikan server berjalan, lalu coba lagi.",
      timeout: "Server terlalu lama menjawab. Coba lagi.",
      out_of_scope: "TUNTAS bisa membimbing persamaan seperti x² + bx + c = 0 dengan jawaban bilangan bulat, misalnya x^2 - 5x + 6 = 0.",
      unreadable_problem: "Itu tidak bisa dibaca sebagai persamaan. Coba seperti x^2 - 5x + 6 = 0.",
      invalid_code: "Kode kelas dan kode siswa terdiri dari 2 sampai 20 huruf, angka, - atau _.",
      invalid_answer: "Tulis jawaban dulu.",
      session_not_found: "Sesi itu sudah tidak ada. Mulai soal baru.",
      default: "Terjadi kesalahan. Coba lagi.",
    },
  },
};

const CODE = /^[A-Za-z0-9_-]{2,20}$/;
const REQUEST_TIMEOUT_MS = 15000; // leaves room for the optional AI rewording (7 s budget on the server)
const LOG_LIMIT = 8;

const { fill, readStorage, writeStorage } = window.TuntasCommon;

let lang = readStorage(localStorage, "tuntas.lang") === "id" ? "id" : "en";
let sessionId = readStorage(sessionStorage, "tuntas.session");
let lastView = null;
let busy = false;

const $ = (id) => document.getElementById(id);
const t = () => UI[lang];
const decimal = (value) => window.TuntasCommon.decimal(lang, value);

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else node.setAttribute(k, v);
  }
  if (text) node.textContent = text;
  return node;
}

function applyStaticText() {
  window.TuntasCommon.applyStaticText(t(), lang);
}

class ApiError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}

async function api(method, path, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new ApiError(data?.error?.code || "default", data?.error?.message || res.statusText);
    return data;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(err.name === "AbortError" ? "timeout" : "network", String(err));
  } finally {
    clearTimeout(timer);
  }
}

function showAlert(message) {
  const box = $("alert");
  box.textContent = message;
  box.hidden = false;
}
function clearAlert() {
  $("alert").hidden = true;
  $("alert").textContent = "";
}
function errorText(err) {
  return t().errors[err.code] || t().errors.default;
}

// While a request is in flight every action is ignored, so a double Enter cannot send an answer twice.
function setBusy(value, statusNode, text) {
  busy = value;
  document.querySelectorAll("main button").forEach((b) => { b.disabled = value || b.dataset.locked === "true"; });
  $("main").setAttribute("aria-busy", String(value));
  statusNode.textContent = value ? text : "";
}

// ---- start --------------------------------------------------------------------
function validateStart() {
  const fields = [
    [$("class-code"), t().classCode, true],
    [$("learner-code"), t().learnerCode, true],
    [$("problem"), t().problemLabel, false],
  ];
  for (const [input] of fields) input.removeAttribute("aria-invalid");
  for (const [input, name, isCode] of fields) {
    const value = input.value.trim();
    let problem = "";
    if (!value) problem = fill(t().fieldMissing, { field: name });
    else if (isCode && !CODE.test(value)) problem = fill(t().fieldCode, { field: name });
    if (problem) {
      input.setAttribute("aria-invalid", "true");
      showAlert(problem);
      input.focus();
      return false;
    }
  }
  return true;
}

async function onStart(event) {
  event.preventDefault();
  if (busy) return;
  clearAlert();
  if (!validateStart()) return;
  setBusy(true, $("start-status"), t().starting);
  try {
    const view = await api("POST", "/api/sessions", {
      class_code: $("class-code").value.trim(),
      learner_code: $("learner-code").value.trim(),
      problem: $("problem").value,
      lang,
    });
    sessionId = view.session_id;
    writeStorage(sessionStorage, "tuntas.session", sessionId);
    $("log").replaceChildren();
    renderSession(view);
  } catch (err) {
    showAlert(errorText(err));
    if (err.code === "out_of_scope" || err.code === "unreadable_problem") $("problem").focus();
  } finally {
    setBusy(false, $("start-status"));
    focusCurrentControl();
  }
}

// ---- session ------------------------------------------------------------------
async function act(action, body = {}) {
  if (busy) return;
  clearAlert();
  setBusy(true, $("session-status"), t().checking);
  try {
    const view = await api("POST", `/api/sessions/${sessionId}/${action}`, { ...body, lang });
    if (action === "answer") {
      const mine = el("p", { class: "msg mine" });
      mine.append(el("span", { class: "who" }, t().you), document.createTextNode(body.text));
      $("log").append(mine);
      $("answer").value = "";
    }
    renderSession(view);
  } catch (err) {
    showAlert(errorText(err));
    if (err.code === "session_not_found") resetToStart();
  } finally {
    setBusy(false, $("session-status"));
    focusCurrentControl();
  }
}

function renderSession(view) {
  lastView = view;
  $("start-view").hidden = true;
  $("session-view").hidden = false;
  $("problem-display").textContent = `${view.problem} = 0`;

  $("steps").replaceChildren(...view.steps.map((s) => {
    const li = el("li", { class: s.status }, "");
    li.append(el("span", {}, s.label), el("span", { class: "state" }, t().status[s.status]));
    if (s.status === "current") li.setAttribute("aria-current", "step");
    return li;
  }));

  const log = $("log");
  for (const text of view.messages) log.append(el("p", { class: "msg" }, text));
  while (log.children.length > LOG_LIMIT) log.firstElementChild.remove();

  const kind = view.prompt.kind;
  $("prompt-text").textContent = view.prompt.text;
  $("prompt").classList.toggle("review", kind === "continue");
  $("answer-form").hidden = !["pair", "expression", "roots"].includes(kind);
  $("continue-row").hidden = kind !== "continue";
  $("done-row").hidden = kind !== "none";
  $("answer-help").textContent = t().help[kind] || "";

  const hintBtn = $("hint-btn");
  hintBtn.textContent = view.hints_left > 0 ? fill(t().hintBtn, { n: view.hints_left }) : t().noHints;
  hintBtn.dataset.locked = String(view.hints_left <= 0);
  hintBtn.disabled = view.hints_left <= 0;

  $("mastery").replaceChildren(...view.mastery.map((m) => {
    const wrap = el("div", { class: "meter" });
    const top = el("div", { class: "top" });
    top.append(el("span", {}, m.label), el("strong", {}, `${decimal(m.p)} (${m.mastered ? t().passed : t().belowGate})`));
    const bar = el("div", { class: "bar", "aria-hidden": "true" });
    const fillBar = el("div", { class: `fill${m.mastered ? " pass" : ""}` });
    fillBar.style.width = `${Math.round(m.p * 100)}%`;
    const thr = el("div", { class: "thr" });
    thr.style.left = `${Math.round(view.threshold * 100)}%`;
    bar.append(fillBar, thr);
    wrap.append(top, bar);
    return wrap;
  }));
  $("mastery-note").textContent = fill(t().masteryNote, { thr: decimal(view.threshold) });
  $("hints-note").textContent = fill(t().hintsNote, { n: view.hints_used });
}

function focusCurrentControl() {
  if (!lastView || $("session-view").hidden) return;
  const kind = lastView.prompt.kind;
  const target = kind === "continue" ? $("continue-btn") : kind === "none" ? $("new-btn") : $("answer");
  target.focus();
}

function resetToStart() {
  sessionId = null;
  lastView = null;
  writeStorage(sessionStorage, "tuntas.session", null);
  $("session-view").hidden = true;
  $("start-view").hidden = false;
  $("problem").value = "";
  $("problem").focus();
}

async function resume() {
  if (!sessionId || !/^[0-9a-f]{32}$/.test(sessionId)) return;
  setBusy(true, $("start-status"), t().loadingSession);
  try {
    renderSession(await api("GET", `/api/sessions/${sessionId}?lang=${lang}`));
    focusCurrentControl();
  } catch (err) {
    if (err.code === "session_not_found") {
      writeStorage(sessionStorage, "tuntas.session", null);
      sessionId = null;
    } else {
      showAlert(errorText(err)); // keep the id: a reload after the server is back resumes the session
    }
  } finally {
    setBusy(false, $("start-status"));
  }
}

async function switchLanguage(next) {
  if (next === lang) return;
  lang = next;
  writeStorage(localStorage, "tuntas.lang", lang);
  applyStaticText();
  if (sessionId && !$("session-view").hidden) {
    $("log").replaceChildren();
    try { renderSession(await api("GET", `/api/sessions/${sessionId}?lang=${lang}`)); } catch (err) { showAlert(errorText(err)); }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  applyStaticText();
  $("start-form").addEventListener("submit", onStart);
  $("answer-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = $("answer").value.trim();
    if (!text) { showAlert(t().errors.invalid_answer); $("answer").focus(); return; }
    act("answer", { text });
  });
  $("hint-btn").addEventListener("click", () => act("hint"));
  $("continue-btn").addEventListener("click", () => act("continue"));
  $("new-btn").addEventListener("click", resetToStart);
  document.querySelectorAll("button.lang").forEach((b) => b.addEventListener("click", () => switchLanguage(b.dataset.lang)));
  resume();
});
