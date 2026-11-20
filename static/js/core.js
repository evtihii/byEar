/* Holosii (Голосій) — іконки, стан, проєкти, теки й готовність до вбудовування.
   Звичайний (не модульний) скрипт: файли static/js/* вантажаться по черзі й ділять глобальну область. */
"use strict";
/* ---------- іконки (у стилі SF Symbols) ---------- */
const I = {
  headphones: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="2.5" y="14" width="5" height="7" rx="2" fill="currentColor" stroke="none"/><rect x="16.5" y="14" width="5" height="7" rx="2" fill="currentColor" stroke="none"/></svg>',
  game: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7h10a5 5 0 0 1 4.9 6l-.7 3.4a2.6 2.6 0 0 1-4.6 1.1L15 15.5H9l-1.6 2a2.6 2.6 0 0 1-4.6-1.1L2.1 13A5 5 0 0 1 7 7z"/><path d="M7.5 10v3M6 11.5h3"/><circle cx="16" cy="10.5" r=".6" fill="currentColor"/><circle cx="17.5" cy="12.5" r=".6" fill="currentColor"/></svg>',
  folder: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h4.6l2 2.2h8.4A1.5 1.5 0 0 1 21 8.7v9.8a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5z"/></svg>',
  tray: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M4 13l2.5-7h11L20 13v5.5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5z"/><path d="M4 13h4.5l1 2h5l1-2H20"/></svg>',
  chev: '<svg width="8" height="10" viewBox="0 0 8 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 1.5 6.5 6 2 10.5"/></svg>',
  plus: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  minus: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 12h14"/></svg>',
  refresh: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></svg>',
  search: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m20 20-4.8-4.8"/></svg>',
  play: '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5v15a1 1 0 0 0 1.5.9l12-7.5a1 1 0 0 0 0-1.8l-12-7.5A1 1 0 0 0 7 4.5z"/></svg>',
  pause: '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="5.5" y="4" width="4.5" height="16" rx="1.2"/><rect x="14" y="4" width="4.5" height="16" rx="1.2"/></svg>',
  ok: '<svg width="14" height="14" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="currentColor"/><path d="m7.5 12.3 3 3 6-6.3" fill="none" stroke="var(--window)" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  fix: '<svg width="14" height="14" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="currentColor"/><path d="m8 16 .6-2.6 5.8-5.8 2 2-5.8 5.8zM13.4 8.6l2 2" fill="none" stroke="var(--window)" stroke-width="1.7" stroke-linejoin="round"/></svg>',
  regen: '<svg width="14" height="14" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="currentColor"/><path d="M16.3 10.2A4.6 4.6 0 1 0 16.5 13.5" fill="none" stroke="var(--window)" stroke-width="1.8" stroke-linecap="round"/><path d="M16.8 7.4v3.1h-3.1" fill="none" stroke="var(--window)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  finder: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h4.6l2 2.2h8.4A1.5 1.5 0 0 1 21 8.7v9.8a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5z"/><path d="M9.5 13.5l2 2 3-3.5" stroke-linecap="round"/></svg>',
  auto: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h11M4 12h8M4 17h6"/><path d="M15 12.5v7l5.5-3.5z" fill="currentColor"/></svg>',
  cloud: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 18h10a4 4 0 0 0 .6-8A6 6 0 0 0 6.2 9.5 4.3 4.3 0 0 0 7 18z"/><path d="m9.5 13.5 2 2 3.5-3.5"/></svg>',
  spark: '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5l1.9 5.6 5.6 1.9-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.9z"/><path d="M18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z" opacity=".75"/></svg>',
  compress: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3v5H3M16 3v5h5M8 21v-5H3M16 21v-5h5"/></svg>',
  restart: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12a8 8 0 1 0 2.3-5.7"/><path d="M4 4v4.5h4.5"/></svg>',
  replay: '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="5" width="3" height="14" rx="1"/><path d="M20 5.8v12.4a1 1 0 0 1-1.5.86L9 13a1.2 1.2 0 0 1 0-2l9.5-6.06A1 1 0 0 1 20 5.8z"/></svg>',
  box: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"><path d="M3.5 7.5 12 3l8.5 4.5v9L12 21l-8.5-4.5z"/><path d="M3.5 7.5 12 12l8.5-4.5M12 12v9"/></svg>',
  embtri: '<svg width="15" height="14" viewBox="0 0 24 22"><path d="M10.3 1.9a2 2 0 0 1 3.4 0l9.6 16.6a2 2 0 0 1-1.7 3H2.4a2 2 0 0 1-1.7-3z" fill="currentColor"/><path d="M12 7.2v6.3" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/><circle cx="12" cy="17.2" r="1.45" fill="#fff"/></svg>',
  shipped: '<svg width="14" height="14" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="currentColor"/><path d="m7.5 12.3 3 3 6-6.3" fill="none" stroke="var(--sidebar)" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  logo: '<svg width="16" height="16" viewBox="14 14 92 92"><path d="M29 40Q37 28 45 40M75 40Q83 28 91 40" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><path d="M30 58H90Q90 94 60 94Q30 94 30 58Z" fill="currentColor"/><g fill="#fff"><rect x="41" y="66" width="5" height="10" rx="2.5"/><rect x="50" y="62" width="5" height="20" rx="2.5"/><rect x="59" y="64" width="5" height="16" rx="2.5"/><rect x="68" y="62" width="5" height="20" rx="2.5"/><rect x="77" y="66" width="5" height="10" rx="2.5"/></g></svg>',   /* біла плитка, чорне обличчя з хвилею в роті — та сама фігура, що в mac/make_icon.swift */
  house: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5.5h-5V20H5a1 1 0 0 1-1-1z"/></svg>',
  book: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5zM20 5.5A1.5 1.5 0 0 0 18.5 4H13v16h5.5a1.5 1.5 0 0 0 1.5-1.5z"/></svg>',
  mic: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/></svg>',
  back: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',
  clock: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  queue: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h11M4 12h11M4 18h7"/><path d="M18 14v6M15 17h6" /></svg>',
  warn: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 4.3 2.6 18a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z"/><path d="M12 10v4M12 17.5v.01"/></svg>',
};
const STATUS = {
  ok:    { name: "Готово",         key: "1", color: "var(--green)" },
  fix:   { name: "Виправити",      key: "2", color: "var(--orange)" },
};
const FILTERS = [
  ["all", "Усі"], ["new", "Нові"], ["ok", "Готово"], ["fix", "Виправити"], ["upd", "Оновлені"],
];
/* мітки мов — з сервера (/api/config); тут лише запасні значення */
let SOURCE = ["en","eng","orig","original","src","ref","ja","jp","jpn","old"];
let TARGET = ["ua","uk","ukr","new"];
let LANG_ALIAS = { eng: "en", jp: "ja", jpn: "ja", uk: "ua", ukr: "ua" };
let LANG_NAME = { en: "англійська", ja: "японська", ua: "українська" };
async function loadConfig() {
  try {
    const c = await api("/api/config");
    SOURCE = c.source_tags || SOURCE; TARGET = c.target_tags || TARGET;
    LANG_ALIAS = c.lang_alias || LANG_ALIAS; LANG_NAME = c.lang_names || LANG_NAME;
  } catch {}
}
function langName(code) { const pr = S.projects.find((x) => x.id === S.pid) || {}; return ({ ...LANG_NAME, ...(pr.lang_names || {}) })[code]; }
function canon(tag) { const t = (tag || "").toLowerCase(); return LANG_ALIAS[t] || t; }
/* оригінали фрази (усе, крім доріжки перекладу) */
function originals(it) { const vt = volTarget(it); return it.files.filter((f) => f !== vt && SOURCE.includes((f.tag || "").toLowerCase())); }
/* еталон для агента й нормалізації: вибір фрази → мова проєкту за замовчуванням → перший оригінал; "none" — без еталона */
function effRef(it) {
  const langs = originals(it).map((f) => canon(f.tag)); if (!langs.length) return null;
  const want = (S.fb[it.id] || {}).ref;
  if (want === "none") return null;
  if (want && langs.includes(want)) return want;
  const pr = S.projects.find((x) => x.id === S.pid) || {};
  if (pr.default_ref && langs.includes(pr.default_ref)) return pr.default_ref;
  return langs[0];
}
function refFile(it) { const r = effRef(it); return r ? originals(it).find((f) => canon(f.tag) === r) : null; }
function renderRefRow(it) {
  const row = $("refRow"); if (!row) return;
  const r = effRef(it);
  row.innerHTML = `<span>Еталон для агента:</span>${originals(it).map((f) => { const l = canon(f.tag);
    return `<button class="rb ${l === r ? "on" : ""}" data-ref="${esc(l)}" title="${l === r ? "Вимкнути: агент працюватиме лише за коментарем" : "Агент робитиме «як у цьому оригіналі»"}">${esc(l.toUpperCase())}</button>`; }).join("")}
    <span class="hint">${r ? `«правильно» = як ${esc(langName(r) ? "в " + langName(r).replace(/а$/, "ій") : r.toUpperCase())}` : "не вибрано — лише за коментарем"}</span>`;
  const nb = $("normBtn"); if (nb) nb.textContent = r ? `Нормалізувати як ${r.toUpperCase()}` : "Нормалізувати як еталон";
  if (typeof renderTempoHint === "function") renderTempoHint();
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-ref]"); if (!b || !S.sel) return;
  const it = S.byId.get(S.sel); if (!it) return;
  const l = b.dataset.ref;
  setFb(it.id, { ref: effRef(it) === l ? "none" : l });
  renderRefRow(it);
});

