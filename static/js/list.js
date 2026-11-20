/* Holosii (Голосій) — фільтри, список фраз, відгук і збереження.
   Звичайний (не модульний) скрипт: файли static/js/* вантажаться по черзі й ділять глобальну область. */
/* ---------- фільтри і список ---------- */
// «Оновлена» = фразу вже слухали/позначали, але її файли змінились пізніше, ніж ти слухав востаннє
function isUpdated(id) {
  const e = S.fb[id], it = S.byId.get(id);
  if (!e || !it || !e.heardAt) return false;
  return it.mtime > e.heardAt + 1;
}
function stateOf(id) {
  const e = S.fb[id];
  if (isUpdated(id)) return "upd";
  return e && e.status ? e.status : (e && e.heard ? "heard" : "new");
}
function matchFilter(it, f) {
  if (f === "all") return true;
  if (f === "upd") return isUpdated(it.id);
  const e = S.fb[it.id];
  if (f === "new") return !e || (!e.heard && !e.status);
  return !!e && e.status === f;
}
function renderFilters() {
  const base = S.items.filter((it) => inLabel(it, S.label));
  $("filters").innerHTML = FILTERS.map(([k, n]) => {
    const c = base.filter((it) => matchFilter(it, k)).length;
    return `<button data-f="${k}" class="${S.filter === k ? "on" : ""}" title="${n}">${n}<span class="n">${c}</span></button>`;
  }).join("");
}
$("filters").addEventListener("click", (e) => {
  const b = e.target.closest("[data-f]"); if (!b) return;
  S.filter = b.dataset.f; saveView(); renderFilters(); renderList(); scrollToSel("center");
});
let qTimer;
$("q").addEventListener("input", () => { clearTimeout(qTimer); qTimer = setTimeout(() => { S.q = $("q").value.trim().toLowerCase(); renderList(); }, 120); });
$("q").addEventListener("keydown", (e) => { if (e.key === "Escape") { $("q").value = ""; S.q = ""; renderList(); $("rows").focus(); } if (e.key === "Enter" || e.key === "ArrowDown") { e.preventDefault(); $("rows").focus(); if (!S.sel && S.visible[0]) select(S.visible[0].id); } });

