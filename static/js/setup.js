/* ByEar (наСлух) — налаштування проєкту з гри: окреме вікно з агентом налаштування.
   Звичайний (не модульний) скрипт: файли static/js/* вантажаться по черзі й ділять глобальну область. */
const SETUP_STEPS = [
  ["survey", "Огляд гри"], ["plan", "План"], ["extract", "Видобування"], ["ready", "Готово"],
];
const SETUP_STATE = {
  new: "ще не почато", surveying: "агент оглядає гру…", plan: "план готовий — чекає твого рішення",
  blocked: "не вийде в межах правил", waiting: "агент чекає твоєї відповіді", extracting: "агент видобуває фрази…",
  talking: "агент відповідає…", ready: "видобування завершено", done: "проєкт відкрито", stopped: "зупинено",
  error: "помилка",
};
let setupTimer = null;

function setupStepIndex(st) {
  const s = st.state, prev = st.prev_state;
  if (s === "ready" || s === "done") return 3;
  if (s === "extracting" || (s === "talking" && (prev === "extracting" || st.result))) return 2;
  if (st.plan) return st.result ? 3 : 1;
  return 0;
}

function setupMsgHtml(m) {
  const who = m.role === "agent" ? "Агент" : m.role === "user" ? "Ти" : "";
  const time = (m.time || "").slice(11, 16);
  return `<div class="smsg ${m.role}">${who ? `<div class="sw">${who}<span>${time}</span></div>` : ""}<div class="sb">${esc(m.text)}${!who ? ` <span class="stime">${time}</span>` : ""}</div></div>`;
}

