/* ByEar (наСлух) — головна сторінка.
   Звичайний (не модульний) скрипт: файли static/js/* вантажаться по черзі й ділять глобальну область. */
/* ---------- головна сторінка ---------- */
const DOCS_URL = "";   // посилання на документацію — поки порожнє
function renderHome() {
  const last = ls.get("lastProject");
  const cards = S.projects.map((p) => `
    <div class="pcard ${p.exists ? "" : "missing"}" data-open="${p.id}" title="${esc(p.path)}">
      <div class="pt"><span class="gi">${I.game}</span>${esc(p.name)}${p.id === last ? '<span class="last">ОСТАННІЙ</span>' : ""}</div>
      <div class="pp">${esc(p.path)}${p.exists ? "" : " — теки немає"}</div>
      <div class="ps">
        <span title="Прослухано">${I.headphones} <b>${p.heard || 0}</b></span>
        <span title="Готово" style="color:var(--green)">✓ <b>${p.ok || 0}</b></span>
        <span title="Виправити" style="color:var(--orange)">✎ <b>${p.fix || 0}</b></span>
        ${p.ready_folders ? `<span title="Теки, готові до вбудовування" style="color:var(--orange)">${I.box} <b>${p.ready_folders}</b></span>` : ""}
        ${p.embedded_folders ? `<span title="Вбудовані теки" style="color:var(--green)">${I.embtri} <b>${p.embedded_folders}</b></span>` : ""}
      </div>
      ${p.last_change ? `<div class="pp">Остання позначка: ${esc(fdate(p.last_change))}</div>` : ""}
    </div>`).join("");
  $("home").innerHTML = `<div class="home-in">
    <div class="home-top"><div class="big-icon">${I.headphones.replace('width="13" height="13"', 'width="30" height="30"')}</div>
      <div><h1>наСлух</h1><p>ByEar — прослуховування й правка озвучки ігор</p></div><span class="grow"></span>
      <a class="doc-link ${DOCS_URL ? "on" : ""}" ${DOCS_URL ? `href="${DOCS_URL}" target="_blank" rel="noopener"` : 'title="Документація ще не готова"'}>${I.book} Документація</a></div>
    <div class="home-h">Проєкти</div>
    <div class="pgrid">${cards}<div class="pcard add" id="homeAdd">${I.plus}&nbsp; Новий проєкт</div></div>
  </div>`;
}
$("home").addEventListener("click", async (e) => {
  if (e.target.closest("#homeAdd")) { openSheet(); return; }
  const c = e.target.closest("[data-open]"); if (!c) return;
  const id = c.dataset.open;
  if (id === S.pid && S.project) setView("phrases", { restore: false }); else await openProject(id);
});
const AG_ST = { stopped: "зупинено", starting: "запуск…", idle: "вільний", working: "працює", compacting: "стискає…", error: "помилка" };
function kfmt(n) { return n == null ? "—" : n >= 1000 ? Math.round(n / 1000) + "к" : String(n); }
function renderRail(a) {
  if (!a) return; S.agent = a;
  const max = a.auto_compact_at || 200000, frac = a.ctx ? Math.min(1, a.ctx / max) : 0;
  $("railNum").textContent = kfmt(a.ctx);
  $("railMax").textContent = a.auto_compact_at ? "з " + kfmt(a.auto_compact_at) : "";
  const f = $("railFill"); f.style.height = (frac * 100).toFixed(1) + "%";
  f.style.background = frac < .6 ? "var(--green)" : frac < .9 ? "var(--orange)" : "var(--red)";
  $("railDot").className = "sd " + a.state;
  let st = AG_ST[a.state] || a.state;
  if (a.compact_requested && a.state === "working") st = "стисну після правки";
  $("railState").textContent = st;
  const lc = a.last_compact ? `\nОстаннє стиснення: ${a.last_compact.time.slice(11, 16)}, було ${kfmt(a.last_compact.before)}` : "";
  $("rail").title = `Модель: ${a.model}\nКонтекст: ${a.ctx == null ? "ще невідомо" : a.ctx.toLocaleString("uk-UA") + " токенів"}`
    + (a.auto_compact_at ? `\nАвтостиснення на ${a.auto_compact_at.toLocaleString("uk-UA")}` : "")
    + `\nПравок за цей запуск: ${a.jobs}\nВартість за цінами API: ≈$${(a.cost || 0).toFixed(2)}${lc}` + (a.error ? "\nПомилка: " + a.error : "");
  $("compactBtn").disabled = a.ctx == null || a.state === "compacting" || a.compact_requested || !a.claude;
  $("restartBtn").disabled = a.state === "working" || a.state === "compacting" || !a.claude;
}
$("compactBtn").onclick = async () => {
  try { await api("/api/agent/compact", {}); toast(S.agent && S.agent.state === "working" ? "Стисну, щойно агент закінчить правку" : "Стискаю контекст агента…"); refreshQueue(true); }
  catch (err) { toast(err.message); }
};
$("restartBtn").onclick = async () => {
  if (!confirm("Почати з новим агентом?\n\nПоточний агент забуде все, що робив за цей запуск. Черга й файли не зміняться.")) return;
  try { await api("/api/agent/restart", {}); toast("Запущено нового агента"); refreshQueue(true); } catch (err) { toast(err.message); }
};
function setView(v, opts = {}) {
  if (v === S.view && v !== "queue") return;
  if (v === "queue" && S.view !== "queue") {
    S.back = { view: S.view, label: S.label, filter: S.filter, sel: S.sel, q: $("q").value, scroll: $("rows").scrollTop };
  }
  S.view = v;
  $("backBtn").hidden = v !== "queue";
  document.querySelector(".app").classList.toggle("home", v === "home");
  $("homeRow").classList.toggle("sel", v === "home");
  if (v === "home") {
    stopAll(); $("queueRow").classList.remove("sel");
    $("projects").querySelectorAll(".sel").forEach((x) => x.classList.remove("sel"));
    $("folders").querySelectorAll(".sel").forEach((x) => x.classList.remove("sel"));
    renderHome(); return;
  }
  $("queueRow").classList.toggle("sel", v === "queue");
  document.querySelector(".filters").style.display = v === "queue" ? "none" : "";
  $("q").placeholder = v === "queue" ? "Пошук у черзі" : "Пошук у назвах і тексті";
  const back = v !== "queue" && opts.restore !== false ? S.back : null;
  $("q").value = back ? back.q : ""; S.q = $("q").value.trim().toLowerCase();
  if (back) { S.label = back.label; S.filter = back.filter; if (back.sel && S.byId.has(back.sel)) S.sel = back.sel; }
  if (v === "queue") { stopAll(); $("projects").querySelectorAll(".sel").forEach((x) => x.classList.remove("sel")); $("folders").querySelectorAll(".sel").forEach((x) => x.classList.remove("sel")); renderQueueList(); renderJobDetail(); }
  else {
    renderProjects(); renderFolders(); renderFilters(); renderList(); renderDetail();
    if (back && back.scroll != null) $("rows").scrollTop = back.scroll; else scrollToSel("center");
  }
}
function goBack() { if (S.view === "queue") setView(S.back && S.back.view === "home" ? "home" : "phrases"); }
$("backBtn").onclick = goBack;
$("queueRow").onclick = () => (S.view === "queue" ? goBack() : setView("queue"));
$("homeRow").onclick = () => setView("home");
$("sideHead").onclick = () => setView("home");