/* ---------- стан ---------- */
const S = {
  projects: [], pid: null, project: null,
  items: [], byId: new Map(), notes: {}, fb: {},
  label: "", filter: "all", q: "",
  visible: [], sel: null,
  pending: {}, saving: false, saveError: false,
  open: {},
  auto: false,
};
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
const ls = {
  get(k, d) { try { const v = localStorage.getItem("sluhach." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("sluhach." + k, JSON.stringify(v)); } catch {} },
  del(k) { try { localStorage.removeItem("sluhach." + k); } catch {} },
};
async function api(path, body) {
  const r = await fetch(path, body === undefined ? { cache: "no-store" }
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || ("Помилка " + r.status));
  return data;
}
function toast(msg, actionLabel, action) {
  const t = $("toast"); t.textContent = msg; t.classList.toggle("act", !!action);
  if (action) { const b = document.createElement("button"); b.textContent = actionLabel; b.onclick = () => { t.classList.remove("show"); action(); }; t.appendChild(b); }
  t.classList.add("show");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("show"), action ? 5000 : 2200);
}
function fileUrl(file) { return "/file?p=" + encodeURIComponent(S.pid) + "&f=" + encodeURIComponent(file.path) + "&v=" + (file.mtime || 0); }
const nowSec = () => Date.now() / 1000;
function firstLine(t) { return (String(t || "").split("\n").find((l) => l.trim()) || "").trim(); }
function plural(n, a, b, c) { const m10 = n % 10, m100 = n % 100; return m10 === 1 && m100 !== 11 ? a : (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? b : c); }

