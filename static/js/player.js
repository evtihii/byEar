/* Holosii (Голосій) — плеєри, хвиля, панель деталей, правки гучності.
   Звичайний (не модульний) скрипт: файли static/js/* вантажаться по черзі й ділять глобальну область. */
/* ---------- плеєри ---------- */
let actx = null;
const peaksCache = new Map();
let players = [], activeIdx = 0, chain = null;

async function getPeaks(url) {
  if (peaksCache.has(url)) return peaksCache.get(url);
  const p = (async () => {
    const buf = await (await fetch(url)).arrayBuffer();
    if (buf.byteLength > 40e6) return null;
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    const ab = await actx.decodeAudioData(buf);
    const ch = ab.getChannelData(0), N = 1200, step = Math.max(1, Math.floor(ch.length / N)), out = new Float32Array(N);
    for (let i = 0; i < N; i++) { let m = 0; const s = i * step, e = Math.min(ch.length, s + step); for (let j = s; j < e; j++) { const v = Math.abs(ch[j]); if (v > m) m = v; } out[i] = m; }
    return { peaks: out, duration: ab.duration };
  })().catch(() => null);
  peaksCache.set(url, p);
  return p;
}
function fmt(t) { if (!isFinite(t)) return "–"; return t < 60 ? t.toFixed(1) : Math.floor(t / 60) + ":" + String(Math.floor(t % 60)).padStart(2, "0"); }

