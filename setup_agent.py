"""Project setup agent: gets the voice-over out of a game into listening folders, and writes the project's
own `extract` / `pack` scripts. Separate from the fix agent (agents.py): its own Claude run per step, a stronger
model, its own token limit.

Steps (state in <workspace>/.holosii/setup.json):
    new → surveying → plan (or blocked / waiting) → extracting → ready → done
The agent reports through files: .holosii/plan.json after the survey, .holosii/result.json after the extraction.
Every step is a separate `claude -p` run that resumes the same session, so the agent remembers the earlier ones;
the user can also write to it between steps.
"""
import json
import os
import re
import subprocess
import threading
import time

import agents
import platform_util

HERE = os.path.dirname(os.path.abspath(__file__))
RECIPES = os.path.join(HERE, "recipes")
TOOLS = "Bash,Read,Write,Edit,Glob,Grep"
MAX_MESSAGES = 400

_runs = {}                       # workspace → Popen of the running step
_lock = threading.Lock()


def _dir(ws):
    d = os.path.join(ws, ".holosii")
    old = os.path.join(ws, ".byear")                 # проєкти, створені до перейменування (наСлух / ByEar)
    if not os.path.isdir(d) and os.path.isdir(old):
        try:
            os.rename(old, d)
        except OSError:
            return old
    return d


def state_path(ws):
    return os.path.join(_dir(ws), "setup.json")


def load(ws):
    st = agents._read_json(state_path(ws), None) or {}
    st.setdefault("state", "new")
    st.setdefault("messages", [])
    st["running"] = ws in _runs
    if st["state"] in ("surveying", "extracting", "talking") and not st["running"]:
        st["state"] = "stopped"                       # the server restarted mid-step
    st["plan"] = agents._read_json(os.path.join(_dir(ws), "plan.json"), None)
    st["result"] = agents._read_json(os.path.join(_dir(ws), "result.json"), None)
    return st


def _save(ws, st):
    os.makedirs(_dir(ws), exist_ok=True)
    keep = {k: v for k, v in st.items() if k not in ("running", "plan", "result")}
    keep["messages"] = keep.get("messages", [])[-MAX_MESSAGES:]
    agents._write_json(state_path(ws), keep)


def _update(ws, **kw):
    with _lock:
        st = agents._read_json(state_path(ws), None) or {"state": "new", "messages": []}
        msg = kw.pop("message", None)
        st.update(kw)
        if msg:
            st.setdefault("messages", []).append({**msg, "time": agents._now()})
        _save(ws, st)
        return st


def create(ws, game_dir, name):
    """New workspace for a game project."""
    os.makedirs(os.path.join(ws, "listen"), exist_ok=True)
    os.makedirs(_dir(ws), exist_ok=True)
    if not os.path.exists(state_path(ws)):
        _save(ws, {"state": "new", "game_dir": game_dir, "name": name, "created": agents._now(), "messages": [
            {"role": "system", "text": f"Проєкт створено. Гра: {game_dir}", "time": agents._now()}]})


def recipes():
    out = []
    for f in sorted(os.listdir(RECIPES)) if os.path.isdir(RECIPES) else []:
        if f.endswith(".md") and f != "README.md":
            out.append(f)
    return out


# --- prompts --------------------------------------------------------------------------------------------------
COMMON = """You are Holosii's project setup agent. Holosii is a tool for reviewing and fixing a game's voice-over
translation, line by line. Your job is to get the game's original voice lines into listening folders, and later
to put the translated lines back into the game.

Game folder (READ ONLY — never create, change, move or delete anything in it): {game}
Workspace (everything you make goes here): {ws}
Recipes (read README.md first, then the matching recipe): {recipes}
Project name: {name}

Rules:
- Only the user's own copy of the game, for a personal mod. Do not look for encryption keys, do not bypass DRM,
  anti-cheat or any protection. If the archives are encrypted, say so and stop.
- Put helper scripts in {ws}/tools/, temporary files in {ws}/.holosii/tmp/. Never write outside the workspace.
- Prefer streaming/reading by offset over copying whole multi-GB archives.
- Write every message to the user in Ukrainian, short and plain (the user is not a programmer). Technical
  names (file formats, tools) may stay as they are.
"""

SURVEY = COMMON + """
THIS STEP: SURVEY ONLY. Do not extract everything yet.
1. Find the engine, the archive format, the audio middleware, which voice languages exist and roughly how many
   voiced lines each has (gameplay vs cutscenes if it differs), and where the subtitle text is.
2. Extract and decode at most 10 sample lines (a few per language) into {ws}/.holosii/samples/ as
   <NN>_<lang>.wav, so the user can listen and confirm.
3. Write {ws}/.holosii/plan.json:
{{
  "engine": "…", "audio": "…", "recipe": "<recipe file or null>",
  "languages": [{{"code": "en", "name": "англійська", "lines": 1234, "note": "…"}}],
  "text": "where the subtitles/transcripts come from",
  "samples": [{{"file": "samples/01_en.wav", "lang": "en", "text": "what it says, if known"}}],
  "steps": ["what the extraction will do, in plain Ukrainian", "…"],
  "size": "rough disk space and time the full extraction needs",
  "problems": ["anything you could not open, e.g. compressed entries without a decoder"],
  "blocked": null,
  "questions": ["questions for the user, if any"]
}}
   Set "blocked" to a short Ukrainian reason when it cannot be done within the rules (e.g. encrypted archives).
4. Finish with a short message to the user: what you found and what you propose.
"""

