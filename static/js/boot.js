/* Holosii (Голосій) — кнопки панелей і старт.
   Звичайний (не модульний) скрипт: файли static/js/* вантажаться по черзі й ділять глобальну область. */
/* ---------- кнопки панелей ---------- */
$("appIcon").innerHTML = I.headphones; $("queueIcon").innerHTML = I.queue;
$("backIcon").innerHTML = I.back; $("projIcon").innerHTML = I.back; $("homeIcon").innerHTML = I.house;
$("railAgIcon").innerHTML = I.spark; $("compactIcon").innerHTML = I.compress; $("restartIcon").innerHTML = I.restart;
$("searchIcon").innerHTML = I.search;
$("addBtn").innerHTML = I.plus; $("removeBtn").innerHTML = I.minus; $("rescanBtn").innerHTML = I.refresh;
$("revealBtn").innerHTML = I.finder; $("autoBtn").innerHTML = I.auto;
S.auto = ls.get("auto", false); $("autoBtn").classList.toggle("on", S.auto);
$("autoBtn").onclick = () => { S.auto = !S.auto; ls.set("auto", S.auto); $("autoBtn").classList.toggle("on", S.auto); toast(S.auto ? "Автовідтворення увімкнено" : "Автовідтворення вимкнено"); };
$("revealBtn").onclick = () => { const it = S.byId.get(S.sel); if (it && it.files[0]) api("/api/reveal?p=" + encodeURIComponent(S.pid), { f: it.files[0].path }).catch((e) => toast(e.message)); };
$("rescanBtn").onclick = async () => { if (S.pid) { await openProject(S.pid, S.sel); toast("Папку перечитано"); } };
$("removeBtn").onclick = async () => {
  const p = S.projects.find((x) => x.id === S.pid); if (!p) return;
  if (!confirm(`Прибрати «${p.name}» зі списку?\n\nФайли й «summary.json» у папці залишаться — проєкт можна додати знову.`)) return;
  await api("/api/projects/remove", { id: p.id }); S.pid = null; ls.del("lastProject");
  await loadProjects(); if (S.projects[0]) openProject(S.projects[0].id); else { S.items = []; S.project = null; $("rows").innerHTML = ""; $("foldersBlock").hidden = true; renderDetail(); renderSaveState(); }
};
const SHEET_HINT = {
  game: "Вкажи теку гри — агент налаштування знайде в ній озвучку, покаже план і зразки, а після твого «так» видобуде фрази в робочу теку. Гру він не змінює.",
  folder: "Тека, де вже лежать фрази (en.wav, ua.wav, текст.txt). Позначки й коментарі збережуться в «summary.json» у цій теці.",
};
function setSheetMode(m) {
  S.sheetMode = m;
  $("pMode").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.mode === m));
  $("pHint").textContent = SHEET_HINT[m];
  $("pPathLbl").textContent = m === "game" ? "Тека гри" : "Тека зі звуками";
  $("pWsField").hidden = m !== "game";
  $("okBtn").textContent = m === "game" ? "Створити" : "Додати";
  wsPlaceholder();
}
function wsPlaceholder() {
  const n = ($("pName").value || $("pPath").value.split("/").pop() || "").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40);
  $("pWs").placeholder = "~/Holosii/" + (n || "назва");
}
$("pMode").addEventListener("click", (e) => { const b = e.target.closest("[data-mode]"); if (b) setSheetMode(b.dataset.mode); });
$("pName").addEventListener("input", wsPlaceholder);
function openSheet() { $("pName").value = ""; $("pPath").value = ""; $("pWs").value = ""; $("pErr").textContent = ""; setSheetMode(S.sheetMode || "game"); $("sheetBack").classList.add("show"); setTimeout(() => $("pName").focus(), 30); }
function closeSheet() { $("sheetBack").classList.remove("show"); }
async function addProject() {
  $("pErr").textContent = "";
  try {
    const r = S.sheetMode === "game"
      ? await api("/api/projects/add", { name: $("pName").value, game: $("pPath").value, workspace: $("pWs").value })
      : await api("/api/projects/add", { name: $("pName").value, path: $("pPath").value });
    closeSheet(); await loadProjects(); openProject(r.id);
  } catch (err) { $("pErr").textContent = err.message; }
}
$("addBtn").onclick = openSheet;
$("cancelBtn").onclick = closeSheet;
$("okBtn").onclick = addProject;
$("sheetBack").addEventListener("mousedown", (e) => { if (e.target === $("sheetBack")) closeSheet(); });
$("pickBtn").onclick = async () => {
  try {
    const r = await api("/api/pick-folder", { prompt: S.sheetMode === "game" ? "Виберіть теку гри" : "Виберіть теку зі звуками" });
    if (r.path) { $("pPath").value = r.path; if (!$("pName").value) $("pName").value = r.path.split("/").pop(); wsPlaceholder(); }
  } catch (err) { $("pErr").textContent = err.message; }
};
$("pickWsBtn").onclick = async () => {
  try { const r = await api("/api/pick-folder", { prompt: "Виберіть робочу теку проєкту" }); if (r.path) $("pWs").value = r.path; }
  catch (err) { $("pErr").textContent = err.message; }
};

/* ---------- старт ---------- */
(async () => {
  await loadConfig();
  try { await loadProjects(); }
  catch { $("rows").innerHTML = '<div class="empty">Сервер не відповідає. Запустіть «Holosii.command».</div>'; return; }
  let last = null;
  try { last = (await api("/api/state")).last_project || null; } catch {}
  last = last || ls.get("lastProject");
  const p = S.projects.find((x) => x.id === last && x.exists);
  if (p) await openProject(p.id); else setView("home");
  refreshQueue(true);
  $("rows").focus();
})();