class Player {
  constructor(file, idx, itemId, editable) {
    this.file = file; this.idx = idx; this.itemId = itemId; this.editable = !!editable; this.sel = null;
    this.url = fileUrl(file);
    this.audio = new Audio(); this.audio.preload = "auto"; this.audio.src = this.url;
    this.duration = NaN; this.peaks = null; this.scale = 1;
    const el = this.el = document.createElement("div");
    el.className = "player" + (this.editable ? " editable" : "");
    el.innerHTML = `<button class="play" title="Грати / пауза">${I.play}</button>
      <button class="replay" title="Грати спочатку">${I.replay}</button>
      <div class="ptag" title="${esc(file.name)}">${esc((file.tag || "♪").toUpperCase())}</div>
      <div class="wave-wrap" title="${esc(file.name)} — клік: перемотати${this.editable ? "; потягни мишкою: виділити шматок" : ""}"><canvas></canvas></div>
      <div class="ptime"><b>0.0</b> / –</div>
      ${this.editable ? `<div class="selbar" hidden><span class="rng"></span>
        <button class="pri" data-a="norm" title="Підігнати гучність шматка під те саме місце в англійській">Нормалізувати</button>
        <button data-a="-1" title="Тихіше на 1 дБ">−1 дБ</button><button data-a="+1" title="Гучніше на 1 дБ">+1 дБ</button>
        <button data-a="-3">−3</button><button data-a="+3">+3</button>
        <button data-a="echo" title="Додати луну до шматка (сила й хвіст — з рядка «Луна»)">Луна</button><button data-a="t-5" title="Стиснути шматок на 5 % (швидше), висота та сама">Коротше 5%</button><button data-a="t+5" title="Розтягнути шматок на 5 % (повільніше), висота та сама">Довше 5%</button>
        <button class="x" data-a="clear" title="Зняти виділення (Esc)">✕</button></div>` : ""}`;
    this.btn = el.querySelector(".play"); this.canvas = el.querySelector("canvas"); this.time = el.querySelector(".ptime");
    this.bar = el.querySelector(".selbar");
    if (this.bar) this.bar.addEventListener("click", (e) => {
      const b = e.target.closest("[data-a]"); if (!b) return;
      const it = S.byId.get(this.itemId); const a = b.dataset.a;
      if (a === "clear") this.setSel(null);
      else if (a === "norm") editAudio(it, "normalize");
      else if (a === "echo") editEcho(it);
      else if (a.startsWith("t")) editTempo(it, { pct: Number(a.slice(1)) });
      else editAudio(it, "gain", Number(a));
    });
    this.btn.onclick = () => { activate(idx); this.toggle(); };
    el.querySelector(".replay").onclick = () => { activate(idx); chain = null; this.play(true); };
    const wrap = el.querySelector(".wave-wrap");
    const tAt = (x) => { const r = wrap.getBoundingClientRect(); return Math.max(0, Math.min(1, (x - r.left) / (r.width * this.scale))) * this.duration; };
    wrap.addEventListener("mousedown", (e) => {
      if (!isFinite(this.duration) || e.button !== 0) return;
      e.preventDefault(); activate(idx);
      const x0 = e.clientX, t0 = tAt(x0); let dragging = false;
      const mv = (ev) => {
        if (!this.editable) return;
        if (!dragging && Math.abs(ev.clientX - x0) > 4) dragging = true;
        if (dragging) { const t1 = tAt(ev.clientX); this.setSel(Math.min(t0, t1), Math.max(t0, t1)); }
      };
      const up = (ev) => {
        document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up);
        if (dragging) { this.audio.currentTime = this.sel ? this.sel[0] : t0; this.draw(); return; }
        if (this.sel && (t0 < this.sel[0] || t0 > this.sel[1])) this.setSel(null);
        this.audio.currentTime = t0;
        if (this.audio.paused) this.play(); else this.draw();
      };
      document.addEventListener("mousemove", mv); document.addEventListener("mouseup", up);
    });
    const a = this.audio;
    a.addEventListener("loadedmetadata", () => { if (!isFinite(this.duration)) { this.duration = a.duration; layoutScales(); } });
    a.addEventListener("play", () => { this.btn.innerHTML = I.pause; this.loop(); });
    a.addEventListener("pause", () => { this.btn.innerHTML = I.play; this.draw(); });
    a.addEventListener("ended", () => {
      this.btn.innerHTML = I.play; markHeard(itemId); a.currentTime = 0; this.draw();
      if (chain && chain.item === itemId) { const next = players[this.idx + 1]; if (next) { activate(next.idx); next.play(true); } else chain = null; }
    });
    a.addEventListener("timeupdate", () => { if (a.duration && a.currentTime / a.duration > 0.8) markHeard(itemId); });
    getPeaks(this.url).then((r) => { if (!r) return; this.peaks = r.peaks; this.duration = r.duration; layoutScales(); });
  }
  play(fromStart) {
    for (const p of players) if (p !== this && !p.audio.paused) p.audio.pause();
    if (fromStart) this.audio.currentTime = 0;
    this.audio.play().catch(() => {});
  }
  toggle() { if (this.audio.paused) { chain = null; this.play(this.audio.ended); } else { chain = null; this.audio.pause(); } }
  setSel(a, b) {
    this.sel = a == null || b - a < 0.03 ? null : [a, b];
    if (this.bar) {
      this.bar.hidden = !this.sel;
      if (this.sel) this.bar.querySelector(".rng").textContent = `${this.sel[0].toFixed(2)}–${this.sel[1].toFixed(2)} с`;
    }
    this.draw(); renderSelInfo();
  }
  stop() { this.audio.pause(); try { this.audio.currentTime = 0; } catch {} }
  loop() { this.draw(); if (!this.audio.paused) this.raf = requestAnimationFrame(() => this.loop()); }
  draw() {
    const c = this.canvas, dpr = window.devicePixelRatio || 1, w = c.clientWidth, h = c.clientHeight;
    if (!w) return;
    if (c.width !== Math.round(w * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }
    const g = c.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
    const cs = getComputedStyle(document.documentElement);
    const waveC = cs.getPropertyValue("--wave").trim(), accC = cs.getPropertyValue("--accent").trim(), sepC = cs.getPropertyValue("--sep").trim();
    const ww = w * this.scale, mid = h / 2;
    const prog = isFinite(this.duration) && this.duration ? this.audio.currentTime / this.duration : 0;
    // доріжка до кінця найдовшого файлу
    g.fillStyle = sepC; g.fillRect(ww, mid - .5, w - ww, 1);
    const bar = 2, gap = 1, n = Math.max(1, Math.floor(ww / (bar + gap)));
    for (let i = 0; i < n; i++) {
      let v = .03;
      if (this.peaks) { const s = Math.floor(i / n * this.peaks.length), e = Math.max(s + 1, Math.floor((i + 1) / n * this.peaks.length)); for (let j = s; j < e; j++) v = Math.max(v, this.peaks[j]); }
      const bh = Math.max(1.5, Math.min(1, v * 1.15) * (h - 4));
      const x = i * (bar + gap);
      g.fillStyle = (x / ww) < prog ? accC : waveC;
      g.beginPath(); g.roundRect ? g.roundRect(x, mid - bh / 2, bar, bh, 1) : g.rect(x, mid - bh / 2, bar, bh); g.fill();
    }
    if (this.sel && isFinite(this.duration) && this.duration) {
      const x0 = this.sel[0] / this.duration * ww, x1 = this.sel[1] / this.duration * ww;
      g.fillStyle = cs.getPropertyValue("--accent-soft").trim(); g.fillRect(x0, 0, x1 - x0, h);
      g.fillStyle = accC; g.fillRect(x0, 0, 1, h); g.fillRect(x1 - 1, 0, 1, h);
    }
    if (prog > 0 && prog < 1) { g.fillStyle = accC; g.fillRect(prog * ww - .5, 2, 1.5, h - 4); }
    this.time.innerHTML = `<b>${fmt(this.audio.currentTime)}</b> / ${fmt(this.duration)} с`;
  }
}
function layoutScales() {
  const max = Math.max(...players.map((p) => p.duration).filter(isFinite), 0);
  for (const p of players) { p.scale = max && isFinite(p.duration) ? p.duration / max : 1; p.draw(); }
  renderTempoHint();
}
function renderTempoHint() {
  const h = $("tempoHint"); const it = S.sel && S.byId.get(S.sel); if (!h || !it) return;
  const ep = editPlayer(); const rf = refFile(it);
  const rp = rf ? players.find((p) => p.file === rf) : null;
  const ud = ep && isFinite(ep.duration) ? ep.duration : null, rd = rp && isFinite(rp.duration) ? rp.duration : null;
  h.textContent = ud == null ? "" : `зараз ${ud.toFixed(2)} с` + (rd != null ? ` · ${canon(rf.tag).toUpperCase()} ${rd.toFixed(2)} с (${ud > rd ? "+" : ""}${Math.round((ud / rd - 1) * 100)}%)` : "");
  const fb = $("fitBtn"); if (fb) { fb.disabled = !rf; fb.textContent = rf ? `Довжина як ${canon(rf.tag).toUpperCase()}` : "Довжина як в еталоні"; }
}
function activate(i) { activeIdx = i; players.forEach((p, j) => p.el.classList.toggle("active", j === i && players.length > 1)); }
function stopAll() { chain = null; for (const p of players) { p.stop(); cancelAnimationFrame(p.raf); p.audio.src = ""; } players = []; }
function playAll() { if (!players.length) return; chain = { item: S.sel }; for (const p of players) p.stop(); activate(0); players[0].play(true); }
function playTag(group, fallback) {
  let i = players.findIndex((p) => group.includes((p.file.tag || "").toLowerCase()));
  if (i < 0) i = fallback; const p = players[i]; if (!p) return;
  activate(i); chain = null;
  if (!p.audio.paused) p.audio.pause(); else p.play(true);
}
function markHeard(id) {
  if (S.detailStale && id === S.sel) return;          // грає стара версія — не знімати червону позначку
  const e = S.fb[id] || {};
  if (e.heard && e.heardAt && !isUpdated(id)) return;
  setFb(id, { heard: true, heardAt: nowSec() }); updateRow(id); renderFilters(); renderFolderCard();
  const b = document.getElementById("updBanner"); if (b && id === S.sel) b.remove();
}
window.addEventListener("resize", () => players.forEach((p) => p.draw()));

