/* ByEar (наСлух) — клавіатура.
   Звичайний (не модульний) скрипт: файли static/js/* вантажаться по черзі й ділять глобальну область. */
/* ---------- клавіатура (працює і на українській розкладці) ---------- */
document.addEventListener("keydown", (e) => {
  if ($("sheetBack").classList.contains("show")) { if (e.key === "Escape") closeSheet(); if (e.key === "Enter") addProject(); return; }
  const tag = (e.target.tagName || "").toLowerCase();
  if (tag === "textarea" || tag === "input") { if (e.key === "Escape") { e.target.blur(); $("rows").focus(); } return; }
  if (e.metaKey || e.ctrlKey || e.altKey) {
    if ((e.metaKey || e.ctrlKey) && e.code === "KeyF") { e.preventDefault(); $("q").focus(); $("q").select(); }
    if ((e.metaKey || e.ctrlKey) && e.code === "KeyZ" && S.view !== "queue" && S.sel) { e.preventDefault(); undoAudio(e.shiftKey); }
    return;
  }
  const c = e.code;
  if (S.view === "home") return;
  if (S.view === "queue") {
    if (e.key === "Escape") { e.preventDefault(); goBack(); return; }
    if (c === "ArrowDown" || c === "ArrowUp") { e.preventDefault(); moveJob(c === "ArrowDown" ? 1 : -1); }
    return;
  }
  if (c === "ArrowDown") { e.preventDefault(); move(1); }
  else if (c === "ArrowUp") { e.preventDefault(); move(-1); }
  else if (c === "Space") { e.preventDefault(); const p = players[activeIdx]; if (p) p.toggle(); }
  else if (c === "KeyE") playTag(SOURCE, 0);
  else if (c === "KeyU") playTag(TARGET, 1);
  else if (c === "KeyJ") playTag(["ja", "jp", "jpn"], -1);
  else if (c === "KeyA") playAll();
  else if (c === "KeyR") { const p = players[activeIdx]; if (p) { chain = null; p.play(true); } }
  else if (e.key === "Escape") { const p = editPlayer(); if (p && p.sel) p.setSel(null); }
  else if (c === "Digit1") setStatus("ok");
  else if (c === "Digit2") setStatus("fix");
  else if (c === "Digit0" || c === "Backspace") { if (S.sel && (S.fb[S.sel] || {}).status) { setFb(S.sel, { status: null }); afterFbChange(); } }
  else if (c === "KeyD") { e.preventDefault(); startDictation(); }
  else if (c === "KeyC") { const ta = $("comment"); if (ta) { e.preventDefault(); ta.focus(); } }
  else if (c === "ArrowRight" || c === "ArrowLeft") { const p = players[activeIdx]; if (p && isFinite(p.duration)) { e.preventDefault(); p.audio.currentTime = Math.max(0, Math.min(p.duration, p.audio.currentTime + (c === "ArrowRight" ? 1 : -1))); p.draw(); } }
  else if (c === "Tab" && players.length > 1) { e.preventDefault(); activate((activeIdx + (e.shiftKey ? players.length - 1 : 1)) % players.length); }
});
