/* ByEar (наСлух) — контекстне меню по правому кліку: «Показати у Finder», «Відкрити теку».
   Звичайний (не модульний) скрипт: файли static/js/* вантажаться по черзі й ділять глобальну область. */
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
