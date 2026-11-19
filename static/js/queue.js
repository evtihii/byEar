/* ByEar (наСлух) — черга агента, автоперевірка правок, «до / після».
   Звичайний (не модульний) скрипт: файли static/js/* вантажаться по черзі й ділять глобальну область. */
/* ---------- черга агентів ---------- */
S.view = "phrases"; S.jobs = []; S.jobSel = null; S.jobsSig = "";
const JOB_ST = {
  queued:    ["У черзі", "var(--text3)"],
  running:   ["Агент працює", "var(--accent)"],
  done:      ["Готово — послухай", "var(--green)"],
  error:     ["Помилка", "var(--red)"],
  cancelled: ["Скасовано", "var(--text3)"],
};
function jobsFor(id) { return S.jobs.filter((j) => j.pid === S.pid && j.item === id); }
function activeJob(id) { return jobsFor(id).find((j) => j.status === "running") || jobsFor(id).find((j) => j.status === "queued") || null; }
function lastJob(id) { const a = jobsFor(id); return a.length ? a[a.length - 1] : null; }
function volTarget(it) {
  return it.files.find((f) => TARGET.includes((f.tag || "").toLowerCase()))
    || it.files.find((f) => !SOURCE.includes((f.tag || "").toLowerCase())) || it.files[it.files.length - 1];
}
function editPlayer() { return players.find((p) => p.editable) || null; }
function renderSelInfo() {
  const el = $("selInfo"), p = editPlayer(), it = S.byId.get(S.sel); if (!el || !p || !it) return;
  if (p.sel) el.innerHTML = `Виділено <span class="sel-info">${p.sel[0].toFixed(2)}–${p.sel[1].toFixed(2)} с</span> у <span class="vt">${esc(p.file.name)}</span>:`;
  else el.innerHTML = `Для <span class="vt">${esc(p.file.name)}</span> (потягни по хвилі, щоб виділити шматок):`;
  const sc = $("selClear"); if (sc) sc.hidden = !p.sel;
}
function changeVolume(it) {
  const db = Math.round(Number($("volDb").value));
  if (!db) { toast("Вкажи, на скільки дБ змінити (наприклад 3 або -2)"); $("volDb").focus(); return; }
  editAudio(it, "gain", db);
}
async function editAudio(it, op, db = 0) {
  const p = editPlayer(); const f = p ? p.file : volTarget(it); const sel = p && p.sel ? p.sel : null;
  const ref = refFile(it);
  if (op === "normalize" && !ref && !sel) { toast("Еталон не вибрано — увімкни мову під оригіналом або виділи шматок, і він підлаштується під решту файлу"); return; }
  const busy = (v) => { ["volBtn", "normBtn"].forEach((id) => { const b = $(id); if (b) b.disabled = v; }); if (p && p.bar) p.bar.querySelectorAll("button").forEach((b) => b.disabled = v); };
  busy(true);
  try {
    const body = { f: f.path, op, db };
    if (sel) { body.start = sel[0]; body.end = sel[1]; }
    if (ref) body.ref = ref.path;
    const r = await api("/api/audio-edit?p=" + encodeURIComponent(S.pid), body);
    f.mtime = r.mtime; it.mtime = Math.max(...it.files.map((x) => x.mtime || 0)); S.sig = projectSig(S.items);
    const i = r.info || {}; const where = sel ? `шматок ${sel[0].toFixed(1)}–${sel[1].toFixed(1)} с` : f.name;
    toast(op === "normalize"
      ? `${where}: ${i.before} → ${i.after} ${i.unit} (${ref ? canon(ref.tag).toUpperCase() : "решта файлу"} ${i.en}), ${i.db > 0 ? "+" : ""}${i.db} дБ`
      : `${where}: ${i.db > 0 ? "+" : ""}${i.db} дБ`, "Скасувати ⌘Z", () => undoAudio(false));
    renderDetail(); updateRow(it.id); renderFilters();
    if (sel) { const np = editPlayer(); if (np) setTimeout(() => np.setSel(sel[0], sel[1]), 50); }
  } catch (err) { toast(err.message); busy(false); }
}
async function undoAudio(redo) {
  const it = S.byId.get(S.sel); const p = editPlayer(); if (!it || !p) return;
  const f = p.file; const sel = p.sel;
  try {
    const r = await api("/api/audio-undo?p=" + encodeURIComponent(S.pid), { f: f.path, redo });
    f.mtime = r.mtime; it.mtime = Math.max(...it.files.map((x) => x.mtime || 0)); S.sig = projectSig(S.items);
    renderDetail(); updateRow(it.id); renderFilters();
    if (sel) { const np = editPlayer(); if (np) setTimeout(() => np.setSel(sel[0], sel[1]), 50); }
    const h = r.history;
    toast(`${redo ? "Повторено" : "Скасовано"} · ще можна скасувати ${h.undo}, повторити ${h.redo}`,
      redo ? "Скасувати ⌘Z" : "Повторити ⇧⌘Z", () => undoAudio(!redo));
  } catch (err) { toast(err.message); }
}
function jobLine(j) {
  const [n, c] = JOB_ST[j.status] || [j.status, "var(--text3)"];
  const icon = j.status === "running" ? '<span class="spin"></span>' : j.status === "queued" ? I.clock : "";
  return `<span class="chip ${j.status === "running" ? "run" : j.status === "error" ? "err" : ""}" style="color:${c}">${icon}${n}</span>`;
}
function renderJobInfo() {
  const chip = $("jobChip"), card = $("agentCard"); if (!chip || !card || !S.sel) return;
  const a = activeJob(S.sel), l = lastJob(S.sel);
  if (a) {
    const pos = S.jobs.filter((j) => j.status === "queued").findIndex((j) => j.id === a.id) + 1;
    chip.innerHTML = jobLine(a) + (a.status === "queued" && pos ? `<span class="chip">· ${pos}-а в черзі</span>` : "")
      + ` <button class="link-btn" data-jobopen="${a.id}">деталі</button>`
      + ` <button class="link-btn danger" data-jobcancel="${a.id}" title="${a.status === "running" ? "Зупинити агента й прибрати позначку «Виправити»" : "Прибрати з черги й зняти позначку «Виправити»"}">${a.status === "running" ? "зупинити" : "прибрати з черги"}</button>`;
  } else chip.innerHTML = l ? ` <button class="link-btn" data-jobopen="${l.id}">остання правка агента</button>` : "";
  const show = l && (l.status === "done" || l.status === "error") && l.result;
  const cost = l && (l.tokens || l.cost != null)
    ? `<span class="cost">${l.tokens ? Math.round(l.tokens / 1000) + " тис. токенів" : ""}${l.cost != null ? ` · ≈$${Number(l.cost).toFixed(2)}` : ""}</span>` : "";
  card.innerHTML = show ? `<div class="agent-card"><div class="h">${l.status === "error" ? "АГЕНТ: ПОМИЛКА" : "ВІДПОВІДЬ АГЕНТА"} · ${esc((l.finished || "").replace("T", " ").slice(5, 16))}${cost}</div>${esc(l.result)}${checkHtml(l)}</div>` : "";
}
/* ---------- випадкове «Виправити»: прибрати фразу з черги прямо з картки ---------- */
document.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-jobcancel]"); if (!b) return;
  const j = S.jobs.find((x) => x.id === b.dataset.jobcancel); if (!j) return;
  if (j.status === "running" && !confirm("Агент уже працює над цією фразою. Зупинити його?\nЯкщо він встиг змінити файл, ⌘Z поверне версію до правки.")) return;
  b.disabled = true;
  try {
    await api("/api/queue/cancel", { id: j.id });
    const it = j.item; const prev = (S.fb[it] || {}).status;
    if (prev === "fix") { setFb(it, { status: null }); afterFbChange(); }
    await refreshQueue(true); renderJobInfo();
    toast(j.status === "running" ? "Агента зупинено, позначку «Виправити» знято" : "Прибрано з черги, позначку «Виправити» знято",
      "Повернути", () => { if (S.sel === it) setStatus("fix"); else toast("Відкрий фразу й натисни «Виправити» ще раз"); });
  } catch (err) { toast(err.message); b.disabled = false; }
});
/* ---------- автоперевірка правки агента: виміри проти еталона, «до / після» ---------- */
function checkHtml(j) {
  const c = j.check; if (!c) return "";
  if (c.changed === false) return `<div class="chk">Агент файл не змінив.</div>`;
  const row = (name, m, ref) => {
    if (!m) return "";
    const d = (k, unit, rel, tol) => {
      const v = m[k]; if (v == null) return "<td>—</td>";
      const r = ref && ref[k]; const bad = r != null && m !== ref && (rel ? Math.abs(v - r) / r > tol : Math.abs(v - r) > tol);
      return `<td class="${bad ? "bad" : ""}">${v}${unit}</td>`;
    };
    return `<tr><td>${name}</td>${d("f0", " Гц", true, 0.2)}${d("lufs", " LUFS", false, 3)}${d("dur", " с", true, 0.15)}</tr>`;
  };
  const ref = c.ref; const rl = (c.ref_lang || "").toUpperCase();
  const w = c.warnings || [];
  return `<div class="chk">
    <table><tr><th></th><th>висота</th><th>гучність</th><th>довжина</th></tr>
      ${row("Нова версія", c.new, ref)}${row("До правки", c.before, ref)}${ref ? row("Еталон " + esc(rl), ref, null) : ""}</table>
    ${ref ? (w.length ? `<div class="warn">Помітна різниця з еталоном: ${esc(w.join("; "))}.</div>` : `<div class="ok">Висота, гучність і довжина близькі до еталона.</div>`) : "<div>Еталона не було — порівняння лише з версією до правки.</div>"}
    ${j.before_file ? `<div class="acts"><button data-before="${esc(j.id)}">▶ До правки</button><span>⌘Z — повернути версію до правки</span></div>` : ""}
  </div>`;
}
let beforeAudio = null;
function stopBefore() { if (beforeAudio) { beforeAudio.pause(); beforeAudio = null; } document.querySelectorAll("[data-before].on").forEach((b) => { b.classList.remove("on"); b.textContent = "▶ До правки"; }); }
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-before]"); if (!b) return;
  if (b.classList.contains("on")) { stopBefore(); return; }
  stopBefore(); players.forEach((p) => p.stop && p.audio.pause());
  beforeAudio = new Audio("/api/before?id=" + encodeURIComponent(b.dataset.before));
  beforeAudio.onended = stopBefore;
  beforeAudio.play().catch(() => { toast("Не вдалося відтворити версію до правки"); stopBefore(); });
  b.classList.add("on"); b.textContent = "■ Зупинити";
});
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-jobopen]"); if (!b) return;
  S.jobSel = b.dataset.jobopen; setView("queue");
});