/* ---------- проєкти ---------- */
async function loadProjects() {
  S.projects = await api("/api/projects");
  renderProjects();
  if (S.view === "home") renderHome();
}
function renderProjects() {
  const el = $("projects");
  if (!S.projects.length) { el.innerHTML = '<div class="side-row" style="color:var(--text3)">Немає проєктів</div>'; return; }
  el.innerHTML = S.projects.map((p) => `
    <div class="side-row ${p.id === S.pid ? "sel" : ""} ${p.exists ? "" : "missing"}" data-pid="${p.id}" title="${esc(p.path)}">
      <span class="ic">${I.game}</span><span class="nm">${esc(p.name)}</span>
      ${inSetup(p.id) ? `<span class="badge setup" title="Налаштування проєкту не завершено">${p.setup.running ? '<span class="spin"></span>' : "⚙"}</span>` : p.fix ? `<span class="badge" title="Позначено «виправити»">${p.fix}</span>` : ""}
    </div>`).join("");
  $("removeBtn").disabled = !S.pid;
}
$("projects").addEventListener("click", (e) => {
  const r = e.target.closest("[data-pid]"); if (!r) return;
  if (S.view === "home" && r.dataset.pid === S.pid) { setView(inSetup(S.pid) ? "setup" : "phrases", { restore: false }); return; }
  if (S.view === "setup" && r.dataset.pid === S.pid) return;
  if (S.view === "queue") { setView("phrases"); if (r.dataset.pid === S.pid) return; }   // той самий проєкт — як «Назад»
  if (r.dataset.pid !== S.pid) openProject(r.dataset.pid);
});
$("projects").addEventListener("dblclick", async (e) => {
  const r = e.target.closest("[data-pid]"); if (!r) return;
  const p = S.projects.find((x) => x.id === r.dataset.pid);
  const name = prompt("Нова назва проєкту:", p.name);
  if (name && name.trim()) { await api("/api/projects/rename", { id: p.id, name }); await loadProjects(); }
});