EXTRACT = COMMON + """
THIS STEP: EXTRACTION. The user approved the plan in {ws}/.holosii/plan.json.{note}
1. Write {ws}/tools/extract.py — re-runnable (skips what is already there), never touches the game — and run it.
   It fills {ws}/listen/ with one folder per voice line:
     listen/<group>/<NNN>_<key>/<lang>.wav   one file per original language (en.wav, ja.wav, …)
     listen/<group>/<NNN>_<key>/текст.txt    the original text (subtitle and/or transcript), labelled by language
   <group> = chapter / scene / type when the game's names show it (Latin or the game's own names). <key> = the
   game's own id of the line, so the line can be found again when packing. Keep a machine-readable index of
   every line (key ↔ game file/event/media id) in {ws}/.holosii/lines.json.
   Do not create translation files (ua.wav): the user's voice-over goes there later.
2. Write {ws}/tools/pack.py — builds a mod from translated files (listen/**/ua.wav, or a folder given on the
   command line) into {ws}/build/ only. It must not install anything into the game. Test it on 1–2 lines
   (copy en.wav as a stand-in translation into a temp folder) and check the result decodes; then delete the test.
3. Write {ws}/BRIEF.md for the fix agent (it edits single lines later): where things are, how lines map to
   game files, how to rebuild, what tools exist.
4. If no recipe matched, write what you learned to {ws}/.holosii/recipe_draft.md in the style of the recipes.
5. Write {ws}/.holosii/result.json:
{{"lines": 1234, "languages": ["en", "ja"], "default_ref": "en",
  "extract_cmd": ["python3", "{ws}/tools/extract.py"], "pack_cmd": ["python3", "{ws}/tools/pack.py"],
  "notes": "short Ukrainian summary: what is in listen/, what is missing"}}
6. Finish with a short message to the user.
"""

TALK = COMMON + """
The user writes to you between steps. Answer, and do what they ask if it fits the current step; keep
{ws}/.holosii/plan.json (and result.json, if it exists) up to date when something changes.

User: {text}
"""


def _prompt(kind, ws, st, text=""):
    f = {"game": st.get("game_dir"), "ws": ws, "recipes": RECIPES, "name": st.get("name") or "",
         "text": text, "note": f"\nUser's note: {text}" if text else ""}
    return {"survey": SURVEY, "extract": EXTRACT, "talk": TALK}[kind].format(**f)


# --- running a step -------------------------------------------------------------------------------------------
def start(ws, kind, text=""):
    """kind: survey | extract | talk. Returns an error string or None."""
    if not agents.CLAUDE:
        return "Не знайдено Claude Code (claude)"
    with _lock:
        if ws in _runs:
            return "Агент налаштування вже працює"
    st = load(ws)
    if kind == "extract" and not st.get("plan"):
        return "Спершу потрібен огляд гри і план"
    if kind == "extract" and st["plan"].get("blocked"):
        return "Агент написав, що це не вийде в межах правил: " + str(st["plan"]["blocked"])
    if kind == "talk" and not text.strip():
        return "Порожнє повідомлення"
    game = st.get("game_dir") or ""
    if not os.path.isdir(game):
        return "Теки гри немає: " + game
    settings = agents.load_settings()
    phase = {"survey": "surveying", "extract": "extracting", "talk": "talking"}[kind]
    prev = st["state"]
    msg = {"role": "user", "text": text} if kind == "talk" else \
        {"role": "system", "text": "Огляд гри почато" if kind == "survey" else
         "Видобування почато" + (f". Примітка: {text}" if text else "")}
    _update(ws, state=phase, prev_state=prev, error=None, message=msg, step_started=agents._now(), now="")

    sett = os.path.join(agents.DATA, "agent_settings.json")
    agents._write_json(sett, {"disableAllHooks": True})
    cmd = [agents.CLAUDE, "-p", "--model", settings.get("setup_model") or "claude-opus-5-5",
           "--output-format", "stream-json", "--verbose", "--permission-mode", "acceptEdits",
           "--tools", TOOLS, "--allowedTools", TOOLS, "--settings", sett, "--strict-mcp-config", "--no-chrome",
           "--add-dir", game, "--add-dir", ws]
    if st.get("session_id"):
        cmd += ["--resume", st["session_id"]]
    os.makedirs(os.path.join(_dir(ws), "tmp"), exist_ok=True)
    proc = subprocess.Popen(cmd, cwd=ws, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1, **platform_util.ENC,
                            **platform_util.new_group_kwargs())
    proc.stdin.write(_prompt(kind, ws, st, text))
    proc.stdin.close()
    with _lock:
        _runs[ws] = proc
    threading.Thread(target=_follow, args=(ws, proc, kind, prev, settings), daemon=True).start()
    return None


