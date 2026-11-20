/* Holosii (Голосій) — контекстне меню по правому кліку: «Показати у Finder», «Відкрити теку».
   Звичайний (не модульний) скрипт: файли static/js/* вантажаться по черзі й ділять глобальну область. */
/* ---------- диктування: запис голосу в сторінці → локальний Whisper на сервері → текст у коментар ---------- */
S.dict = null;                                        // {available, reason, model_name, lang}
let rec = null;                                        // {recorder, stream, chunks, t0, timer}
async function loadDictation() {
  try { S.dict = await api("/api/dictation"); } catch { S.dict = { available: false, reason: "Сервер не відповідає" }; }
  renderDictBtn();
}
function renderDictBtn() {
  const b = $("dictBtn"), tip = $("dictTip"); if (!b) return;
  const d = S.dict;
  if (rec) return;
  b.classList.remove("rec");
  b.disabled = !d || !d.available;
  b.innerHTML = `${I.mic} Диктувати`;
  b.title = d && d.available ? `Надиктувати коментар (Whisper ${d.model_name || ""}, мова ${d.lang || "uk"}). Клавіша D` : "";
  if (tip) tip.innerHTML = d && !d.available
    ? `<b>Диктування недоступне.</b> ${esc(d.reason || "")}.<br><a href="/docs/whisper.html" target="_blank" rel="noopener">Як встановити Whisper →</a>` : "";
}
function blobToB64(blob) {
  return new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(",")[1] || ""); r.onerror = bad; r.readAsDataURL(blob); });
}
async function startDictation() {
  const b = $("dictBtn"); const ta = $("comment"); if (!b || !ta) return;
  if (rec) { rec.recorder.stop(); return; }                       // друге натискання — зупинити
  if (!S.dict || !S.dict.available) { toast("Диктування недоступне: " + ((S.dict && S.dict.reason) || "немає Whisper")); return; }
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch { toast("Немає доступу до мікрофона. Дозволь його для Голосія: Системні параметри → Приватність і безпека → Мікрофон"); return; }
  const type = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || "";
  const recorder = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
  const chunks = [];
  recorder.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
  const itemId = S.sel;
  recorder.onstop = async () => {
    clearInterval(rec.timer); stream.getTracks().forEach((t) => t.stop()); rec = null;
    const bb = $("dictBtn"); if (bb) { bb.classList.remove("rec"); bb.disabled = true; bb.innerHTML = `${I.mic} Розпізнаю…`; }
    try {
      const blob = new Blob(chunks, { type: recorder.mimeType || type || "audio/webm" });
      if (blob.size < 2000) { toast("Запис закороткий"); return; }
      const ext = (blob.type.includes("mp4") ? "mp4" : blob.type.includes("ogg") ? "ogg" : "webm");
      const r = await api("/api/dictate", { audio: await blobToB64(blob), ext });
      const text = (r.text || "").trim();
      if (!text) { toast("Нічого не розпізнано"); return; }
      const t = $("comment");
      if (t && S.sel === itemId) {
        const s = t.selectionStart ?? t.value.length, e = t.selectionEnd ?? t.value.length;
        const pre = t.value.slice(0, s); const sep = pre && !/\s$/.test(pre) ? " " : "";
        t.setRangeText(sep + text, s, e, "end"); t.dispatchEvent(new Event("input")); t.focus();
      } else { setFb(itemId, { comment: (((S.fb[itemId] || {}).comment || "") + " " + text).trim() }); toast("Текст додано в коментар фрази, з якої почався запис"); }
    } catch (err) { toast(err.message); }
    finally { renderDictBtn(); }
  };
  rec = { recorder, stream, chunks, t0: Date.now(), timer: null };
  recorder.start(250);
  b.classList.add("rec"); b.disabled = false;
  const tick = () => { const s = Math.floor((Date.now() - rec.t0) / 1000); b.innerHTML = `● Зупинити ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; if (s >= 120) recorder.stop(); };
  tick(); rec.timer = setInterval(tick, 500);
}
loadDictation();
const ctxEl = document.createElement("div");
ctxEl.className = "ctx"; ctxEl.hidden = true; document.body.appendChild(ctxEl);
let ctxItems = [];
function hideCtx() { ctxEl.hidden = true; ctxItems = []; }
async function reveal(pid, rel, open) {
  try { await api("/api/reveal?p=" + encodeURIComponent(pid), { f: rel, open: !!open }); }
  catch (err) { toast(err.message); }
}
/* що показувати для елемента під курсором: [заголовок, [[назва, дія], …]] або null */
function ctxFor(t) {
  const pl = t.closest(".player");
  if (pl) {
    const p = players.find((x) => x.el === pl); if (!p) return null;
    return [p.file.name, [["Показати у Finder", () => reveal(S.pid, p.file.path)]]];
  }
  const row = t.closest(".row[data-id]");
  if (row) {
    const it = S.byId.get(row.dataset.id); if (!it) return null;
    const dir = it.files[0] ? it.files[0].path.split("/").slice(0, -1).join("/") : it.id;
    return [it.name, [["Показати у Finder", () => reveal(S.pid, it.files.length > 1 ? dir || it.files[0].path : it.files[0].path)],
                      ["Відкрити теку фрази", () => reveal(S.pid, dir, true)]]];
  }
  const fr = t.closest("[data-label]");
  if (fr && S.pid) {
    const l = fr.dataset.label;
    return [l ? l.split("/").pop() : "Усі фрази", [["Показати у Finder", () => reveal(S.pid, l)], ["Відкрити теку", () => reveal(S.pid, l, true)]]];
  }
  const pr = t.closest("[data-pid]");
  if (pr) {
    const p = S.projects.find((x) => x.id === pr.dataset.pid); if (!p || !p.exists) return null;
    return [p.name, [["Показати у Finder", () => reveal(p.id, "")], ["Відкрити теку проєкту", () => reveal(p.id, "", true)]]];
  }
  return null;
}
document.addEventListener("contextmenu", (e) => {
  if (e.target.closest("input, textarea")) return;          // у полях — звичайне меню (копіювати/вставити)
  const m = ctxFor(e.target);
  if (!m) { hideCtx(); return; }
  e.preventDefault();
  ctxItems = m[1];
  ctxEl.innerHTML = `<div class="ctx-h">${esc(m[0])}</div>` + ctxItems.map((x, i) => `<button data-ctx="${i}">${esc(x[0])}</button>`).join("");
  ctxEl.hidden = false;
  const w = ctxEl.offsetWidth, h = ctxEl.offsetHeight;
  ctxEl.style.left = Math.min(e.clientX, innerWidth - w - 6) + "px";
  ctxEl.style.top = Math.min(e.clientY, innerHeight - h - 6) + "px";
});
ctxEl.addEventListener("click", (e) => {
  const b = e.target.closest("[data-ctx]"); if (!b) return;
  const f = ctxItems[Number(b.dataset.ctx)]; hideCtx(); if (f) f[1]();
});
document.addEventListener("mousedown", (e) => { if (!ctxEl.hidden && !ctxEl.contains(e.target)) hideCtx(); }, true);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !ctxEl.hidden) { hideCtx(); e.stopPropagation(); } }, true);
window.addEventListener("blur", hideCtx);
document.addEventListener("scroll", hideCtx, true);