/* проєкт з гри, налаштування якого ще не завершено → вікно налаштування замість списку фраз */
function inSetup(pid) { const p = S.projects.find((x) => x.id === pid); return !!(p && p.setup && p.setup.state !== "done"); }
async function openProject(pid, keepSel) {
  stopAll();
  S.pid = pid; ls.set("lastProject", pid);
  api("/api/state", { last_project: pid }).catch(() => {});
  if (inSetup(pid)) {
    S.project = null; S.items = []; S.byId = new Map(); $("foldersBlock").hidden = true;
    renderProjects();
    if (S.view === "setup") renderSetup(); else setView("setup");
    return;
  }
  loadUsage(false);
  if (S.view === "home" || S.view === "setup") setView("phrases", { restore: false });
  renderProjects();
  $("rows").innerHTML = '<div class="empty">Читаю папку…</div>';
  $("pane").innerHTML = "";
  let data;
  try { data = await api("/api/project?p=" + encodeURIComponent(pid)); }
  catch (err) {
    S.items = []; S.byId = new Map(); S.project = null;
    $("rows").innerHTML = `<div class="empty">${esc(err.message)}</div>`; $("foldersBlock").hidden = true; renderDetail(); return;
  }
  S.project = data.project; S.items = data.items; S.notes = data.notes || {};
  S.byId = new Map(S.items.map((it) => [it.id, it]));
  S.fb = data.feedback || {};
  S.folders = data.folders || {};
  // незбережені зміни з браузера мають пріоритет
  S.pending = ls.get("pending." + pid, {});
  for (const [id, e] of Object.entries(S.pending)) { if (e) S.fb[id] = e; else delete S.fb[id]; }
  if (Object.keys(S.pending).length) scheduleSave(0);
  for (const e of Object.values(S.fb)) {
    if (e.status === "regen") e.status = "fix";           // старі позначки «перегенерувати»
    if ((e.heard || e.status) && !e.heardAt && e.updated) { const t = Date.parse(e.updated + "Z"); if (t) e.heardAt = t / 1000; /* старі записи були в UTC */ }
  }
  S.sig = projectSig(data.items);
  S.open = ls.get("open." + pid, {});
  const view = ls.get("view." + pid, {});
  S.label = view.label && S.items.some((it) => inLabel(it, view.label)) ? view.label : "";
  S.filter = view.filter || "all";
  S.q = ""; $("q").value = "";
  S.sel = keepSel && S.byId.has(keepSel) ? keepSel : (S.byId.has(view.sel) ? view.sel : null);
  renderFolders(); renderFilters(); renderList(); renderDetail(); renderSaveState();
  scrollToSel("center");
}
function projectSig(items) { let m = 0; for (const it of items) m += it.mtime; return items.length + ":" + m.toFixed(2); }
// Перечитати папку, якщо файли змінились (нові дублі агентів, зміна гучності).
// Оновлює час файлів на місці, не скидаючи пошук і вибір. Якщо щось грає чи ти пишеш коментар,
// панель фрази оновиться, щойно звільниться (S.needReload).
async function refreshIfChanged() {
  if (!S.pid || !S.project || refreshIfChanged.busy) return;
  refreshIfChanged.busy = true;
  try {
    const data = await api("/api/project?p=" + encodeURIComponent(S.pid));
    if (projectSig(data.items) === S.sig) { S.needReload = false; return; }
    const sameIds = data.items.length === S.items.length && data.items.every((it, i) => it.id === S.items[i].id);
    const playing = players.some((p) => !p.audio.paused);
    const tag = (document.activeElement && document.activeElement.tagName || "").toLowerCase();
    const typing = tag === "textarea" || tag === "input" || $("sheetBack").classList.contains("show");
    if (!sameIds) {                                   // з'явились чи зникли фрази — перечитати повністю
      if (playing || typing) { S.needReload = true; return; }
      const q = $("q").value;
      await openProject(S.pid, S.sel);
      if (q) { $("q").value = q; S.q = q.trim().toLowerCase(); renderList(); scrollToSel("center"); }
      S.needReload = false; return;
    }
    const changed = [];
    data.items.forEach((n, i) => {
      const o = S.items[i];
      if (n.mtime !== o.mtime || n.text !== o.text) { o.files = n.files; o.mtime = n.mtime; o.text = n.text; changed.push(o.id); }
    });
    S.sig = projectSig(S.items);
    if (S.view !== "queue") { changed.forEach(updateRow); renderFilters(); }
    if (changed.includes(S.sel) && S.view !== "queue") {
      if (playing || typing) S.detailStale = true;    // перемалюємо, щойно звільниться
      else renderDetail();
    }
    S.needReload = false;
    if (changed.length) toast(changed.length === 1 ? "Файл фрази оновився" : `Оновилось фраз: ${changed.length}`);
  } catch {} finally { refreshIfChanged.busy = false; }
}
window.addEventListener("focus", refreshIfChanged);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshIfChanged(); });
function saveView() { if (S.pid) ls.set("view." + S.pid, { label: S.label, filter: S.filter, sel: S.sel }); }

