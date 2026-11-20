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
/* темп без зміни висоти: opts.pct — зміна довжини у % (мінус — коротше), opts.fit — довжина як в еталоні */
async function editTempo(it, opts) {
  const p = editPlayer(); const f = p ? p.file : volTarget(it); const sel = p && p.sel ? p.sel : null;
  const body = { f: f.path, op: "tempo" };
  if (opts.fit) {
    if (sel) { toast("Під еталон підганяється весь файл — зніми виділення (Esc)"); return; }
    const ref = refFile(it); if (!ref) { toast("Еталон не вибрано — увімкни мову під оригіналом"); return; }
    body.fit_ref = true; body.ref = ref.path;
  } else {
    const k = 1 + opts.pct / 100;
    if (k < 0.5 || k > 2) { toast("Можна від −50% до +100% довжини"); return; }
    body.speed = 1 / k;
  }
  if (sel) { body.start = sel[0]; body.end = sel[1]; }
  const ids = ["tempoBtn", "fitBtn", "volBtn", "normBtn"]; const busy = (v) => { ids.forEach((id) => { const b = $(id); if (b) b.disabled = v; }); if (p && p.bar) p.bar.querySelectorAll("button").forEach((b) => b.disabled = v); };
  busy(true);
  try {
    const r = await api("/api/audio-edit?p=" + encodeURIComponent(S.pid), body);
    f.mtime = r.mtime; it.mtime = Math.max(...it.files.map((x) => x.mtime || 0)); S.sig = projectSig(S.items);
    const i = r.info || {}; const where = sel ? `шматок ${sel[0].toFixed(1)}–${sel[1].toFixed(1)} с` : f.name;
    toast(`${where}: темп ×${i.speed} · файл ${i.before} → ${i.after} с, висота та сама`, "Скасувати ⌘Z", () => undoAudio(false));
    renderDetail(); updateRow(it.id); renderFilters();          // виділення скидається: після зміни темпу час зсунувся
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
  const cost = l ? costHtml(l) : "";
  card.innerHTML = show ? `<div class="agent-card"><div class="h">${l.status === "error" ? "АГЕНТ: ПОМИЛКА" : "ВІДПОВІДЬ АГЕНТА"} · ${esc((l.finished || "").replace("T", " ").slice(5, 16))}</div>${cost}${esc(l.result)}${checkHtml(l)}</div>` : "";
}
/* ---------- ціна правки: агент (токени, $) і генерація (кредити сервісу, напр. ElevenLabs) ---------- */
function costParts(j) {
  const out = [];
  if (j.tokens) out.push(`Claude: ${Math.round(j.tokens / 1000)} тис. токенів${j.cost != null ? ` · ≈$${Number(j.cost).toFixed(2)}` : ""}`);
  else if (j.cost != null) out.push(`Claude: ≈$${Number(j.cost).toFixed(2)}`);
  if (j.usage) out.push(`${j.usage.label}: ${Number(j.usage.spent).toLocaleString("uk-UA")} кредитів`);
  return out;
}
function costHtml(j) { const p = costParts(j); return p.length ? `<div class="cost">${p.map(esc).join(" &nbsp;·&nbsp; ")}</div>` : ""; }
/* залишок кредитів сервісу генерації — на лівій смужці */
async function loadUsage(fresh) {
  const box = $("railUsage"); if (!box) return;
  if (!S.pid) { box.hidden = true; return; }
  let u = null;
  try { u = (await api("/api/usage?p=" + encodeURIComponent(S.pid) + (fresh ? "&fresh=1" : ""))).usage; } catch {}
  if (!u) { box.hidden = true; return; }
  box.hidden = false;
  $("railUsageLbl").textContent = u.label;
  if (u.error || u.used == null) { $("railUsageNum").textContent = "?"; box.title = `${u.label}: не вдалося дізнатися залишок (${u.error || ""})`; return; }
  const left = u.limit != null ? u.limit - u.used : null;
  $("railUsageNum").textContent = left == null ? kfmt(u.used) : kfmt(left);
  box.classList.toggle("low", left != null && u.limit && left / u.limit < 0.1);
  box.title = `${u.label}: використано ${u.used.toLocaleString("uk-UA")}${u.limit ? " з " + u.limit.toLocaleString("uk-UA") : ""} кредитів`
    + (u.reset ? `\nОновлення: ${new Date(u.reset * 1000).toLocaleDateString("uk-UA", { day: "numeric", month: "long" })}` : "");
}
setInterval(() => loadUsage(false), 5 * 60 * 1000);
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
  const ref = c.ref, bef = c.before; const rl = (c.ref_lang || "").toUpperCase();
  // висота — проти версії до правки (той самий голос); гучність і довжина — проти еталона
  const base = { f0: bef, lufs: ref, dur: ref };
  const cell = (m, k, unit, rel, tol, isNew, dim) => {
    const v = m && m[k]; if (v == null) return "<td>—</td>";
    const b = isNew && base[k] && base[k][k];
    const bad = b != null && (rel ? Math.abs(v - b) / b > tol : Math.abs(v - b) > tol);
    return `<td class="${bad ? "bad" : ""}${dim ? " dim" : ""}"${dim ? ' title="Інший актор — висота лише для довідки"' : ""}>${v}${unit}</td>`;
  };
  const row = (name, m, isNew, refRow) => m ? `<tr><td>${name}</td>${cell(m, "f0", " Гц", true, 0.2, isNew, refRow)}${cell(m, "lufs", " LUFS", false, 3, isNew)}${cell(m, "dur", " с", true, 0.15, isNew)}</tr>` : "";
  const w = c.warnings || [];
  const okText = ref ? "Висота як до правки; гучність і довжина близькі до еталона." : "Висота як до правки. Еталона не було — гучність і довжину ні з чим не порівнювала.";
  return `<div class="chk">
    <table><tr><th></th><th title="Порівнюється з версією до правки">висота</th><th title="Порівнюється з еталоном">гучність</th><th title="Порівнюється з еталоном">довжина</th></tr>
      ${row("Нова версія", c.new, true)}${row("До правки", bef)}${ref ? row("Еталон " + esc(rl), ref, false, true) : ""}</table>
    ${w.length ? `<div class="warn">Помітна різниця: ${esc(w.join("; "))}.</div>` : `<div class="ok">${okText}</div>`}
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
  if (finishedHere) { S.needReload = true; refreshIfChanged(); loadUsage(true); }
  if (S.view === "queue") { renderQueueList(); renderJobDetail(); return; }
  for (const j of S.jobs) if (j.pid === S.pid && (prev.get(j.id) !== j.status)) updateRow(j.item);
  renderJobInfo();
}
setInterval(refreshQueue, 3000);
