"""Черга правок і агенти Claude Code для Голосія (Holosii), а також зміна гучності скриптом.

Черга — «queue.json», налаштування — «settings.json»,
журнали роботи — тека «logs/». Усе лежить поруч із сервером (або в SLUHACH_DATA для тестів).

Агент один на запуск Голосія: постійний процес Claude Code, правки йдуть йому по черзі.
Розмір його контексту видно в Голосії; «Стиснути» (/compact) або автоматично на порозі auto_compact_at.
"""
import json
import os
import hashlib
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid

import analysis
import tempo
import echo

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("SLUHACH_DATA") or HERE
QUEUE_FILE = os.path.join(DATA, "queue.json")
SETTINGS_FILE = os.path.join(DATA, "settings.json")
LOGS_DIR = os.path.join(DATA, "logs")
VOLUME_TRASH = os.path.expanduser("~/.Trash/Holosii_volume")
HISTORY_DIR = os.path.join(DATA, "history")      # версії файлів для «Скасувати» (⌘Z) і «Повторити» (⌘⇧Z)
HISTORY_MAX = 30
BEFORE_DIR = os.path.join(DATA, "before")        # версія файлу до правки агента (для «до / після»)
OLD_LOGS_TRASH = os.path.expanduser("~/.Trash/Holosii_old_logs")
KEEP_LOGS = 300                                  # журналів правок лишати
KEEP_BEFORE = 150                                # копій «до правки» лишати
AGENT_LOG_MAX = 5 * 1024 * 1024
LIMITS_FILE = os.path.join(DATA, "limits.json")   # останні ліміти плану Claude (5 год / тиждень)

DEFAULT_SETTINGS = {
    "model": "claude-sonnet-5-5",    # модель агента (примусово дешевша)
    "auto_compact_at": 100000,       # стискати контекст, коли він більший (0 — лише вручну)
    "timeout_min": 25,               # максимум хвилин на одну правку
    "max_job_tokens": 1000000,       # ліміт токенів на одну правку (0 — без ліміту)
    "port": 8765,                    # порт сервера (і Holosii.app); змінна PORT має перевагу
    "dictation_lang": "uk",          # мова диктування (Whisper)
    "whisper_model": "",             # шлях до моделі Whisper; порожньо — знайти найкращу в ~/.cache/whisper
    "dictation_prompt": "",          # підказка Whisper: імена й терміни, які треба писати правильно
    "setup_model": "claude-opus-5-5",  # агент налаштування проєкту (видобування з гри) — сильніша модель
    "setup_max_tokens": 5000000,     # ліміт токенів на один крок налаштування (0 — без ліміту)
    "setup_timeout_min": 180,        # максимум хвилин на один крок налаштування
}
OBSOLETE = ("workers", "reset_after")
TOOLS = "Bash,Read,Write,Edit,Glob,Grep"

qcond = threading.Condition()

_find_project = None
_target_tags = []
_source_tags = []


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _write_json(path, data):
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    raw = _read_json(SETTINGS_FILE, {})
    s.update({k: v for k, v in raw.items() if k not in OBSOLETE})
    if not os.path.exists(SETTINGS_FILE) or any(k in raw for k in OBSOLETE) or set(s) - set(raw):
        _write_json(SETTINGS_FILE, s)
    return s


def which(name, extra=()):
    p = shutil.which(name)
    if p:
        return p
    for d in extra:
        c = os.path.join(os.path.expanduser(d), name)
        if os.path.exists(c):
            return c
    return None


CLAUDE = os.environ.get("SLUHACH_CLAUDE") or which("claude", ["~/.local/bin", "/opt/homebrew/bin", "/usr/local/bin"])
FFMPEG = which("ffmpeg", ["/opt/homebrew/bin", "/usr/local/bin"])
FFPROBE = which("ffprobe", ["/opt/homebrew/bin", "/usr/local/bin"])


# ---------- черга ----------

def load_queue():
    return _read_json(QUEUE_FILE, [])


def save_queue(q):
    _write_json(QUEUE_FILE, q)


def agent_ready(project):
    return bool(project and project.get("agent_cwd") and project.get("agent_brief") and CLAUDE)


def target_file(item_files):
    for f in item_files:
        if (f.get("tag") or "").lower() in _target_tags:
            return f
    for f in item_files:
        if (f.get("tag") or "").lower() not in _source_tags:
            return f
    return item_files[-1] if item_files else None


def add_job(project, item, comment, ref=None, ref_file=None):
    """item: {id, name, label, files, text}. ref — мова еталона (None — без еталона). Повертає задачу."""
    with qcond:
        q = load_queue()
        for j in q:
            if j["pid"] == project["id"] and j["item"] == item["id"] and j["status"] == "queued":
                j["comment"] = comment
                j["ref"], j["ref_file"] = ref, ref_file
                j["updated"] = _now()
                save_queue(q)
                qcond.notify_all()
                return j
        job = {
            "id": uuid.uuid4().hex[:8],
            "pid": project["id"], "project": project["name"],
            "item": item["id"], "name": item["name"], "label": item.get("label", ""),
            "files": item["files"], "text": item.get("text", ""),
            "comment": comment, "ref": ref, "ref_file": ref_file, "status": "queued",
            "created": _now(), "updated": _now(),
        }
        q.append(job)
        save_queue(q)
        qcond.notify_all()
        return job