def stop(ws):
    with _lock:
        proc = _runs.get(ws)
    if not proc:
        return False
    platform_util.kill_tree(proc)                    # the agent and whatever it started (extract scripts)
    _update(ws, stop_requested=True)
    return True


def _follow(ws, proc, kind, prev, settings):
    limit = int(settings.get("setup_max_tokens") or 0)
    timeout = float(settings.get("setup_timeout_min") or 180) * 60
    t0 = time.time()
    tokens = 0
    cost = 0.0
    err = None
    log = open(os.path.join(_dir(ws), "setup.log"), "a", encoding="utf-8")
    log.write(f"\n=== {agents._now()} {kind}\n")
    killer = threading.Timer(timeout, lambda: platform_util.kill_tree(proc))
    killer.daemon = True
    killer.start()
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                log.write(line + "\n")
                continue
            t = ev.get("type")
            if t == "system" and ev.get("subtype") == "init" and ev.get("session_id"):
                _update(ws, session_id=ev["session_id"])
            elif t == "rate_limit_event":
                agents.record_limits(ev.get("rate_limit_info"))
            elif t == "assistant":
                m = ev.get("message") or {}
                u = m.get("usage") or {}
                tokens += sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens",
                                                             "cache_creation_input_tokens"))
                for b in m.get("content") or []:
                    if b.get("type") == "text" and b.get("text", "").strip():
                        _update(ws, message={"role": "agent", "text": b["text"].strip()}, tokens=tokens)
                    elif b.get("type") == "tool_use":
                        s = agents._summ_tool(b)
                        log.write(s + "\n")
                        _update(ws, now=s, tokens=tokens)
                log.flush()
                if limit and tokens > limit:
                    err = f"Перевищено ліміт токенів на крок ({limit:,})".replace(",", " ")
                    platform_util.kill_tree(proc)
            elif t == "result":
                cost = float(ev.get("total_cost_usd") or 0)
                if ev.get("is_error") and not err:
                    err = (ev.get("result") or ev.get("subtype") or "помилка")[:300]
        proc.wait()
    except Exception as e:                           # noqa: BLE001
        err = str(e)[:300]
    finally:
        killer.cancel()
        log.close()
        with _lock:
            _runs.pop(ws, None)
    st = agents._read_json(state_path(ws), {}) or {}
    stopped = st.pop("stop_requested", False)
    if not err and proc.returncode not in (0, None) and not stopped:
        err = f"Агент завершився з кодом {proc.returncode}"
    if time.time() - t0 >= timeout - 1:
        err = f"Крок триває довше {int(timeout // 60)} хв — зупинено"
    plan = os.path.isfile(os.path.join(_dir(ws), "plan.json"))
    result = os.path.isfile(os.path.join(_dir(ws), "result.json"))
    p = agents._read_json(os.path.join(_dir(ws), "plan.json"), {}) if plan else {}
    if stopped:
        new = "stopped"
    elif err:
        new = "error"
    elif result:
        new = "ready"
    elif plan and p.get("blocked"):
        new = "blocked"
    elif plan:
        new = "plan"
    else:
        new = "waiting"                              # the agent asked something instead of writing a plan
    if kind == "talk" and not err and not stopped and prev in ("ready", "done"):
        new = prev
    total_cost = round(float(st.get("cost") or 0) + cost, 3)
    _update(ws, state=new, error=err, now="", stop_requested=False, cost=total_cost,
            tokens_total=int(st.get("tokens_total") or 0) + tokens, step_finished=agents._now(),
            message={"role": "system", "text": "Зупинено" if stopped else ("Помилка: " + err) if err else
                     {"survey": "Огляд завершено", "extract": "Видобування завершено", "talk": "Готово"}[kind]
                     + f" · ≈${cost:.2f}"})


def finish(ws):
    """The user accepts the result: the project becomes a normal Holosii project."""
    st = load(ws)
    if st["state"] != "ready" or not st.get("result"):
        return None, "Видобування ще не завершено"
    _update(ws, state="done", message={"role": "system", "text": "Проєкт відкрито для прослуховування"})
    r = st["result"]
    out = {"default_ref": r.get("default_ref") or (r.get("languages") or ["en"])[0]}
    brief = os.path.join(ws, "BRIEF.md")
    if os.path.isfile(brief):
        out["agent_brief"] = brief
    for k in ("extract_cmd", "pack_cmd"):
        if isinstance(r.get(k), list) and r[k]:
            out[k] = [str(x) for x in r[k]]
    return out, None


def safe_file(ws, rel):
    """A file inside the workspace's .holosii folder (samples), or None."""
    base = os.path.realpath(_dir(ws))
    full = os.path.realpath(os.path.join(base, rel))
    if not full.startswith(base + os.sep) or not os.path.isfile(full):
        return None
    return full


def slug(name):
    s = re.sub(r"[^A-Za-z0-9]+", "_", name or "").strip("_")
    return s[:40] or "project"