function visibleJobs() {
  const q = S.q; const order = { running: 0, queued: 1, error: 2, done: 3, cancelled: 4 };
  return S.jobs.filter((j) => !q || (j.name + j.comment + j.project + (j.result || "")).toLowerCase().includes(q))
    .slice().sort((a, b) => (order[a.status] - order[b.status]) || (a.status === "queued" ? (a.created < b.created ? -1 : 1) : (b.created < a.created ? -1 : 1)));
}
function renderQueueList() {
  const list = visibleJobs(); const rows = $("rows"); const st = rows.scrollTop;
  let html = "", last = null;
  for (const j of list) {
    const g = j.status === "running" || j.status === "queued" ? "Зараз" : "Завершені";
    if (g !== last) { last = g; html += `<div class="group">${g}</div>`; }
    const [n, c] = JOB_ST[j.status];
    const icon = j.status === "running" ? '<span class="spin"></span>' : j.status === "queued" ? I.clock
      : j.status === "done" ? I.ok : j.status === "error" ? I.warn : I.minus;
    html += `<div class="row ${j.id === S.jobSel ? "sel" : ""}" data-job="${j.id}">
      <span class="st" style="color:${c}" title="${n}">${icon}</span><span class="t">${esc(j.name)}</span>
      <span class="tags"><span class="tag">${esc(j.project)}</span></span>
      <span class="s">💬 ${esc(j.comment)}</span></div>`;
  }
  if (!list.length) html = `<div class="empty">Черга порожня.<br><br>Напиши коментар до фрази й натисни «Виправити» — агент візьме її в роботу.</div>`;
  rows.innerHTML = html; rows.scrollTop = st;
}
$("rows").addEventListener("click", (e) => {
  const r = e.target.closest("[data-job]"); if (!r) return;
  S.jobSel = r.dataset.job; renderQueueList(); renderJobDetail();
});
function moveJob(d) {
  const list = visibleJobs(); if (!list.length) return;
  let i = list.findIndex((j) => j.id === S.jobSel); i = i < 0 ? 0 : Math.max(0, Math.min(list.length - 1, i + d));
  S.jobSel = list[i].id; renderQueueList(); renderJobDetail();
  const r = $("rows").querySelector(".row.sel"); if (r) r.scrollIntoView({ block: "nearest" });
}
function renderJobDetail() {
  const pane = $("pane"); const j = S.jobs.find((x) => x.id === S.jobSel);
  $("revealBtn").disabled = true;
  if (!j) {
    const s = S.qsettings || {};
    const act = S.jobs.filter((x) => x.status === "running").length, wait = S.jobs.filter((x) => x.status === "queued").length;
    pane.style.display = "flex";
    pane.innerHTML = `<div class="placeholder"><div><h2>Черга правок</h2>Агент ${act ? "працює" : "вільний"}, у черзі ${wait}.<br>Один агент на запуск наСлуху, модель ${esc(s.model || "")}.<br>Розмір його контексту — на смужці зліва; автостиснення на ${kfmt(s.auto_compact_at)}.<br><br>${S.jobs.some((x) => x.status === "done" || x.status === "cancelled") ? '<button class="btn" id="clearDone">Прибрати завершені</button>' : ""}</div></div>`;
    const cd = $("clearDone"); if (cd) cd.onclick = async () => { await api("/api/queue/clear", {}); S.jobSel = null; refreshQueue(true); };
    return;
  }
  pane.style.display = "";
  const tok = j.tokens ? `${Math.round(j.tokens / 1000)} тис.` : "—";
  pane.innerHTML = `
    <div class="crumbs">${esc(j.project)}${j.label ? " › " + esc(j.label.split("/").join(" › ")) : ""}</div>
    <h1 class="title">${esc(j.name)}</h1>
    <div class="status-bar">${jobLine(j)}</div>
    <div class="qbtns">
      <button class="btn" id="jOpen">Відкрити фразу</button>
      ${j.status === "queued" || j.status === "running" ? '<button class="btn" id="jCancel">Скасувати</button>' : '<button class="btn" id="jRetry">Ще раз</button>'}
    </div>
    <dl class="jobmeta">
      <dt>Коментар</dt><dd>${esc(j.comment)}</dd>
      ${"ref" in j ? `<dt>Еталон</dt><dd>${j.ref ? esc(String(j.ref).toUpperCase()) : "немає — лише за коментарем"}</dd>` : ""}
      <dt>Додано</dt><dd>${esc((j.created || "").replace("T", " "))}</dd>
      ${j.started ? `<dt>Почато</dt><dd>${esc(j.started.replace("T", " "))}</dd>` : ""}
      ${j.finished ? `<dt>Завершено</dt><dd>${esc(j.finished.replace("T", " "))}</dd>` : ""}
      ${j.tokens ? `<dt>Токени</dt><dd>${tok}${j.cost != null ? ` · ≈$${Number(j.cost).toFixed(2)} за цінами API` : ""}${j.ctx_after ? ` · контекст після: ${kfmt(j.ctx_after)}` : ""}</dd>` : ""}
      ${j.note ? `<dt>Примітка</dt><dd>${esc(j.note)}</dd>` : ""}
    </dl>
    ${j.result ? `<div class="agent-card"><div class="h">${j.status === "error" ? "ПОМИЛКА" : "ВІДПОВІДЬ АГЕНТА"}</div>${esc(j.result)}</div>` : ""}
    <div class="section-label">Що робить агент</div>
    <div class="log" id="jobLog">…</div>`;
  $("jOpen").onclick = async () => {
    setView("phrases", { restore: false });
    if (j.pid !== S.pid) await openProject(j.pid, j.item);
    else { S.label = ""; S.filter = "all"; renderFolders(); renderFilters(); renderList(); select(j.item, { force: true }); scrollToSel("center"); }
  };
  const c = $("jCancel"); if (c) c.onclick = async () => { await api("/api/queue/cancel", { id: j.id }); refreshQueue(true); };
  const r = $("jRetry"); if (r) r.onclick = async () => { const x = await api("/api/queue/retry", { id: j.id }); S.jobSel = x.job && x.job.id; refreshQueue(true); };
  refreshLog(true);
}
async function refreshLog(force) {
  const el = $("jobLog"); const j = S.jobs.find((x) => x.id === S.jobSel);
  if (!el || !j || (!force && j.status !== "running")) return;
  try {
    const r = await api("/api/queue/log?id=" + encodeURIComponent(j.id));
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
    el.textContent = r.log || (j.status === "queued" ? "Чекає вільного агента…" : "Журналу немає");
    if (atBottom || force) el.scrollTop = el.scrollHeight;
  } catch {}
}