def cancel_job(job_id):
    with qcond:
        q = load_queue()
        for j in q:
            if j["id"] == job_id and j["status"] in ("queued", "running"):
                if j["status"] == "running":
                    j["cancel"] = True               # агент отримає interrupt, сам процес лишиться живим
                j["status"] = "cancelled"
                j["finished"] = _now()
                save_queue(q)
                return True
    return False


def retry_job(job_id):
    with qcond:
        q = load_queue()
        for j in q:
            if j["id"] == job_id and j["status"] in ("error", "cancelled", "done"):
                n = {k: j[k] for k in ("pid", "project", "item", "name", "label", "files", "text", "comment")}
                n.update({k: j[k] for k in ("ref", "ref_file") if k in j})
                n.update(id=uuid.uuid4().hex[:8], status="queued", created=_now(), updated=_now())
                q.append(n)
                save_queue(q)
                qcond.notify_all()
                return n
    return None


def clear_finished():
    with qcond:
        q = [j for j in load_queue() if j["status"] in ("queued", "running", "error")]
        save_queue(q)


def queue_state():
    s = load_settings()
    return {
        "jobs": load_queue(),
        "settings": s,
        "claude": bool(CLAUDE),
        "agent": agent_state(),
    }


def read_log(job_id, limit=12000):
    p = os.path.join(LOGS_DIR, f"{job_id}.log")
    try:
        with open(p, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - limit))
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


# ---------- агент ----------
# Один агент Claude Code на один запуск Голосія: постійний процесс `claude -p --input-format stream-json`,
# якому правки передаються по черзі. Він стартує в окремій теці (щоб не підвантажувати CLAUDE.md проєктів),
# з 6 інструментами, без хуків і MCP — так стартовий контекст ~8 тис. токенів замість ~35 тис.

def _summ_tool(block):
    inp = block.get("input") or {}
    s = inp.get("command") or inp.get("file_path") or inp.get("pattern") or ""
    s = " ".join(str(s).split())
    return f"🔧 {block.get('name')}: {s[:160]}"