/* ---------- папки (лише орієнтир, без редагування) ---------- */
/* ---------- готовність тек до вбудовування ---------- */
S.folders = {};
function okCount(label) { let n = 0; for (const it of S.items) if (inLabel(it, label) && (S.fb[it.id] || {}).status === "ok") n++; return n; }
function folderProblems(label) {
  const busy = new Set(S.jobs.filter((j) => j.pid === S.pid && (j.status === "queued" || j.status === "running")).map((j) => j.item));
  const n = { fix: 0, unheard: 0, notok: 0, updated: 0, queue: 0 }; let total = 0, ok = 0;
  for (const it of S.items) {
    if (!inLabel(it, label)) continue; total++;
    const e = S.fb[it.id] || {};
    if (busy.has(it.id)) n.queue++;
    if (e.status === "ok") ok++;
    else if (e.status === "fix") n.fix++;
    else if (e.heard) n.notok++; else n.unheard++;
    if (isUpdated(it.id)) n.updated++;
  }
  const words = { fix: "«Виправити»", unheard: "не прослухано", notok: "без «Готово»", updated: "оновлено, не переслухано", queue: "у черзі агента" };
  return { total, ok, list: Object.entries(n).filter(([, v]) => v).map(([k, v]) => `${words[k]}: ${v}`) };
}
function fdate(iso) { return iso ? new Date(iso).toLocaleString("uk-UA", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }) : ""; }
function folderIcon(label) {
  const f = S.folders[label] || {};
  if (f.embedded && (!f.ready || f.embedded >= f.ready)) return `<span class="fst" style="color:var(--green)" title="Вбудовано в гру ${esc(fdate(f.embedded))}. Позначка лишається, доки теку не прибрано.">${I.embtri}</span>`;
  if (f.ready) return `<span class="fst" style="color:var(--orange)" title="Готова до вбудовування з ${esc(fdate(f.ready))}">${I.box}</span>`;
  return "";
}
function folderCardHtml(label) {
  const f = S.folders[label] || {}; const pr = folderProblems(label);
  const pct = pr.total ? Math.round(pr.ok / pr.total * 100) : 0;
  const name = esc(label.split("/").pop());
  if (f.embedded && (!f.ready || f.embedded >= f.ready)) {
    const after = !f.ready && f.unready ? `<div class="why">Після вбудовування щось змінено: ${esc((f.unready.split(" — ")[1]) || "")}. Щоб вбудувати знову, знову познач теку готовою.</div>` : "";
    return `<div class="fcard embedded"><div class="fh"><span style="color:var(--green)">${I.embtri}</span>${name}: вбудовано в гру</div>
      <div>${esc(fdate(f.embedded))}${f.embedded_note ? " · " + esc(f.embedded_note) : ""}. Теку можна прибрати зі прослуховування — позначка лишається, доки її не прибрано.</div>${after}
      ${!f.ready && !pr.list.length ? `<div class="row2"><button class="btn" data-fact="ready">${I.box} Вбудувати знову</button></div>` : ""}</div>`;
  }
  if (f.ready) {
    return `<div class="fcard ready"><div class="fh"><span style="color:var(--orange)">${I.box}</span>${name}: готова до вбудовування</div>
      <div>Позначено ${esc(fdate(f.ready))}. Скажи Claude «вбудуй готові» — він візьме лише такі теки.</div>
      <div class="row2"><button class="link-btn" data-fact="unready">Зняти позначку</button></div></div>`;
  }
  const can = pr.total && !pr.list.length;
  return `<div class="fcard"><div class="fh">${name}: ${pr.ok} з ${pr.total} готові</div>
    <div class="prog"><i style="width:${pct}%"></i></div>
    ${pr.list.length ? `<div class="why">Ще: ${esc(pr.list.join(" · "))}</div>` : ""}
    ${f.embedded ? `<div class="why">Раніше вбудовано ${esc(fdate(f.embedded))}, після цього зміни.</div>` : ""}
    ${f.unready && !can ? `<div class="why">Позначку знято: ${esc((f.unready.split(" — ")[1]) || "")}</div>` : ""}
    <div class="row2"><button class="btn ${can ? "primary" : ""}" data-fact="ready" ${can ? "" : "disabled"} title="${can ? "Позначити теку готовою до вбудовування: усі фрази схвалені" : "Спершу всі фрази мають бути «Готово»"}">${I.box} Вбудувати</button></div></div>`;
}
function renderFolderCard() { const w = $("fcardWrap"); if (w && S.label) w.innerHTML = folderCardHtml(S.label); }
$("rows").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-fact]"); if (!b || !S.label) return;
  const action = b.dataset.fact;
  if (action === "unready" && !confirm("Зняти позначку «готова до вбудовування» з цієї теки?")) return;
  try {
    await flush();
    const r = await api("/api/folder?p=" + encodeURIComponent(S.pid), { label: S.label, action });
    S.folders = r.folders; renderFolders(); renderFolderCard();
    toast(action === "ready" ? "Теку позначено готовою до вбудовування" : "Позначку знято");
  } catch (err) { toast(err.message); }
});
function inLabel(it, label) { return !label || it.label === label || it.label.startsWith(label + "/"); }
function renderFolders() {
  $("foldersBlock").hidden = !S.items.length;
  const counts = new Map();
  for (const it of S.items) {
    if (!it.label) continue;
    const parts = it.label.split("/");
    for (let i = 1; i <= parts.length; i++) { const k = parts.slice(0, i).join("/"); counts.set(k, (counts.get(k) || 0) + 1); }
  }
  const keys = [...counts.keys()];
  const nat = new Intl.Collator("uk", { numeric: true, sensitivity: "base" });
  keys.sort((a, b) => {
    const A = a.split("/"), B = b.split("/");
    for (let i = 0; i < Math.min(A.length, B.length); i++) { const c = nat.compare(A[i], B[i]); if (c) return c; }
    return A.length - B.length;
  });
  const hasKids = new Set(keys.map((k) => k.split("/").slice(0, -1).join("/")).filter(Boolean));
  const visibleKey = (k) => { const p = k.split("/"); for (let i = 1; i < p.length; i++) if (!S.open[p.slice(0, i).join("/")]) return false; return true; };
  let html = `<div class="side-row ${S.label === "" ? "sel" : ""}" data-label=""><span class="chev none"></span><span class="ic">${I.tray}</span><span class="nm">Усі фрази</span><span class="cnt">${S.items.length}</span></div>`;
  for (const k of keys) {
    if (!visibleKey(k)) continue;
    const depth = k.split("/").length - 1;
    const kids = hasKids.has(k);
    html += `<div class="side-row ${S.label === k ? "sel" : ""}" data-label="${esc(k)}" style="padding-left:${8 + depth * 14}px" title="${esc(k)}">
      <span class="chev ${kids ? "" : "none"} ${S.open[k] ? "open" : ""}" data-toggle="${esc(k)}">${I.chev}</span>
      <span class="ic">${I.folder}</span><span class="nm">${esc(k.split("/").pop())}</span>${folderIcon(k)}<span class="cnt" title="Готово / усього">${okCount(k)}/${counts.get(k)}</span></div>`;
  }
  $("folders").innerHTML = html;
}
$("folders").addEventListener("click", (e) => {
  const t = e.target.closest("[data-toggle]");
  if (t && !t.classList.contains("none")) {
    const k = t.dataset.toggle; S.open[k] = !S.open[k]; ls.set("open." + S.pid, S.open); renderFolders(); return;
  }
  const r = e.target.closest("[data-label]"); if (!r) return;
  if (S.view === "queue") setView("phrases", { restore: false });
  S.label = r.dataset.label;
  if (S.label) { const pp = S.label.split("/"); for (let i = 1; i <= pp.length; i++) S.open[pp.slice(0, i).join("/")] = true; ls.set("open." + S.pid, S.open); }
  saveView(); renderFolders(); renderFilters(); renderList(); scrollToSel("center");
});
/* Значок «агент працює» створюється заново при кожному оновленні черги, і обертання починалося б з нуля —
   звідси ривки. Кожен новий значок стає в ту саму фазу, що й годинник, тож перемальовування непомітне. */
const SPIN_MS = 800;
function syncSpin(el) { el.style.animationDelay = `-${Math.round(performance.now() % SPIN_MS)}ms`; }
new MutationObserver((muts) => {
  for (const m of muts) for (const n of m.addedNodes) {
    if (n.nodeType !== 1) continue;
    if (n.classList.contains("spin")) syncSpin(n);
    n.querySelectorAll && n.querySelectorAll(".spin").forEach(syncSpin);
  }
}).observe(document.documentElement, { childList: true, subtree: true });