function statusIcon(id) {
  const j = activeJob(id);
  if (j && j.status === "running") return '<span class="st" style="color:var(--accent)" title="Агент виправляє"><span class="spin"></span></span>';
  if (j && j.status === "queued") return `<span class="st" style="color:var(--text3)" title="У черзі агента">${I.clock}</span>`;
  const st = stateOf(id);
  if (st === "new") return '<span class="st"><span class="dot" title="Ще не прослухано"></span></span>';
  if (st === "heard") return '<span class="st"></span>';
  if (st === "upd") return '<span class="st"><span class="dot red" title="Файл оновлено — ще не прослухано"></span></span>';
  return `<span class="st" style="color:${STATUS[st].color}" title="${STATUS[st].name}">${I[st]}</span>`;
}
function renderList() {
  if (S.view === "queue") { renderQueueList(); return; }
  const q = S.q;
  S.visible = S.items.filter((it) => inLabel(it, S.label) && matchFilter(it, S.filter) &&
    (!q || it.name.toLowerCase().includes(q) || it.text.toLowerCase().includes(q) || it.label.toLowerCase().includes(q) ||
      ((S.fb[it.id] || {}).comment || "").toLowerCase().includes(q)));
  let html = "";
  if (S.label && !q) html += `<div id="fcardWrap">${folderCardHtml(S.label)}</div>`;
  const note = S.label && S.notes[S.label];
  if (note && !q) html += `<div class="note" id="note" title="Клікніть, щоб розгорнути">${esc(note)}</div>`;
  let last = null;
  for (const it of S.visible) {
    if (it.label !== last) {
      last = it.label;
      const shown = S.label && it.label.startsWith(S.label) ? it.label.slice(S.label.length).replace(/^\//, "") : it.label;
      if (shown || S.label === "") html += `<div class="group">${esc(shown ? shown.split("/").join(" › ") : "Корінь папки")}</div>`;
    }
    const sub = (S.fb[it.id] || {}).comment ? "💬 " + S.fb[it.id].comment : firstLine(it.text);
    html += `<div class="row ${it.id === S.sel ? "sel" : ""}" data-id="${esc(it.id)}">
      ${statusIcon(it.id)}<span class="t">${esc(it.name)}</span>
      <span class="tags">${it.files.map((f) => `<span class="tag">${esc((f.tag || "♪").toUpperCase())}</span>`).join("")}</span>
      ${sub ? `<span class="s">${esc(sub)}</span>` : ""}</div>`;
  }
  if (!S.visible.length) html += `<div class="empty">${S.items.length ? "Нічого не знайдено" : "У папці немає аудіофайлів"}</div>`;
  $("rows").innerHTML = html;
}
function updateRow(id) {
  const r = $("rows").querySelector(`.row[data-id="${CSS.escape(id)}"]`); if (!r) return;
  r.querySelector(".st").outerHTML = statusIcon(id);
  const it = S.byId.get(id); const sub = (S.fb[id] || {}).comment ? "💬 " + S.fb[id].comment : firstLine(it.text);
  let s = r.querySelector(".s");
  if (sub) { if (!s) { s = document.createElement("span"); s.className = "s"; r.appendChild(s); } s.textContent = sub; } else if (s) s.remove();
}
$("rows").addEventListener("click", (e) => {
  const n = e.target.closest("#note"); if (n) { n.classList.toggle("open"); return; }
  const r = e.target.closest(".row"); if (r) select(r.dataset.id);
});
function select(id, opts = {}) {
  if (S.sel === id && !opts.force) return;
  const prev = $("rows").querySelector(".row.sel"); if (prev) prev.classList.remove("sel");
  S.sel = id; saveView();
  const r = $("rows").querySelector(`.row[data-id="${CSS.escape(id)}"]`); if (r) r.classList.add("sel");
  scrollToSel("nearest");
  renderDetail();
  if (S.auto) playAll();
}
function scrollToSel(block) {
  const r = S.sel && $("rows").querySelector(`.row[data-id="${CSS.escape(S.sel)}"]`);
  if (r) r.scrollIntoView({ block });
}
function move(d) {
  if (!S.visible.length) return;
  let i = S.visible.findIndex((it) => it.id === S.sel);
  i = i < 0 ? (d > 0 ? 0 : S.visible.length - 1) : Math.max(0, Math.min(S.visible.length - 1, i + d));
  select(S.visible[i].id);
}

/* ---------- відгук і збереження ---------- */
function setFb(id, patch) {
  const e = { ...(S.fb[id] || {}), ...patch };
  for (const k of Object.keys(e)) if (e[k] === null || e[k] === "" || e[k] === false) delete e[k];
  delete e.updated;
  const empty = !Object.keys(e).length;
  if (!empty) { const d = new Date(); e.updated = new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 19); }
  if (empty) delete S.fb[id]; else S.fb[id] = e;
  S.pending[id] = empty ? null : e;
  ls.set("pending." + S.pid, S.pending);
  scheduleSave(350);
}
let saveTimer;
function scheduleSave(ms) { clearTimeout(saveTimer); saveTimer = setTimeout(flush, ms); renderSaveState(); }
async function flush() {
  if (S.saving || !S.pid) return;
  const batch = S.pending; const pid = S.pid;
  if (!Object.keys(batch).length) { renderSaveState(); return; }
  S.saving = true; S.pending = {};
  try {
    const fr = await api("/api/feedback?p=" + encodeURIComponent(pid), { items: batch });
    if (pid === S.pid && fr.folders && JSON.stringify(fr.folders) !== JSON.stringify(S.folders)) {
      S.folders = fr.folders; renderFolders(); if (S.view !== "queue") renderFolderCard();
    }
    S.saveError = false;
    if (pid === S.pid) {
      if (Object.keys(S.pending).length) ls.set("pending." + pid, S.pending); else ls.del("pending." + pid);
    }
    updateBadge();
  } catch {
    S.saveError = true;
    if (pid === S.pid) { S.pending = { ...batch, ...S.pending }; ls.set("pending." + pid, S.pending); }
    clearTimeout(saveTimer); saveTimer = setTimeout(flush, 4000);
  } finally {
    S.saving = false; renderSaveState();
    if (!S.saveError && Object.keys(S.pending).length) scheduleSave(200);
  }
}
function renderSaveState() {
  const el = $("saveState");
  if (!S.pid || !S.project) { el.innerHTML = ""; return; }
  const n = Object.keys(S.pending).length;
  if (S.saveError) { el.className = "save-state err"; el.innerHTML = I.warn + "Немає зв’язку з сервером — зміни тримаю в браузері"; }
  else if (n || S.saving) { el.className = "save-state"; el.innerHTML = "Зберігаю…"; }
  else { el.className = "save-state"; el.innerHTML = I.cloud + "Збережено у «summary.json»"; el.title = S.project.path + "/summary.json"; }
}
function updateBadge() {
  const p = S.projects.find((x) => x.id === S.pid); if (!p) return;
  p.fix = Object.values(S.fb).filter((e) => e.status === "fix").length;
  renderProjects();
}
function setStatus(st) {
  if (!S.sel) return;
  const id = S.sel;
  if (st === "fix") {
    const ta = $("comment"); const comment = ta ? ta.value.trim() : ((S.fb[id] || {}).comment || "").trim();
    if (!comment) { toast("Спершу напиши коментар — що виправити"); if (ta) ta.focus(); return; }
    setFb(id, { status: "fix", comment, heard: true, heardAt: nowSec() });
    afterFbChange();
    enqueue(id, comment);
    return;
  }
  const cur = (S.fb[id] || {}).status;
  setFb(id, { status: cur === st ? null : st, heard: true, heardAt: nowSec() });
  afterFbChange();
}
async function enqueue(id, comment) {
  const p = S.projects.find((x) => x.id === S.pid);
  if (!p || !p.agent) { toast("Позначено «Виправити». Агент для цього проєкту не налаштований"); return; }
  if (!limitsOk()) { toast("Не відправлено — позначка «Виправити» лишилась"); return; }
  try {
    const it = S.byId.get(id);
    const r = await api("/api/queue/add?p=" + encodeURIComponent(S.pid), { item: id, comment, ref: (it && effRef(it)) || "none" });
    await refreshQueue(true);
    const waiting = S.jobs.filter((j) => j.status === "queued");
    const pos = waiting.findIndex((j) => j.id === r.job.id) + 1;
    toast(pos > 0 ? `Відправлено агенту · у черзі ${pos}-а` : "Відправлено агенту");
  } catch (err) { toast(err.message); }
}
function afterFbChange() {
  updateRow(S.sel); renderFilters(); renderFolderCard(); renderFolders();
  document.querySelectorAll(".sbtn").forEach((b) => b.classList.toggle("on", (S.fb[S.sel] || {}).status === b.dataset.st));
}
window.addEventListener("beforeunload", () => {
  if (Object.keys(S.pending).length && S.pid) {
    try { navigator.sendBeacon("/api/feedback?p=" + encodeURIComponent(S.pid), new Blob([JSON.stringify({ items: S.pending })], { type: "application/json" })); } catch {}
  }
});