class Agent:
    def __init__(self):
        self.proc = None
        self.events = None
        self.state = "stopped"          # stopped | starting | idle | working | compacting | error
        self.ctx = None                 # поточний розмір контексту (токени)
        self.session = None
        self.model = None
        self.dirs = set()
        self.jobs = 0
        self.cost = 0.0                 # сумарна вартість за цінами API (з result.total_cost_usd)
        self.started = None
        self.error = None
        self.compact_requested = False
        self.last_compact = None
        self.briefed = set()            # проєкти, пам'ятку яких агент уже прочитав
        self.log = None

    # --- процес ---
    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, settings, dirs):
        self.stop()
        cwd = os.path.join(DATA, "agent_workdir")
        os.makedirs(cwd, exist_ok=True)
        sett = os.path.join(DATA, "agent_settings.json")
        _write_json(sett, {"disableAllHooks": True})
        cmd = [CLAUDE, "-p", "--model", settings["model"], "--input-format", "stream-json",
               "--output-format", "stream-json", "--verbose", "--permission-mode", "acceptEdits",
               "--tools", TOOLS, "--allowedTools", TOOLS, "--settings", sett, "--strict-mcp-config", "--no-chrome"]
        for d in sorted(dirs):
            cmd += ["--add-dir", d]
        self.proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.events = queue.Queue()
        proc, evq = self.proc, self.events

        def reader():
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    evq.put({"type": "_raw", "text": line})
                    continue
                if ev.get("type") == "assistant":
                    u = (ev.get("message") or {}).get("usage") or {}
                    self.ctx = sum(int(u.get(k) or 0) for k in (
                        "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
                elif ev.get("type") == "rate_limit_event":
                    record_limits(ev.get("rate_limit_info"))
                elif ev.get("type") == "system" and ev.get("subtype") == "init":
                    self.session = ev.get("session_id") or self.session
                evq.put(ev)
            evq.put({"type": "_exit"})

        threading.Thread(target=reader, daemon=True).start()
        self.dirs = set(dirs)
        self.model = settings["model"]
        self.session = None
        self.ctx = None
        self.jobs = 0
        self.cost = 0.0
        self.briefed = set()
        self.started = _now()
        self.error = None
        self.state = "idle"
        self._log(f"=== {_now()} агент запущено, модель {settings['model']}")

    def stop(self):
        if self.alive():
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=5)
            except Exception:                        # noqa: BLE001
                self.proc.kill()
        self.proc = None
        self.state = "stopped"

    def _log(self, text):
        if self.log is None:
            os.makedirs(LOGS_DIR, exist_ok=True)
            self.log = open(os.path.join(LOGS_DIR, "agent.log"), "a", encoding="utf-8")
        if self.log:
            self.log.write(text + "\n")
            self.log.flush()

    def _send(self, text):
        self.proc.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}},
                                         ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def interrupt(self):
        if self.alive():
            try:
                self.proc.stdin.write(json.dumps({"type": "control_request", "request_id": uuid.uuid4().hex,
                                                  "request": {"subtype": "interrupt"}}) + "\n")
                self.proc.stdin.flush()
            except OSError:
                pass

    def turn(self, text, log=None, timeout=None, cancelled=lambda: False, max_tokens=0):
        """Надіслати повідомлення й дочекатися відповіді (event result).
        max_tokens — зупинити агента, якщо правка використала більше токенів."""
        out = {"text": "", "error": True, "tokens": 0, "cost": None, "meta": None, "limit": False}
        self._send(text)
        deadline = time.time() + timeout if timeout else None
        interrupted_at = None
        while True:
            wait = 2.0
            try:
                ev = self.events.get(timeout=wait)
            except queue.Empty:
                now = time.time()
                if (cancelled() or (deadline and now > deadline)) and interrupted_at is None:
                    interrupted_at = now
                    self.interrupt()
                    if log:
                        log.write(f"=== {_now()} зупиняю агента ({'скасовано' if cancelled() else 'перевищено час'})\n")
                        log.flush()
                elif interrupted_at and now - interrupted_at > 60:
                    self.proc.kill()                 # не зупинився — перезапустимо пізніше
                continue
            t = ev.get("type")
            if t == "_exit":
                out["text"] = "Процес агента завершився"
                self.state = "error"
                self.error = out["text"]
                return out
            if t == "assistant":
                u = (ev.get("message") or {}).get("usage") or {}
                out["tokens"] += sum(int(u.get(k) or 0) for k in (
                    "input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
                if max_tokens and out["tokens"] > max_tokens and interrupted_at is None:
                    interrupted_at = time.time()
                    out["limit"] = True
                    self.interrupt()
                    if log:
                        log.write(f"=== {_now()} зупиняю агента: перевищено ліміт {max_tokens} токенів\n")
                        log.flush()
                if log:
                    for b in (ev.get("message") or {}).get("content") or []:
                        if b.get("type") == "text" and b.get("text", "").strip():
                            log.write("💬 " + b["text"].strip() + "\n")
                        elif b.get("type") == "tool_use":
                            log.write(_summ_tool(b) + "\n")
                    log.flush()
            elif t == "system" and ev.get("subtype") == "compact_boundary":
                out["meta"] = ev.get("compact_metadata") or {}
            elif t == "result":
                out["text"] = ev.get("result") or ""
                out["error"] = bool(ev.get("is_error")) or ev.get("subtype") != "success"
                if out["error"] and not out["text"]:
                    out["text"] = "; ".join(ev.get("errors") or []) or str(ev.get("subtype") or "помилка")
                c = ev.get("total_cost_usd")
                if isinstance(c, (int, float)):
                    out["cost"] = max(0.0, c - self.cost) if c >= self.cost else c
                    self.cost = c if c >= self.cost else self.cost + c
                self.session = ev.get("session_id") or self.session
                if interrupted_at:
                    out["error"] = True
                    out["text"] = out["text"] or "Зупинено"
                    if out["limit"]:
                        out["text"] = (f"Зупинено: правка перевищила ліміт {max_tokens:,} токенів".replace(",", " ")
                                       + ". Файл міг лишитися напівготовим — послухай або скасуй (⌘Z).")
                return out

    def compact(self):
        self.state = "compacting"
        before = self.ctx
        self._log(f"=== {_now()} стискаю контекст ({before} токенів)")
        r = self.turn("/compact")
        meta = r.get("meta") or {}
        self.last_compact = {"time": _now(), "before": meta.get("pre_tokens") or before,
                             "after": meta.get("post_tokens")}
        if meta.get("post_tokens"):
            self.ctx = meta["post_tokens"]
        else:
            self.ctx = None                          # точний розмір видно після наступного кроку
        self._log(f"=== {_now()} стиснуто: {self.last_compact}")
        self.state = "idle" if self.alive() else "error"


AGENT = Agent()


def agent_state():
    s = load_settings()
    a = AGENT
    return {
        "state": a.state if (a.alive() or a.state in ("stopped", "error")) else "error",
        "ctx": a.ctx, "auto_compact_at": s.get("auto_compact_at"), "model": a.model or s["model"],
        "jobs": a.jobs, "cost": round(a.cost, 3), "started": a.started, "error": a.error,
        "compact_requested": a.compact_requested, "last_compact": a.last_compact,
        "claude": bool(CLAUDE),
    }


def request_compact():
    with qcond:
        AGENT.compact_requested = True
        qcond.notify_all()


def _prompt(job, project, first):
    root = project["path"]
    tf = target_file(job["files"])
    files = "\n".join(
        f"  - {os.path.join(root, f['path'])}" + ("   ← це треба виправити" if f is tf else "")
        + ("   ← еталон" if job.get("ref_file") and f["path"] == job["ref_file"] else "")
        for f in job["files"])
    ref = ""
    if "ref" in job:                                   # старі задачі без поля — як раніше
        if job.get("ref_file"):
            ref = (f"Еталон: {os.path.join(root, job['ref_file'])} (мова {str(job['ref']).upper()}). "
                   "Якщо в коментарі не сказано інакше, «правильно» означає як в еталоні: слова й таймінги, "
                   "звуки (дихання, зітхання, плач, сміх), гучність частин, висота голосу, луна. "
                   "Працюй за розділом «Еталон» пам'ятки.\n\n")
        else:
            ref = ("Еталону немає: користувач вимкнув його для цієї фрази. Працюй лише за коментарем, "
                   "ні з чим не вирівнюй.\n\n")
    head = ""
    if first:
        head = (f"Проєкт «{project['name']}». Тека проєкту: {project['agent_cwd']}\n"
                "Твоя поточна тека — службова, тож у командах завжди переходь у теку проєкту (cd \"…\").\n"
                f"Спершу уважно прочитай пам'ятку: {project['agent_brief']}\n"
                "Дотримуйся її в усіх наступних завданнях цього проєкту.\n\n")
    return head + (
        f"Завдання {job['id']}\n"
        f"Фраза: {job['item']}\n"
        f"Файли:\n{files}\n\n"
        f"Текст фрази:\n<<<\n{job['text'] or '(немає)'}\n>>>\n\n"
        f"Коментар користувача: «{job['comment']}»\n\n"
        + ref +
        f"Зроби правку за пам'яткою. Результат — один файл поверх {os.path.join(root, tf['path']) if tf else '(файл UA)'} "
        "(стару версію спершу збережи в Кошик). Онови опис у текстовому файлі фрази. Нічого не вбудовуй у гру.\n"
        "Наприкінці відповідай 1–3 реченнями українською: що зроблено і на що звернути увагу при прослуховуванні."
    )


def _project_dirs(find_project):
    import json as _j
    dirs = set()
    try:
        with open(os.environ.get("SLUHACH_PROJECTS") or os.path.join(HERE, "projects.json"), encoding="utf-8") as f:
            for p in _j.load(f):
                for k in ("path", "agent_cwd"):
                    if p.get(k) and os.path.isdir(p[k]):
                        dirs.add(p[k])
    except (OSError, ValueError):
        pass
    return dirs


def _worker(find_project):
    while True:
        with qcond:
            job = None
            while job is None and not AGENT.compact_requested:
                q = load_queue()
                for j in q:
                    if j["status"] == "queued" and agent_ready(find_project(j["pid"])):
                        job = j
                        break
                if job is None:
                    qcond.wait(10)
            if job is None:                          # прохання стиснути контекст
                AGENT.compact_requested = False
            else:
                job["status"] = "running"
                job["worker"] = 1
                job["started"] = _now()
                save_queue(q)
        settings = load_settings()
        if job is None:
            if AGENT.alive() and AGENT.ctx is not None:
                try:
                    AGENT.compact()
                except Exception as e:               # noqa: BLE001
                    AGENT.error = f"Стиснення не вдалося: {e}"
            continue
        project = find_project(job["pid"])
        need = {d for d in (project["path"], project["agent_cwd"]) if os.path.isdir(d)}
        if not AGENT.alive() or not need <= AGENT.dirs or AGENT.model != settings["model"]:
            AGENT.start(settings, _project_dirs(find_project) | need)
        os.makedirs(LOGS_DIR, exist_ok=True)
        logp = os.path.join(LOGS_DIR, f"{job['id']}.log")
        tf = target_file(job["files"])
        tfull = os.path.join(project["path"], tf["path"]) if tf else None
        before = _snapshot_before(job, tfull)
        u0 = project_usage(project, fresh=True)
        AGENT.state = "working"
        try:
            with open(logp, "a", encoding="utf-8") as log:
                log.write(f"=== {_now()} агент бере правку (контекст {AGENT.ctx or '—'} токенів), модель {AGENT.model}\n")
                log.flush()

                def cancelled():
                    return any(j.get("cancel") for j in load_queue() if j["id"] == job["id"])
                r = AGENT.turn(_prompt(job, project, project["id"] not in AGENT.briefed), log,
                               settings["timeout_min"] * 60, cancelled, settings.get("max_job_tokens") or 0)
                log.write(f"=== {_now()} завершено: {'помилка' if r['error'] else 'готово'}, "
                          f"{r['tokens']} токенів, контекст тепер {AGENT.ctx}\n")
            if not r["error"]:
                AGENT.briefed.add(project["id"])
            AGENT.jobs += 1
        except Exception as e:                       # noqa: BLE001
            r = {"error": True, "text": f"Збій агента: {e}", "cost": None, "tokens": None}
        if AGENT.alive() and AGENT.state == "working":
            AGENT.state = "idle"
        check = _after_job(job, project, tfull, before)
        u1 = project_usage(project, fresh=True) if u0 else None
        usage = None
        if u0 and u1 and "used" in u0 and "used" in u1:
            usage = {"label": u1["label"], "spent": max(0, u1["used"] - u0["used"]),
                     "left": (u1["limit"] - u1["used"]) if u1.get("limit") else None}
        with qcond:
            q = load_queue()
            for j in q:
                if j["id"] == job["id"]:
                    if j["status"] != "cancelled":
                        j["status"] = "error" if r["error"] else "done"
                    j["result"] = r["text"]
                    j["cost"] = r.get("cost")
                    j["tokens"] = r.get("tokens")
                    j["ctx_after"] = AGENT.ctx
                    j["finished"] = _now()
                    j["before_file"] = check.pop("before_file", None)
                    j["check"] = check or None
                    j["usage"] = usage
            save_queue(q)
            qcond.notify_all()
        th = settings.get("auto_compact_at") or 0
        if th and AGENT.alive() and (AGENT.ctx or 0) >= th:
            try:
                AGENT.compact()
            except Exception as e:                   # noqa: BLE001
                AGENT.error = f"Стиснення не вдалося: {e}"


# ---------- кредити сервісу генерації (ElevenLabs тощо) ----------
# Проєкт може мати "usage_cmd": команда (список аргументів), що друкує JSON {"used", "limit", "reset"}.
# Ключ API лишається в проєкті: Голосій лише запускає команду. Різниця «до / після» — ціна генерації правки.
_usage_cache = {}
USAGE_TTL = 120


def project_usage(project, fresh=False):
    cmd = project.get("usage_cmd") if project else None
    if not cmd or not isinstance(cmd, list):
        return None
    pid = project["id"]
    c = _usage_cache.get(pid)
    if c and not fresh and time.time() - c["_t"] < USAGE_TTL:
        return {k: v for k, v in c.items() if k != "_t"}
    try:
        r = subprocess.run([str(x) for x in cmd], capture_output=True, text=True, timeout=20,
                           cwd=project.get("agent_cwd") or None)
        d = json.loads(r.stdout.strip().splitlines()[-1])
        if not isinstance(d.get("used"), (int, float)):
            raise ValueError(d.get("error") or "немає used")
    except Exception as e:                           # noqa: BLE001
        out = {"label": project.get("usage_label") or "Генерація", "error": str(e)[:200]}
        _usage_cache[pid] = {**out, "_t": time.time()}
        return out
    out = {"label": project.get("usage_label") or "Генерація", "used": d["used"], "limit": d.get("limit"),
           "reset": d.get("reset")}
    _usage_cache[pid] = {**out, "_t": time.time()}
    return out


# --- ліміти плану Claude ---
# Claude Code сам повідомляє їх у потоці подій («rate_limit_event»): частка використаного 5-годинного й
# тижневого вікна і коли воно скинеться. Голосій лише запам'ятовує останнє — вхід в акаунт не потрібен.
_limits_lock = threading.Lock()
_limits_refreshing = False
LIMITS_WINDOWS = ("five_hour", "seven_day", "seven_day_opus", "seven_day_sonnet")


def record_limits(info):
    if not isinstance(info, dict):
        return
    wins = {}
    for k, w in (info.get("unifiedWindows") or {}).items():
        if isinstance(w, dict) and w.get("utilization") is not None:
            wins[k] = {"used": float(w["utilization"]), "resets": w.get("resetsAt"), "status": w.get("status")}
    k = info.get("rateLimitType")
    if k and k not in wins and info.get("utilization") is not None:
        wins[k] = {"used": float(info["utilization"]), "resets": info.get("resetsAt"), "status": info.get("status")}
    if not wins and not info.get("status"):
        return
    with _limits_lock:
        old = _read_json(LIMITS_FILE, {}) or {}
        merged = {**(old.get("windows") or {}), **wins}
        _write_json(LIMITS_FILE, {"windows": merged, "status": info.get("status"), "seen": int(time.time()),
                                  "overage": bool(info.get("isUsingOverage"))})


def claude_limits():
    """Останні відомі ліміти; вікно, що вже скинулось, показується як 0 %."""
    d = _read_json(LIMITS_FILE, None)
    out = {"available": bool(d and d.get("windows")), "refreshing": _limits_refreshing, "claude": bool(CLAUDE)}
    if not out["available"]:
        return out
    now = time.time()
    wins = {}
    for k, w in d["windows"].items():
        w = dict(w)
        if w.get("resets") and w["resets"] <= now:
            w.update(used=0.0, status="allowed", stale=True, resets=None)
        wins[k] = w
    out.update(windows=wins, seen=d.get("seen"), status=d.get("status"), overage=d.get("overage", False))
    return out


def refresh_limits(wait=False):
    """Дізнатися ліміти зараз: короткий запит до найдешевшої моделі (одна відповідь «ok»)."""
    global _limits_refreshing
    if not CLAUDE or _limits_refreshing:
        return False

    def run():
        global _limits_refreshing
        try:
            cwd = os.path.join(DATA, "agent_workdir")
            os.makedirs(cwd, exist_ok=True)
            _write_json(os.path.join(DATA, "agent_settings.json"), {"disableAllHooks": True})
            p = subprocess.run([CLAUDE, "-p", "--model", "haiku", "--output-format", "stream-json", "--verbose",
                                "--tools", "", "--strict-mcp-config", "--no-chrome", "--no-session-persistence",
                                "--settings", os.path.join(DATA, "agent_settings.json")],
                               cwd=cwd, input="Reply with: ok", capture_output=True, text=True, timeout=90)
            for line in p.stdout.splitlines():
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") == "rate_limit_event":
                    record_limits(ev.get("rate_limit_info"))
        except Exception:                            # noqa: BLE001
            pass
        finally:
            _limits_refreshing = False

    _limits_refreshing = True
    if wait:
        run()
    else:
        threading.Thread(target=run, daemon=True).start()
    return True


def _snapshot_before(job, tfull):
    """Копія цільового файлу до правки агента + крок в історії (⌘Z поверне версію до правки)."""
    if not tfull or not os.path.isfile(tfull):
        return None
    try:
        os.makedirs(BEFORE_DIR, exist_ok=True)
        name = job["id"] + os.path.splitext(tfull)[1].lower()
        shutil.copy2(tfull, os.path.join(BEFORE_DIR, name))
        history_push(tfull)
        return {"name": name, "mtime": os.path.getmtime(tfull)}
    except OSError:
        return None


def _after_job(job, project, tfull, before):
    """Чи змінився файл; виміри нового файлу, еталона й версії до правки; попередження."""
    out = {}
    if not before or not tfull or not os.path.isfile(tfull):
        return out
    if os.path.getmtime(tfull) == before["mtime"]:           # агент файл не чіпав
        history_drop_last(tfull)
        try:
            os.remove(os.path.join(BEFORE_DIR, before["name"]))
        except OSError:
            pass
        return {"changed": False}
    out["before_file"] = before["name"]
    out["changed"] = True
    if not FFMPEG:
        return out
    m = lambda f: analysis.measure(FFMPEG, _measure, _duration, f)  # noqa: E731
    out["new"] = m(tfull)
    out["before"] = m(os.path.join(BEFORE_DIR, before["name"]))
    if job.get("ref_file"):
        rf = os.path.join(project["path"], job["ref_file"])
        if os.path.isfile(rf):
            out["ref"] = m(rf)
            out["ref_lang"] = job.get("ref")
    out["warnings"] = analysis.compare(out["new"], out.get("ref"), out["before"])
    return out


def history_drop_last(full):
    """Прибрати останній крок історії (коли агент файл так і не змінив)."""
    with hist_lock:
        d, meta = _hist(full)
        if meta["undo"]:
            try:
                os.remove(meta["undo"].pop())
            except OSError:
                pass
            _hist_save(d, meta)


def _rotate(folder, keep, skip=()):
    """Старі файли теки — у Кошик (нічого не видаляємо назавжди)."""
    try:
        files = [os.path.join(folder, f) for f in os.listdir(folder) if f not in skip and not f.startswith(".")]
    except OSError:
        return
    files = sorted((f for f in files if os.path.isfile(f)), key=os.path.getmtime)
    old = files[:-keep] if len(files) > keep else []
    if not old:
        return
    dst = os.path.join(OLD_LOGS_TRASH, time.strftime("%Y%m%d_%H%M%S") + "_" + os.path.basename(folder))
    os.makedirs(dst, exist_ok=True)
    for f in old:
        try:
            shutil.move(f, os.path.join(dst, os.path.basename(f)))
        except OSError:
            pass


def rotate_logs():
    _rotate(LOGS_DIR, KEEP_LOGS, skip=("agent.log", "app_server.log"))
    _rotate(BEFORE_DIR, KEEP_BEFORE)
    for name in ("agent.log",):                      # app_server.log Holosii.app перестворює сам
        f = os.path.join(LOGS_DIR, name)
        try:
            if os.path.getsize(f) > AGENT_LOG_MAX:
                os.makedirs(OLD_LOGS_TRASH, exist_ok=True)
                shutil.move(f, os.path.join(OLD_LOGS_TRASH, time.strftime("%Y%m%d_%H%M%S_") + name))
        except OSError:
            pass


def start_workers(find_project, target_tags, source_tags):
    global _target_tags, _source_tags
    _target_tags, _source_tags = target_tags, source_tags
    rotate_logs()
    with qcond:                                      # після перезапуску: незавершені — знову в чергу
        q = load_queue()
        for j in q:
            if j["status"] == "running":
                j["status"] = "queued"
                j["note"] = "перезапущено після зупинки Голосія"
        save_queue(q)
    if CLAUDE:
        try:
            AGENT.start(load_settings(), _project_dirs(find_project))
        except OSError as e:
            AGENT.state, AGENT.error = "error", str(e)
    threading.Thread(target=_worker, args=(find_project,), daemon=True).start()


# ---------- гучність ----------

def _codec_args(full):
    ext = os.path.splitext(full)[1].lower()
    if ext == ".wav":
        c = "pcm_s16le"
        if FFPROBE:
            r = subprocess.run([FFPROBE, "-v", "quiet", "-select_streams", "a:0", "-show_entries",
                                "stream=codec_name", "-of", "csv=p=0", full], capture_output=True, text=True)
            c = r.stdout.strip() or c
        return ["-c:a", c]
    if ext == ".mp3":
        return ["-c:a", "libmp3lame", "-b:a", "192k"]
    return []


# ---------- історія змін (undo / redo) ----------
hist_lock = threading.Lock()


def _hist(full):
    key = hashlib.sha1(os.path.realpath(full).encode("utf-8")).hexdigest()[:16]
    d = os.path.join(HISTORY_DIR, key)
    meta = _read_json(os.path.join(d, "meta.json"), {"file": full, "undo": [], "redo": []})
    return d, meta


def _hist_save(d, meta):
    os.makedirs(d, exist_ok=True)
    _write_json(os.path.join(d, "meta.json"), meta)


def _snapshot(full, d):
    os.makedirs(d, exist_ok=True)
    snap = os.path.join(d, f"{time.time():.6f}{os.path.splitext(full)[1].lower()}")
    shutil.copy2(full, snap)
    return snap


def history_push(full):
    """Перед зміною: поточну версію — в історію, «повторити» очищується."""
    with hist_lock:
        d, meta = _hist(full)
        meta["undo"].append(_snapshot(full, d))
        for old in meta["redo"]:
            try:
                os.remove(old)
            except OSError:
                pass
        meta["redo"] = []
        while len(meta["undo"]) > HISTORY_MAX:
            try:
                os.remove(meta["undo"].pop(0))
            except OSError:
                pass
        _hist_save(d, meta)


def history_state(full):
    with hist_lock:
        _, meta = _hist(full)
        return {"undo": len(meta["undo"]), "redo": len(meta["redo"])}


def history_step(full, redo=False):
    """Скасувати (або повторити) останню зміну файлу. Повертає кількість кроків, що лишились."""
    with hist_lock:
        d, meta = _hist(full)
        src, dst = ("redo", "undo") if redo else ("undo", "redo")
        if not meta[src]:
            raise RuntimeError("Нема чого повторювати" if redo else "Нема чого скасовувати")
        snap = meta[src].pop()
        meta[dst].append(_snapshot(full, d))
        tmp = full + ".tmp" + os.path.splitext(full)[1].lower()
        shutil.copyfile(snap, tmp)
        os.replace(tmp, full)
        os.utime(full, None)                         # новий час — Голосій побачить, що файл змінився
        try:
            os.remove(snap)
        except OSError:
            pass
        _hist_save(d, meta)
        return {"undo": len(meta["undo"]), "redo": len(meta["redo"])}


def _backup(full, rel):
    """Стару версію — у ~/.Trash/Holosii_volume/ (назва латиницею)."""
    os.makedirs(VOLUME_TRASH, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", rel.replace(os.sep, "__")).strip("_") or "file"
    shutil.copy2(full, os.path.join(VOLUME_TRASH, f"{time.strftime('%Y%m%d_%H%M%S')}_{safe}"))


def _measure(full, start=None, end=None):
    """Повертає (LUFS або None, RMS дБ) для всього файлу чи шматка [start, end]."""
    cut = []
    if start is not None:
        cut = ["-ss", f"{start:.3f}", "-t", f"{max(0.01, end - start):.3f}"]
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", *cut, "-i", full, "-af", "ebur128,astats=metadata=0",
                        "-f", "null", "-"], capture_output=True, text=True)
    txt = r.stderr
    lufs = None
    m = re.findall(r"I:\s+(-?[\d.]+|-inf) LUFS", txt)
    if m and m[-1] != "-inf" and float(m[-1]) > -69:
        lufs = float(m[-1])
    rms = None
    m = re.findall(r"RMS level dB:\s+(-?[\d.]+|-inf)", txt)
    if m:
        vals = [float(x) for x in m if x != "-inf"]
        rms = vals[-1] if vals else None          # останній — «Overall»
    return lufs, rms


def _duration(full):
    r = subprocess.run([FFPROBE, "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", full],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def audio_tempo(full, rel, speed=None, length=None, start=None, end=None, ref=None):
    """Змінити темп без зміни висоти (tempo.py / ffmpeg atempo).
    speed — множник (>1 швидше й коротше); length — бажана довжина (файлу чи шматка) у секундах;
    ref — підігнати довжину всього файлу під еталон. Стара версія — у Кошик і в історію (⌘Z)."""
    if not FFMPEG or not FFPROBE:
        raise RuntimeError("Не знайдено ffmpeg")
    total = _duration(full) or 0
    part = start is not None and end is not None
    if part:
        start, end = max(0.0, float(start)), min(total, float(end))
        if end - start < 0.05:
            raise RuntimeError("Виділення закоротке")
    region = (end - start) if part else total
    if ref:
        if part:
            raise RuntimeError("Під еталон підганяється весь файл — зніми виділення")
        if not os.path.isfile(ref):
            raise RuntimeError("Немає файлу еталона")
        length = _duration(ref)
    if length:
        speed = region / float(length)
    if not speed:
        raise RuntimeError("Вкажи, наскільки змінити темп")
    speed = float(speed)
    if abs(speed - 1) < 0.005:
        raise RuntimeError("Довжина вже така — нічого не змінюю")
    _backup(full, rel)
    history_push(full)
    ext = os.path.splitext(full)[1].lower()
    tmp = full + ".tmp" + ext
    try:
        tempo.stretch(FFMPEG, full, tmp, speed, start if part else None, end if part else None, total,
                      _codec_args(full))
    except (ValueError, RuntimeError):
        history_drop_last(full)
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    os.replace(tmp, full)
    return {"speed": round(speed, 3), "before": round(total, 2), "after": round(_duration(full) or 0, 2),
            "history": history_state(full)}


def audio_echo(full, rel, amount, tail, start=None, end=None, tone=4000.0):
    """Додати луну (echo.py): amount 1…100 %, tail — секунд до згасання; весь файл або шматок.
    Гучність лишається тією самою. Стара версія — у Кошик і в історію (⌘Z)."""
    if not FFMPEG or not FFPROBE:
        raise RuntimeError("Не знайдено ffmpeg")
    total = _duration(full) or 0
    part = start is not None and end is not None
    try:
        amount, tail = float(amount), float(tail)
    except (TypeError, ValueError):
        raise RuntimeError("Вкажи силу луни (%) і хвіст (с)")
    _backup(full, rel)
    history_push(full)
    ext = os.path.splitext(full)[1].lower()
    tmp = full + ".tmp" + ext
    try:
        echo.add(FFMPEG, full, tmp, amount, tail, start if part else None, end if part else None, total,
                 float(tone or 4000), _codec_args(full))
    except (ValueError, RuntimeError):
        history_drop_last(full)
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    os.replace(tmp, full)
    return {"amount": amount, "tail": tail, "history": history_state(full)}


def audio_edit(full, rel, op, db=0.0, start=None, end=None, ref=None):
    """op: 'gain' — змінити на db дБ; 'normalize' — підігнати під ref (EN).
    start/end (с) — лише шматок, з плавними краями 20 мс; інакше весь файл. Стеля −1 dBFS."""
    if not FFMPEG or not FFPROBE:
        raise RuntimeError("Не знайдено ffmpeg")
    dur = _duration(full) or 0
    part = start is not None and end is not None
    if part:
        start, end = max(0.0, float(start)), min(dur or float(end), float(end))
        if end - start < 0.05:
            raise RuntimeError("Виділення закоротке")
    info = {}
    if op == "normalize":
        has_ref = bool(ref and os.path.isfile(ref))
        if not has_ref and not part:
            raise RuntimeError("Немає англійського файлу — весь файл нема під що нормалізувати")
        if part:
            if has_ref:
                _, er = _measure(ref, start, end)
                if er is None or er < -60:            # в EN тут тиша — рівняємо на загальну гучність EN
                    _, er = _measure(ref)
            else:                                     # без EN — під гучність решти цього ж файлу
                _, er = _measure(full)
            _, ur = _measure(full, start, end)
            if ur is None or ur < -70:
                raise RuntimeError("У виділенні тиша — нема що нормалізувати")
            db = er - ur
            info.update(en=round(er, 1), before=round(ur, 1), unit="дБ RMS")
        else:
            el, er = _measure(ref)
            ul, ur = _measure(full)
            if el is not None and ul is not None:
                db = el - ul
                info.update(en=round(el, 1), before=round(ul, 1), unit="LUFS")
            else:
                db = er - ur
                info.update(en=round(er, 1), before=round(ur, 1), unit="дБ RMS")
    db = max(-30.0, min(30.0, float(db)))
    if abs(db) < 0.05:
        raise RuntimeError("Гучність уже така сама — нічого не змінюю")
    g = 10 ** (db / 20)
    if part:
        r_ = 0.02
        expr = (f"1+({g:.6f}-1)*max(0,min(1,min((t-{start:.4f})/{r_},({end:.4f}-t)/{r_})))")
        af = f"asetnsamples=n=64:p=0,volume=volume='{expr}':eval=frame"
    else:
        af = f"volume={db:.2f}dB"
    af += ",alimiter=limit=0.891:attack=3:release=60:level=disabled"
    _backup(full, rel)
    history_push(full)
    ext = os.path.splitext(full)[1].lower()
    tmp = full + ".tmp" + ext
    r = subprocess.run([FFMPEG, "-v", "error", "-y", "-i", full, "-af", af, "-map_metadata", "0",
                        *_codec_args(full), tmp], capture_output=True, text=True)
    if r.returncode != 0:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise RuntimeError("ffmpeg: " + r.stderr.strip()[-300:])
    os.replace(tmp, full)
    info["db"] = round(db, 1)
    info["history"] = history_state(full)
    if op == "normalize":
        if part:
            info["after"] = round(_measure(full, start, end)[1] or 0, 1)
        else:
            l, rr = _measure(full)
            info["after"] = round(l if info["unit"] == "LUFS" else rr, 1)
    return info