/* ---------- панель деталей ---------- */
function renderDetail() {
  if (S.view === "queue") { renderJobDetail(); return; }
  if (S.view === "home") return;
  S.detailStale = false;
  stopAll(); stopBefore();
  const pane = $("pane");
  $("revealBtn").disabled = !S.sel;
  const it = S.sel && S.byId.get(S.sel);
  if (!it) {
    pane.innerHTML = S.project
      ? `<div class="placeholder"><div><h2>${esc(S.project.name)}</h2>${S.items.length} ${plural(S.items.length, "фраза", "фрази", "фраз")}. Виберіть фразу зліва або натисніть <kbd>↓</kbd>.</div></div>`
      : `<div class="placeholder"><div><h2>Немає проєкту</h2>Додайте папку гри кнопкою <kbd>+</kbd> внизу бокової панелі.</div></div>`;
    pane.style.display = "flex"; return;
  }
  pane.style.display = "";
  const e = S.fb[it.id] || {};
  pane.innerHTML = `
    <div class="crumbs">${esc(it.label ? it.label.split("/").join(" › ") : S.project.name)}</div>
    <h1 class="title">${esc(it.name)}</h1>
    ${isUpdated(it.id) ? `<div class="updated" id="updBanner"><span class="dot red"></span>Файл оновлено ${esc(new Date(it.mtime * 1000).toLocaleString("uk-UA", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }))} — ти ще не слухав нову версію</div>` : ""}
    ${(() => { const vt = volTarget(it), og = originals(it);
      return og.length && vt
        ? `<div class="grp-label">ОРИГІНАЛ</div><div class="players src" id="playersSrc"></div><div class="refrow" id="refRow"></div>
           <div class="grp-label tr">ПЕРЕКЛАД · ${esc((vt.tag || "").toUpperCase())}</div><div class="players" id="players"></div>`
        : `<div class="players" id="players"></div>`; })()}
    ${volTarget(it) ? `<div class="vol-row"><span id="selInfo">Для <span class="vt">${esc(volTarget(it).name)}</span> (потягни по хвилі, щоб виділити шматок):</span>
      <input type="number" id="volDb" step="1" min="-30" max="30" value="0" title="Крок 1 дБ; мінус — тихіше"> дБ
      <button class="btn" id="volBtn">Змінити гучність</button>
      <button class="btn" id="normBtn" title="Підігнати гучність під вибраний еталон (весь файл — за LUFS, шматок — за тим самим місцем в еталоні)">Нормалізувати як EN</button>
      <button class="link-btn" id="selClear" hidden>скинути виділення</button></div>
    <div class="vol-row tempo-row"><span>Довжина:</span>
      <input type="number" id="tempoPct" step="1" min="-40" max="80" value="0" title="На скільки відсотків змінити довжину: мінус — коротше (швидше), плюс — довше (повільніше). Висота голосу не змінюється">%
      <button class="btn" id="tempoBtn" title="Змінити темп без зміни висоти голосу (весь файл або виділений шматок)">Змінити темп</button>
      <button class="btn" id="fitBtn" title="Стиснути чи розтягнути весь файл до довжини еталона, без зміни висоти голосу">Довжина як в еталоні</button>
      <span class="hint" id="tempoHint"></span></div>
    <div class="vol-row tempo-row"><span>Луна:</span>
      <input type="number" id="echoAmt" step="5" min="1" max="100" value="${esc(ls.get("echoAmt") || 30)}" title="Сила луни, %: 10 — ледь чутно, 30 — кімната, 70 — великий зал">%
      <span>хвіст</span><input type="number" id="echoTail" step="0.1" min="0.1" max="4" value="${esc(ls.get("echoTail") || 1)}" title="За скільки секунд луна згасає">с
      <button class="btn" id="echoBtn" title="Додати луну до всього файлу або до виділеного шматка; гучність слів лишається тією самою">Додати луну</button>
      <span class="hint">⌘Z — прибрати</span></div>` : ""}
    <div class="section-label comment-head">Коментар <span class="dict-wrap"><button class="dict-btn" id="dictBtn">${I.mic} Диктувати</button><span class="dict-tip" id="dictTip"></span></span></div>
    <textarea class="comment" id="comment" placeholder="Що не так? Наприклад: наголос у слові…, тон не той, пауза задовга…" spellcheck="true"></textarea>
    <div class="status-bar under">${Object.entries(STATUS).map(([k, s]) =>
      `<button class="sbtn ${k} ${e.status === k ? "on" : ""}" data-st="${k}"><span style="color:${s.color}">${I[k]}</span>${s.name}<kbd>${s.key}</kbd></button>`).join("")}
      <span id="jobChip"></span></div>
    <div id="agentCard"></div>
    ${it.text ? `<div class="section-label">Текст</div><div class="text">${esc(it.text)}</div>` : ""}
    <div class="keys">
      <kbd>E</kbd> англійська &nbsp; <kbd>J</kbd> японська &nbsp; <kbd>U</kbd> українська &nbsp; <kbd>A</kbd> усе по черзі &nbsp; <kbd>R</kbd> спочатку &nbsp; <kbd>Пробіл</kbd> пауза &nbsp; <kbd>↑</kbd><kbd>↓</kbd> фрази<br>
      <kbd>1</kbd> готово &nbsp; <kbd>2</kbd> виправити &nbsp; <kbd>0</kbd> зняти позначку &nbsp; <kbd>⌘Z</kbd> скасувати зміну звуку &nbsp; <kbd>⇧⌘Z</kbd> повторити &nbsp; <kbd>C</kbd> коментар &nbsp; <kbd>Esc</kbd> вийти з коментаря
    </div>`;
  const box = $("players");
  const vt = volTarget(it);
  players = it.files.map((f, i) => new Player(f, i, it.id, f === vt));
  const srcBox = $("playersSrc");
  players.forEach((p) => (srcBox && !p.editable ? srcBox : box).appendChild(p.el));
  renderRefRow(it);
  activate(0);
  requestAnimationFrame(() => players.forEach((p) => p.draw()));
  pane.querySelectorAll(".sbtn").forEach((b) => b.onclick = () => setStatus(b.dataset.st));
  const ta = $("comment"); ta.value = e.comment || "";
  const syncFix = () => { const b = pane.querySelector(".sbtn.fix"); if (b) { b.disabled = !ta.value.trim(); b.title = b.disabled ? "Спершу напишіть коментар" : "Позначити й відправити агенту"; } };
  syncFix();
  let ct;
  ta.addEventListener("input", () => { syncFix(); clearTimeout(ct); ct = setTimeout(() => { setFb(it.id, { comment: ta.value, heard: true }); updateRow(it.id); }, 400); });
  const vb = $("volBtn"); if (vb) vb.onclick = () => changeVolume(it);
  const tb = $("tempoBtn"); if (tb) tb.onclick = () => { const v = Math.round(Number($("tempoPct").value)); if (!v) { toast("Вкажи, на скільки відсотків змінити довжину (наприклад -10 або 15)"); $("tempoPct").focus(); return; } editTempo(it, { pct: v }); };
  const fb = $("fitBtn"); if (fb) fb.onclick = () => editTempo(it, { fit: true });
  const eb = $("echoBtn"); if (eb) eb.onclick = () => editEcho(it);
  const db = $("dictBtn"); if (db) db.onclick = () => startDictation();
  renderDictBtn();
  ["echoAmt", "echoTail"].forEach((id) => { const x = $(id); if (x) x.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); editEcho(it); } }); });
  const tp = $("tempoPct"); if (tp) tp.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); $("tempoBtn").click(); } });
  const nb = $("normBtn"); if (nb) nb.onclick = () => editAudio(it, "normalize");
  const sc = $("selClear"); if (sc) sc.onclick = () => { const p = editPlayer(); if (p) p.setSel(null); };
  const vi = $("volDb"); if (vi) vi.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); changeVolume(it); } });
  renderJobInfo();
  ta.addEventListener("blur", () => { clearTimeout(ct); if ((S.fb[it.id] || {}).comment !== ta.value && (ta.value || (S.fb[it.id] || {}).comment)) { setFb(it.id, { comment: ta.value }); updateRow(it.id); } });
  pane.scrollTop = 0;
}
