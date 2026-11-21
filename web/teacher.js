"use strict";

const UI = {
  en: {
    pageTitle: "TUNTAS: teacher view",
    skip: "Skip to the class table",
    tagline: "Teacher view: where each learner needs help",
    learnerLink: "Learner view",
    classTitle: "Your class",
    classCode: "Class code",
    loadBtn: "Show class",
    loading: "Loading class…",
    resultTitle: "Class {code}: {n} learners",
    legend: "Mastery below {thr} has not passed the gate yet. Hints per step above 1 suggests a learner is leaning on hints.",
    empty: "No sessions yet for class {code}. Learners appear here after they start a problem with this class code.",
    colLearner: "Learner", colProblem: "Problem", colStep: "Current step", colWeakest: "Weakest concept",
    colHints: "Hints (per step)", colFlags: "Needs help", colUpdated: "Last activity",
    finished: "finished", none: "none", notAssessed: "not assessed yet",
    refreshed: "Updated {time}. Refreshes every 30 seconds while this page is open.",
    flag: "{concept} (at {step})",
    badCode: "Class codes use 2 to 20 letters, digits, - or _.",
    errors: {
      network: "Could not reach the TUNTAS server. Check that it is running, then try again.",
      timeout: "The server took too long to answer. Try again.",
      default: "Something went wrong. Try again.",
    },
  },
  id: {
    pageTitle: "TUNTAS: tampilan guru",
    skip: "Langsung ke tabel kelas",
    tagline: "Tampilan guru: di mana tiap siswa perlu bantuan",
    learnerLink: "Tampilan siswa",
    classTitle: "Kelasmu",
    classCode: "Kode kelas",
    loadBtn: "Tampilkan kelas",
    loading: "Memuat kelas…",
    resultTitle: "Kelas {code}: {n} siswa",
    legend: "Penguasaan di bawah {thr} belum lulus gerbang. Petunjuk per langkah di atas 1 menandakan siswa terlalu bergantung pada petunjuk.",
    empty: "Belum ada sesi untuk kelas {code}. Siswa muncul di sini setelah memulai soal dengan kode kelas ini.",
    colLearner: "Siswa", colProblem: "Soal", colStep: "Langkah saat ini", colWeakest: "Konsep terlemah",
    colHints: "Petunjuk (per langkah)", colFlags: "Perlu bantuan", colUpdated: "Aktivitas terakhir",
    finished: "selesai", none: "tidak ada", notAssessed: "belum dinilai",
    refreshed: "Diperbarui {time}. Diperbarui otomatis tiap 30 detik selama halaman ini terbuka.",
    flag: "{concept} (di {step})",
    badCode: "Kode kelas terdiri dari 2 sampai 20 huruf, angka, - atau _.",
    errors: {
      network: "Server TUNTAS tidak bisa dihubungi. Pastikan server berjalan, lalu coba lagi.",
      timeout: "Server terlalu lama menjawab. Coba lagi.",
      default: "Terjadi kesalahan. Coba lagi.",
    },
  },
};

const CODE = /^[A-Za-z0-9_-]{2,20}$/;
const REFRESH_MS = 30000;
const { fill, readStorage, writeStorage } = window.TuntasCommon;

let lang = readStorage(localStorage, "tuntas.lang") === "id" ? "id" : "en";
let lastCode = null;

const $ = (id) => document.getElementById(id);
const t = () => UI[lang];
const decimal = (value) => window.TuntasCommon.decimal(lang, value);

function applyStaticText() {
  window.TuntasCommon.applyStaticText(t(), lang);
}

function cell(text, cls) {
  const td = document.createElement("td");
  td.textContent = text;
  if (cls) td.className = cls;
  return td;
}

function formatTime(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString(lang === "id" ? "id-ID" : "en-GB");
}

function render(data) {
  $("result").hidden = false;
  $("result-h").textContent = fill(t().resultTitle, { code: data.class_code, n: data.learners.length });
  $("legend").textContent = fill(t().legend, { thr: decimal(data.threshold) });
  const hasRows = data.learners.length > 0;
  $("empty").hidden = hasRows;
  $("table-wrap").hidden = !hasRows;
  $("empty").textContent = hasRows ? "" : fill(t().empty, { code: data.class_code });
  $("rows").replaceChildren(...data.learners.map((l) => {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = l.learner_code;
    const flags = l.flags.length
      ? l.flags.map((f) => fill(t().flag, { concept: f.concept_label, step: f.step_label })).join("; ")
      : t().none;
    tr.append(
      th,
      cell(`${l.problem} = 0`, "nowrap"),
      cell(l.done ? t().finished : l.step_label),
      cell(l.weakest ? `${l.weakest.label} (${decimal(l.weakest.p)})` : t().notAssessed),
      cell(l.hint_dependency === null ? String(l.hints_used) : `${l.hints_used} (${decimal(l.hint_dependency)})`),
      cell(flags, l.flags.length ? "flag" : ""),
      cell(formatTime(l.updated_at)),
    );
    return tr;
  }));
}

async function load(code, { quiet = false } = {}) {
  const alertBox = $("alert");
  if (!quiet) {
    alertBox.hidden = true;
    $("load-btn").disabled = true;
    $("main").setAttribute("aria-busy", "true");
    $("status").textContent = t().loading;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(`/api/classes/${encodeURIComponent(code)}?lang=${lang}`, { signal: controller.signal });
    if (!res.ok) throw new Error("default");
    render(await res.json());
    lastCode = code;
    alertBox.hidden = true;
    $("refreshed").textContent = fill(t().refreshed, { time: new Date().toLocaleTimeString(lang === "id" ? "id-ID" : "en-GB") });
  } catch (err) {
    const key = err.name === "AbortError" ? "timeout" : err instanceof TypeError ? "network" : "default";
    alertBox.textContent = t().errors[key];
    alertBox.hidden = false;
  } finally {
    clearTimeout(timer);
    if (!quiet) {
      $("load-btn").disabled = false;
      $("main").setAttribute("aria-busy", "false");
      $("status").textContent = "";
    }
  }
}

// Background refresh is silent (no status text) so screen readers are not interrupted every 30 seconds.
setInterval(() => {
  if (lastCode && document.visibilityState === "visible") load(lastCode, { quiet: true });
}, REFRESH_MS);

document.addEventListener("DOMContentLoaded", () => {
  applyStaticText();
  $("class-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("class-code");
    const code = input.value.trim();
    if (!CODE.test(code)) {
      input.setAttribute("aria-invalid", "true");
      $("alert").textContent = t().badCode;
      $("alert").hidden = false;
      input.focus();
      return;
    }
    input.removeAttribute("aria-invalid");
    load(code);
  });
  document.querySelectorAll("button.lang").forEach((b) => b.addEventListener("click", () => {
    lang = b.dataset.lang;
    writeStorage(localStorage, "tuntas.lang", lang);
    applyStaticText();
    if (lastCode) load(lastCode);
  }));
});