async function refreshQueue(force) {
  let st; try { st = await api("/api/queue"); } catch { return; }
  const prev = new Map(S.jobs.map((j) => [j.id, j.status]));
  S.jobs = st.jobs; S.qsettings = st.settings; renderRail(st.agent);
  const sig = S.jobs.map((j) => j.id + j.status).join(",");
  const changed = sig !== S.jobsSig; S.jobsSig = sig;
  const active = S.jobs.filter((j) => j.status === "queued" || j.status === "running").length;
  $("queueBadge").innerHTML = active ? `<span class="badge" style="background:var(--accent)">${active}</span>` : "";
  if (S.needReload) refreshIfChanged();
  if (S.detailStale && S.view !== "queue") {
    const tag = (document.activeElement && document.activeElement.tagName || "").toLowerCase();
    if (!players.some((p) => !p.audio.paused) && tag !== "textarea" && tag !== "input") { S.detailStale = false; renderDetail(); }
  }
  if (!changed && !force) { if (S.view === "queue") refreshLog(); return; }
  const finishedHere = S.jobs.some((j) => j.pid === S.pid && (j.status === "done" || j.status === "error") && prev.get(j.id) !== j.status);
  if (finishedHere) { S.needReload = true; refreshIfChanged(); }
  if (S.view === "queue") { renderQueueList(); renderJobDetail(); return; }
  for (const j of S.jobs) if (j.pid === S.pid && (prev.get(j.id) !== j.status)) updateRow(j.item);
  renderJobInfo();
}
setInterval(refreshQueue, 3000);