function setupPlanHtml(plan, pid) {
  if (!plan) return "";
  const langs = (plan.languages || []).map((l) => `<tr><td><b>${esc(String(l.code || "").toUpperCase())}</b> ${esc(l.name || "")}</td><td>${l.lines != null ? Number(l.lines).toLocaleString("uk-UA") : "?"}</td><td>${esc(l.note || "")}</td></tr>`).join("");
  const samples = (plan.samples || []).map((s) => `<div class="ssample"><button class="btn sm" data-sample="${esc(s.file)}">${I.play}</button><b>${esc(String(s.lang || "").toUpperCase())}</b><span>${esc(s.text || s.file)}</span></div>`).join("");
  const list = (a) => (a || []).length ? `<ul>${a.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "";
  return `<div class="scard">
    <div class="sh">План</div>
    ${plan.blocked ? `<div class="sblocked">${I.warn} ${esc(plan.blocked)}</div>` : ""}
    <dl class="jobmeta">
      <dt>Рушій</dt><dd>${esc(plan.engine || "?")}</dd>
      <dt>Звук</dt><dd>${esc(plan.audio || "?")}</dd>
      <dt>Рецепт</dt><dd>${plan.recipe ? esc(plan.recipe) : "немає — агент розбирається сам"}</dd>
      ${plan.text ? `<dt>Текст</dt><dd>${esc(plan.text)}</dd>` : ""}
      ${plan.size ? `<dt>Обсяг</dt><dd>${esc(plan.size)}</dd>` : ""}
    </dl>
    ${langs ? `<table class="stable"><tr><th>Мова</th><th>Фраз</th><th></th></tr>${langs}</table>` : ""}
    ${samples ? `<div class="section-label">Зразки — послухай, чи це ті голоси</div><div class="ssamples">${samples}</div>` : ""}
    ${(plan.steps || []).length ? `<div class="section-label">Що буде далі</div>${list(plan.steps)}` : ""}
    ${(plan.problems || []).length ? `<div class="section-label">Проблеми</div>${list(plan.problems)}` : ""}
    ${(plan.questions || []).length ? `<div class="section-label">Питання до тебе</div>${list(plan.questions)}` : ""}
  </div>`;
}

function setupResultHtml(r) {
  if (!r) return "";
  return `<div class="scard ok">
    <div class="sh">Результат</div>
    <dl class="jobmeta">
      <dt>Фраз</dt><dd>${r.lines != null ? Number(r.lines).toLocaleString("uk-UA") : "?"}</dd>
      <dt>Мови</dt><dd>${esc((r.languages || []).join(", ").toUpperCase())}</dd>
      ${r.notes ? `<dt>Примітки</dt><dd>${esc(r.notes)}</dd>` : ""}
    </dl></div>`;
}

async function renderSetup(keepInput) {
  const pid = S.pid; if (!pid) return setView("home");
  clearTimeout(setupTimer);
  const typing = keepInput && document.activeElement && document.activeElement.id === "setupInput";
  let d;
  try { d = await api("/api/setup?p=" + encodeURIComponent(pid)); }
  catch (err) { $("home").innerHTML = `<div class="home-in"><button class="btn" id="setupHome">${I.back} Проєкти</button><p>${esc(err.message)}</p></div>`; $("setupHome").onclick = () => setView("home"); return; }
  if (S.view !== "setup" || S.pid !== pid) return;
  if (typing && !d.setup.running && JSON.stringify(d.setup) === S.setupSig) {   // не збивати курсор, поки нічого не змінилось
    setupTimer = setTimeout(() => { if (S.view === "setup" && S.pid === pid) renderSetup(true); }, 10000); return;
  }
  S.setupSig = JSON.stringify(d.setup);
  const sp = S.projects.find((x) => x.id === pid);           // значок у боковій панелі
  if (sp && (!sp.setup || sp.setup.state !== d.setup.state || sp.setup.running !== d.setup.running)) {
    sp.setup = { state: d.setup.state, running: d.setup.running }; renderProjects();
  }
  const st = d.setup, p = d.project, idx = setupStepIndex(st);
  const busy = st.running;
  const draft = keepInput && $("setupInput") ? $("setupInput").value : "";
  const steps = SETUP_STEPS.map(([, n], i) => `<div class="sstep ${i < idx ? "done" : i === idx ? "cur" : ""}"><span>${i < idx ? "✓" : i + 1}</span>${n}</div>`).join('<i class="sline"></i>');
  let main = "";
  if (st.state === "new" || ((st.state === "stopped" || st.state === "error") && !st.plan))
    main = `<button class="btn primary" id="setupSurvey">${st.state === "new" ? "Почати огляд гри" : "Почати огляд знову"}</button>`;
  else if (st.plan && !st.plan.blocked && !st.result && !busy)
    main = `<button class="btn primary" id="setupExtract">Так, видобувай</button>`;
  else if (st.state === "ready")
    main = `<button class="btn primary" id="setupFinish">Відкрити проєкт для прослуховування</button>`;
  const msgs = (st.messages || []).map(setupMsgHtml).join("");
  const cost = st.cost ? ` · ≈$${Number(st.cost).toFixed(2)} за цінами API` : "";
  $("home").innerHTML = `<div class="home-in setup">
    <div class="setup-top">
      <button class="btn" id="setupHome">${I.back} Проєкти</button>
      <span class="grow"></span>
      <a class="doc-link on" href="/docs/setup.html" target="_blank" rel="noopener">${I.book} Як це працює</a>
    </div>
    <h1>${esc(p.name)} <small>налаштування проєкту</small></h1>
    <div class="spaths">
      <div><span>Гра</span><code>${esc(p.game_dir)}</code></div>
      <div><span>Робоча тека</span><code class="link" id="setupWs" title="Показати у Finder">${esc(p.workspace)}</code></div>
    </div>
    <div class="ssteps">${steps}</div>
    <div class="sstate ${st.state}">${busy ? '<span class="spin"></span>' : ""}<b>${esc(SETUP_STATE[st.state] || st.state)}</b>${st.now && busy ? `<span class="snow">${esc(st.now)}</span>` : ""}${st.error ? `<span class="serr">${esc(st.error)}</span>` : ""}<span class="grow"></span><span class="scost">${st.tokens_total ? Math.round(st.tokens_total / 1000) + " тис. токенів" : ""}${cost}</span></div>
    <div class="sactions">${main}${busy ? '<button class="btn" id="setupStop">Зупинити</button>' : ""}</div>
    ${setupResultHtml(st.result)}
    ${setupPlanHtml(st.plan, pid)}
    <div class="section-label">Розмова з агентом</div>
    <div class="schat" id="setupChat">${msgs || '<div class="empty">Тут з\'являться повідомлення агента.</div>'}</div>
    <div class="scompose">
      <textarea id="setupInput" rows="2" placeholder="${busy ? "Агент працює — напишеш, коли закінчить" : "Напиши агенту: відповідь на питання, уточнення до плану…"}" ${busy ? "disabled" : ""}></textarea>
      <button class="btn" id="setupSend" ${busy ? "disabled" : ""}>Надіслати</button>
    </div>
  </div>`;
  if (draft) { $("setupInput").value = draft; if (typing) $("setupInput").focus(); }
  const chat = $("setupChat"); chat.scrollTop = chat.scrollHeight;
  const go = async (kind, text) => {
    try { await api("/api/setup/start?p=" + encodeURIComponent(pid), { kind, text: text || "" }); renderSetup(); }
    catch (err) { toast(err.message); }
  };
  $("setupHome").onclick = () => setView("home");
  $("setupWs").onclick = () => api("/api/setup/reveal?p=" + encodeURIComponent(pid), {}).catch((err) => toast(err.message));
  const b = (id, fn) => { const x = $(id); if (x) x.onclick = fn; };
  b("setupSurvey", () => go("survey"));
  b("setupExtract", () => {
    const note = $("setupInput").value.trim();
    if (!confirm("Агент видобуде всі фрази в робочу теку й напише скрипти видобування й пакування.\nГра не зміниться. Це може зайняти чимало часу й токенів.\n\nПочати?")) return;
    $("setupInput").value = ""; go("extract", note);
  });
  b("setupFinish", async () => {
    try { await api("/api/setup/finish?p=" + encodeURIComponent(pid), {}); await loadProjects(); S.view = "home"; await openProject(pid); }
    catch (err) { toast(err.message); }
  });
  b("setupStop", async () => { if (confirm("Зупинити агента налаштування?")) { await api("/api/setup/stop?p=" + encodeURIComponent(pid), {}); renderSetup(); } });
  b("setupSend", () => { const t = $("setupInput").value.trim(); if (!t) return; $("setupInput").value = ""; go("talk", t); });
  $("setupInput").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); $("setupSend").click(); } });
  $("home").querySelectorAll("[data-sample]").forEach((x) => x.onclick = () => {
    stopAll();
    const a = new Audio("/api/setup/file?p=" + encodeURIComponent(pid) + "&f=" + encodeURIComponent(x.dataset.sample.replace(/^\.?\/?(\.byear\/)?/, "")));
    S.setupAudio = a; a.play().catch((err) => toast("Не вдалося відтворити: " + err.message));
  });
  setupTimer = setTimeout(() => { if (S.view === "setup" && S.pid === pid) renderSetup(true); }, busy ? 2500 : 10000);
}
