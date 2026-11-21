#!/usr/bin/env python3
"""Голосій (англ. Holosii) — локальний плеєр для прослуховування реплік з ігор.

Запуск:  python3 server.py        (або подвійний клік по «Holosii.command»)
Відкриває http://localhost:8765 у браузері.

Проєкти (ігри) записані в «projects.json» поруч зі скриптом.
Позначки й коментарі кожної гри лежать у «summary.json» у корені папки гри (один файл на гру).
Сервер слухає лише 127.0.0.1 — ззовні до нього не достукатись.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser

import agents
import dictation
import platform_util
import setup_agent
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECTS_FILE = os.environ.get("SLUHACH_PROJECTS") or os.path.join(HERE, "projects.json")
PAGE_FILE = os.path.join(HERE, "index.html")
STATIC_DIR = os.path.join(HERE, "static")
FEEDBACK_NAME = "summary.json"
STATE_FILE = os.path.join(os.environ.get("SLUHACH_DATA") or HERE, "state.json")   # останній відкритий проєкт тощо
OLD_FEEDBACK_NAMES = ("відгук.json",)   # старі назви — переносяться в summary.json автоматично
HOST = "127.0.0.1"
# Порт: змінна PORT → "port" у settings.json → 8765 (Holosii.app читає той самий settings.json)
PORT = int(os.environ.get("PORT") or agents.load_settings().get("port") or 8765)

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".aif", ".aiff"}
MIME = {
    ".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac",
    ".flac": "audio/flac", ".ogg": "audio/ogg", ".opus": "audio/ogg",
    ".aif": "audio/aiff", ".aiff": "audio/aiff",
}
# Мітки мови/версії у назвах файлів: en.wav, ua.wav, Line_010_en.mp3 ...
SOURCE_TAGS = ["en", "eng", "orig", "original", "src", "ref", "ja", "jp", "jpn", "old",
               "ko", "zh", "fr", "de", "es", "it", "pt", "pl"]
TARGET_TAGS = ["ua", "uk", "ukr", "new"]
TAGS = "|".join(SOURCE_TAGS + TARGET_TAGS)
# Синоніми мов → один код (для вибору еталона): eng → en, jp/jpn → ja, uk/ukr → ua
LANG_ALIAS = {"eng": "en", "jp": "ja", "jpn": "ja", "uk": "ua", "ukr": "ua"}
# Назви мов для підказок в інтерфейсі; проєкт може доповнити їх полем "lang_names" у projects.json
LANG_NAMES = {"en": "англійська", "ja": "японська", "ua": "українська", "ko": "корейська",
              "zh": "китайська", "fr": "французька", "de": "німецька", "es": "іспанська", "pl": "польська"}


def canon(tag):
    t = (tag or "").lower()
    return LANG_ALIAS.get(t, t)


def resolve_ref(project, item, want=None):
    """Еталон для агента: файл-оригінал вибраної мови. want: код мови, "none" або None (= за замовчуванням)."""
    srcs = [f for f in item["files"] if (f.get("tag") or "").lower() in SOURCE_TAGS]
    if want == "none" or not srcs:
        return None, None
    by = {canon(f["tag"]): f for f in srcs}
    for lang in (want, project.get("default_ref")):
        if lang and lang in by:
            return lang, by[lang]
    f = srcs[0]
    return canon(f["tag"]), f
TAG_ONLY = re.compile(rf"(?i)^({TAGS})$")
TAG_SUFFIX = re.compile(rf"(?i)^(.+?)[ _.\-]({TAGS})$")

lock = threading.Lock()
lock_migrate = threading.Lock()


# ---------- допоміжне ----------

def nat_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def project_id(path):
    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:10]


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_text(path, limit=40000):
    try:
        with open(path, "rb") as f:
            return f.read(limit).decode("utf-8", "replace").strip()
    except OSError:
        return ""


def load_projects():
    try:
        with open(PROJECTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []
    for p in data:
        p["id"] = project_id(p["path"])
    return data


def save_projects(projects):
    write_json(PROJECTS_FILE, [{k: v for k, v in p.items() if k != "id"} for p in projects])


def find_project(pid):
    for p in load_projects():
        if p["id"] == pid:
            return p
    return None


def feedback_path(project):
    path = os.path.join(project["path"], FEEDBACK_NAME)
    migrate_feedback(project["path"], path)
    return path


def migrate_feedback(root, path):
    """відгук.json → summary.json. Якщо є обидва — злити (новіший запис перемагає), старий файл у Кошик."""
    for old in OLD_FEEDBACK_NAMES:
        op = os.path.join(root, old)
        if not os.path.exists(op):
            continue
        with lock_migrate:
            if not os.path.exists(op):
                continue
            try:
                with open(op, encoding="utf-8") as f:
                    od = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            nd = {}
            if os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        nd = json.load(f)
                except (OSError, json.JSONDecodeError):
                    nd = {}
            items = dict(nd.get("items") or {})
            for k, v in (od.get("items") or {}).items():
                if k not in items or str(v.get("updated", "")) > str(items[k].get("updated", "")):
                    items[k] = v
            nd.update({k: v for k, v in od.items() if k != "items" and k not in nd})
            nd["items"] = dict(sorted(items.items(), key=lambda kv: nat_key(kv[0])))
            write_json(path, nd)
            trash = os.path.join(os.environ.get("SLUHACH_DATA") or HERE, "old_feedback")
            os.makedirs(trash, exist_ok=True)
            safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", os.path.basename(root)).strip("_") or "project"
            os.replace(op, os.path.join(trash, f"{time.strftime('%Y%m%d_%H%M%S')}_{safe}_feedback_old.json"))


def load_feedback(project):
    try:
        with open(feedback_path(project), encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data.setdefault("items", {})
    return data


# ---------- готовність тек до вбудовування ----------
# summary.json → "folders": { "<тека>": {"ready": "...", "ready_ts": 0.0, "embedded": "...", "note": "..."} }

def in_folder(item, label):
    return item["label"] == label or item["label"].startswith(label + "/")


def folder_problems(label, items, fb, jobs, since=None):
    """Чому теку не можна вважати готовою. Порожній список — готова.
    since — час позначки «готова»: файли, змінені пізніше, теж проблема."""
    members = [it for it in items if in_folder(it, label)]
    if not members:
        return ["у теці немає фраз"]
    busy = {j["item"] for j in jobs if j["status"] in ("queued", "running")}
    n = {"fix": 0, "unheard": 0, "notok": 0, "updated": 0, "queue": 0, "changed": 0}
    for it in members:
        e = fb.get(it["id"]) or {}
        st = e.get("status")
        if it["id"] in busy:
            n["queue"] += 1
        if st == "fix":
            n["fix"] += 1
        elif st != "ok":
            n["notok"] += 1 if e.get("heard") else 0
            n["unheard"] += 0 if e.get("heard") else 1
        if e.get("heardAt") and it["mtime"] > e["heardAt"] + 1:
            n["updated"] += 1
        if since and it["mtime"] > since + 1:
            n["changed"] += 1
    words = {"fix": "«Виправити»", "unheard": "не прослухано", "notok": "без позначки «Готово»",
             "updated": "оновлено після прослуховування", "queue": "у черзі агента", "changed": "змінено після позначки"}
    return [f"{words[k]}: {v}" for k, v in n.items() if v]


def check_ready_folders(project, items=None, fb_data=None):
    """Зняти позначку «готова» з тек, у яких щось змінилось. Повертає оновлений summary."""
    fb_data = fb_data or load_feedback(project)
    folders = fb_data.get("folders") or {}
    if not any(v.get("ready") for v in folders.values()):
        return fb_data
    if items is None:
        items, _ = scan(project["path"])
    jobs = [j for j in agents.load_queue() if j["pid"] == project["id"]]
    changed = False
    for label, v in folders.items():
        if v.get("ready"):
            probs = folder_problems(label, items, fb_data["items"], jobs, v.get("ready_ts"))
            if probs:
                v.pop("ready", None)
                v.pop("ready_ts", None)
                v["unready"] = time.strftime("%Y-%m-%dT%H:%M:%S") + " — " + "; ".join(probs)
                changed = True
    if changed:
        write_json(feedback_path(project), fb_data)
    return fb_data


def tag_rank(tag):
    t = (tag or "").lower()
    if t in SOURCE_TAGS:
        return (0, SOURCE_TAGS.index(t))
    if t in TARGET_TAGS:
        return (2, TARGET_TAGS.index(t))
    return (1, 0)


# ---------- сканування папки проєкту ----------

def scan(root):
    """Фраза = або папка з файлами en.wav/ua.wav (+ текст.txt),
    або окремий аудіофайл (разом з однойменним .txt і парою *_en / *_ua)."""
    items, notes = [], {}
    root = os.path.abspath(root)
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted((x for x in dirs if not x.startswith(".")), key=nat_key)
        rel = os.path.relpath(d, root).replace(os.sep, "/")   # "/" в id і шляхах і на Windows
        rel = "" if rel == "." else rel
        files = sorted(
            (f for f in files if not f.startswith(".") and f != FEEDBACK_NAME and f not in OLD_FEEDBACK_NAMES and ".tmp" not in f),
            key=nat_key,
        )
        audio = [f for f in files if os.path.splitext(f)[1].lower() in AUDIO_EXT]
        txts = [f for f in files if f.lower().endswith(".txt")]

        folder_files, groups = [], {}
        for f in audio:
            stem = os.path.splitext(f)[0]
            m_only = TAG_ONLY.match(stem)
            if m_only:
                folder_files.append({"name": f, "tag": m_only.group(1).lower()})
                continue
            m = TAG_SUFFIX.match(stem)
            key, tag = (m.group(1), m.group(2).lower()) if m else (stem, "")
            groups.setdefault(key, []).append({"name": f, "tag": tag})

        used = set()

        def mk(item_id, name, label, flist, tlist):
            flist = sorted(flist, key=lambda x: (tag_rank(x["tag"]), nat_key(x["name"])))
            for x in flist:
                x["path"] = f"{rel}/{x['name']}" if rel else x["name"]
                try:
                    x["mtime"] = round(os.path.getmtime(os.path.join(d, x["name"])), 2)
                except OSError:
                    x["mtime"] = 0
            parts = []
            for t in tlist:
                body = read_text(os.path.join(d, t))
                parts.append(body if len(tlist) == 1 else f"— {t} —\n{body}")
            return {"id": item_id, "name": name, "label": label, "files": flist, "text": "\n\n".join(parts),
                    "mtime": max((x["mtime"] for x in flist), default=0)}

        if folder_files:
            rest = [t for t in txts if os.path.splitext(t)[0] not in groups]
            used.update(rest)
            name = os.path.basename(rel) if rel else os.path.basename(root)
            items.append(mk(rel or ".", name, os.path.dirname(rel), folder_files, rest))

        for key, flist in groups.items():
            stems = {key} | {os.path.splitext(x["name"])[0] for x in flist}
            tl = [t for t in txts if os.path.splitext(t)[0] in stems]
            used.update(tl)
            item_id = f"{rel}/{key}" if rel else key
            items.append(mk(item_id, key, rel, flist, tl))

        left = [t for t in txts if t not in used]
        if left:
            notes[rel] = "\n\n".join(
                (f"— {t} —\n" if len(left) > 1 else "") + read_text(os.path.join(d, t)) for t in left
            )

    order = {it["id"]: i for i, it in enumerate(items)}
    items.sort(key=lambda it: ([nat_key(p) for p in it["label"].split("/")] if it["label"] else [], order[it["id"]]))
    return items, notes


def safe_join(root, rel):
    root = os.path.realpath(root)
    full = os.path.realpath(os.path.join(root, rel))
    if full != root and not full.startswith(root + os.sep):
        return None
    return full


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    server_version = "Holosii/1.0"

    def log_message(self, fmt, *args):
        pass  # тиша в Терміналі

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def error(self, msg, code=400):
        self.send_json({"error": msg}, code)

    def body_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def qs(self):
        u = urlparse(self.path)
        return u.path, {k: v[0] for k, v in parse_qs(u.query).items()}

    # --- захист від чужих сайтів ---
    # Сервер слухає лише 127.0.0.1, але браузер може надіслати сюди запит з будь-якого відкритого сайту
    # (CSRF), а також через підміну DNS (DNS rebinding). Черга правок запускає агента з Bash, тож:
    #  - Host має бути localhost / 127.0.0.1 / [::1] з нашим портом;
    #  - POST: якщо є Origin, він має бути нашою ж сторінкою; тіло — лише application/json
    #    (такий запит браузер не відправить з чужого сайту без дозволу CORS, а дозволу ми не даємо).
    def allowed(self, post=False):
        hosts = {f"{h}:{PORT}" for h in ("localhost", "127.0.0.1", "[::1]")}
        host = (self.headers.get("Host") or "").lower()
        if host not in hosts:
            return False
        if post:
            origin = self.headers.get("Origin")
            if origin is not None and origin.lower() not in {"http://" + h for h in hosts}:
                return False
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if int(self.headers.get("Content-Length") or 0) and ctype != "application/json":
                return False
        return True

    # --- GET ---
    def do_GET(self):
        path, q = self.qs()
        if not self.allowed():
            return self.error("Заборонено", 403)
        try:
            if path in ("/", "/index.html"):
                with open(PAGE_FILE, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            elif path.startswith("/static/") or path.startswith("/docs/"):
                # стилі й скрипти сторінки (static/app.css, static/js/*.js) і документація (/docs/ → static/docs/)
                rel = path[len("/static/"):] if path.startswith("/static/") else "docs/" + (path[len("/docs/"):] or "index.html")
                rel = unquote(rel)
                full = os.path.normpath(os.path.join(STATIC_DIR, rel))
                ext = os.path.splitext(full)[1].lower()
                allowed = (".css", ".js", ".html") if full.startswith(os.path.join(STATIC_DIR, "docs") + os.sep) else (".css", ".js")
                if not full.startswith(STATIC_DIR + os.sep) or ext not in allowed or not os.path.isfile(full):
                    return self.error("Немає такого файлу", 404)
                with open(full, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", {".css": "text/css", ".js": "text/javascript", ".html": "text/html"}[ext] + "; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            elif path == "/api/state":
                try:
                    with open(STATE_FILE, encoding="utf-8") as f:
                        self.send_json(json.load(f))
                except (OSError, json.JSONDecodeError):
                    self.send_json({})
            elif path == "/api/projects":
                out = []
                for p in load_projects():
                    fbd = load_feedback(p) if os.path.isdir(p["path"]) else {"items": {}}
                    fb = fbd["items"]
                    fl = fbd.get("folders") or {}
                    sst = setup_agent.load(p["workspace"]) if p.get("workspace") else None
                    if sst:
                        sst = {"state": sst["state"], "running": sst["running"]}
                    out.append({**p, "exists": os.path.isdir(p["path"]), "agent": agents.agent_ready(p), "setup": sst,
                                "ok": sum(1 for v in fb.values() if v.get("status") == "ok"),
                                "heard": sum(1 for v in fb.values() if v.get("heard") or v.get("status")),
                                "ready_folders": sum(1 for v in fl.values() if v.get("ready") and not (v.get("embedded") and v["embedded"] >= v["ready"])),
                                "embedded_folders": sum(1 for v in fl.values() if v.get("embedded")),
                                "last_change": max((v.get("updated") or "" for v in fb.values()), default=""),
                                "fix": sum(1 for v in fb.values() if v.get("status") in ("fix", "regen"))})
                self.send_json(out)
            elif path == "/api/project":
                p = find_project(q.get("p", ""))
                if not p:
                    return self.error("Проєкт не знайдено", 404)
                if not os.path.isdir(p["path"]):
                    return self.error("Папки проєкту не існує: " + p["path"], 404)
                items, notes = scan(p["path"])
                with lock:
                    fbd = check_ready_folders(p, items)
                # коментарі старшої моделі / оркестратора: <проєкт>/reviews.json, у застосунку лише для читання
                try:
                    with open(os.path.join(p["path"], "reviews.json"), encoding="utf-8") as rf:
                        reviews = json.load(rf)
                except (OSError, ValueError):
                    reviews = {}
                self.send_json({"project": p, "items": items, "notes": notes, "reviews": reviews,
                                "feedback": fbd["items"], "folders": fbd.get("folders") or {}})
            elif path == "/api/queue":
                self.send_json(agents.queue_state())
            elif path == "/api/config":
                # мітки й мови — одне джерело для сервера й сторінки
                self.send_json({"source_tags": SOURCE_TAGS, "target_tags": TARGET_TAGS,
                                "lang_alias": LANG_ALIAS, "lang_names": LANG_NAMES,
                                "reveal_label": platform_util.REVEAL_LABEL})
            elif path == "/api/usage":
                # кредити сервісу генерації проєкту (кеш 2 хв; fresh=1 — оновити)
                p = find_project(q.get("p", ""))
                if not p:
                    return self.error("Проєкт не знайдено", 404)
                self.send_json({"usage": agents.project_usage(p, fresh=q.get("fresh") == "1")})
            elif path == "/api/setup":
                # стан налаштування проєкту з гри: крок, повідомлення агента, план, результат
                p = find_project(q.get("p", ""))
                if not p or not p.get("workspace"):
                    return self.error("Це не проєкт з гри", 404)
                st = setup_agent.load(p["workspace"])
                st["recipes"] = setup_agent.recipes()
                self.send_json({"project": {k: p.get(k) for k in ("id", "name", "game_dir", "workspace", "path")},
                                "setup": st})
            elif path == "/api/setup/file":
                p = find_project(q.get("p", ""))
                full = setup_agent.safe_file(p["workspace"], q.get("f", "")) if p and p.get("workspace") else None
                if not full:
                    return self.error("Не знайдено", 404)
                return self.send_file(full)
            elif path == "/api/limits":
                # ліміти плану Claude (5 год / тиждень), останні відомі
                self.send_json(agents.claude_limits())
            elif path == "/api/dictation":
                # чи доступне диктування (локальний Whisper) і чому ні
                self.send_json(dictation.status(agents.load_settings()))
            elif path == "/api/before":
                # версія файлу до правки агента (для «до / після»)
                job = next((j for j in agents.load_queue() if j["id"] == q.get("id")), None)
                name = job and job.get("before_file")
                full = os.path.join(agents.BEFORE_DIR, name) if name else None
                if not full or os.path.basename(name) != name or not os.path.isfile(full):
                    return self.error("Версії до правки немає", 404)
                self.send_file(full)
            elif path == "/api/queue/log":
                self.send_json({"log": agents.read_log(q.get("id", ""))})
            elif path == "/file":
                p = find_project(q.get("p", ""))
                full = safe_join(p["path"], q.get("f", "")) if p else None
                if not full or not os.path.isfile(full):
                    return self.error("Файл не знайдено", 404)
                self.send_file(full)
            else:
                self.error("Немає такої сторінки", 404)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_file(self, full):
        size = os.path.getsize(full)
        ctype = MIME.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        m = re.match(r"bytes=(\d*)-(\d*)", rng or "")
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                if m.group(2):
                    end = min(int(m.group(2)), size - 1)
            else:
                start = max(0, size - int(m.group(2)))
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        length = end - start + 1
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with open(full, "rb") as f:
            f.seek(start)
            while length > 0:
                chunk = f.read(min(256 * 1024, length))
                if not chunk:
                    break
                self.wfile.write(chunk)
                length -= len(chunk)

    # --- POST ---
    def do_POST(self):
        path, q = self.qs()
        if not self.allowed(post=True):
            return self.error("Заборонено: запит не з Голосія", 403)
        try:
            data = self.body_json()
        except json.JSONDecodeError:
            return self.error("Некоректний JSON")
        try:
            if path == "/api/feedback":
                p = find_project(q.get("p", ""))
                if not p or not os.path.isdir(p["path"]):
                    return self.error("Проєкт не знайдено", 404)
                with lock:
                    fb = load_feedback(p)
                    for item_id, entry in (data.get("items") or {}).items():
                        clean = {}
                        if isinstance(entry, dict):
                            st = entry.get("status")
                            if st in ("ok", "fix", "regen"):
                                clean["status"] = "fix" if st == "regen" else st
                            if str(entry.get("comment") or "").strip():
                                clean["comment"] = str(entry["comment"])
                            if entry.get("heard"):
                                clean["heard"] = True
                            if isinstance(entry.get("heardAt"), (int, float)):
                                clean["heardAt"] = round(entry["heardAt"], 2)
                            r = entry.get("ref")
                            if isinstance(r, str) and re.fullmatch(r"[a-z]{2,8}", r):
                                clean["ref"] = r          # вибраний еталон фрази ("none" — без еталона)
                        if clean:
                            clean["updated"] = entry.get("updated") or time.strftime("%Y-%m-%dT%H:%M:%S")
                            fb["items"][item_id] = clean
                        else:
                            fb["items"].pop(item_id, None)
                    fb["project"] = p["name"]
                    fb["items"] = dict(sorted(fb["items"].items(), key=lambda kv: nat_key(kv[0])))
                    write_json(feedback_path(p), fb)
                    fb = check_ready_folders(p, None, fb)
                self.send_json({"ok": True, "folders": fb.get("folders") or {}})
            elif path == "/api/state":
                st = {}
                try:
                    with open(STATE_FILE, encoding="utf-8") as f:
                        st = json.load(f)
                except (OSError, json.JSONDecodeError):
                    pass
                for k in ("last_project",):
                    if k in data:
                        st[k] = data[k]
                write_json(STATE_FILE, st)
                self.send_json({"ok": True})
            elif path == "/api/folder":
                # {label, action: "ready" | "unready" | "embedded"}
                p = find_project(q.get("p", ""))
                if not p or not os.path.isdir(p["path"]):
                    return self.error("Проєкт не знайдено", 404)
                label = str(data.get("label") or "")
                action = data.get("action")
                if not label:
                    return self.error("Не вказано теку")
                with lock:
                    fb = load_feedback(p)
                    folders = fb.setdefault("folders", {})
                    v = folders.setdefault(label, {})
                    now = time.strftime("%Y-%m-%dT%H:%M:%S")
                    if action == "ready":
                        items, _ = scan(p["path"])
                        jobs = [j for j in agents.load_queue() if j["pid"] == p["id"]]
                        probs = folder_problems(label, items, fb["items"], jobs)
                        if probs:
                            return self.error("Тека ще не готова: " + "; ".join(probs))
                        v.update(ready=now, ready_ts=round(time.time(), 2))
                        v.pop("unready", None)
                    elif action == "unready":
                        v.pop("ready", None)
                        v.pop("ready_ts", None)
                        v["unready"] = now + " — знято вручну"
                    elif action == "embedded":
                        if not v.get("ready"):
                            return self.error("Тека не позначена як готова")
                        v["embedded"] = now
                        if data.get("note"):
                            v["embedded_note"] = str(data["note"])
                    else:
                        return self.error("Невідома дія")
                    fb["folders"] = dict(sorted(folders.items(), key=lambda kv: nat_key(kv[0])))
                    write_json(feedback_path(p), fb)
                self.send_json({"ok": True, "folders": fb["folders"]})
            elif path == "/api/queue/add":
                p = find_project(q.get("p", ""))
                if not p or not os.path.isdir(p["path"]):
                    return self.error("Проєкт не знайдено", 404)
                if not agents.agent_ready(p):
                    return self.error("Для цього проєкту агент не налаштований")
                comment = str(data.get("comment") or "").strip()
                if not comment:
                    return self.error("Спершу напишіть коментар")
                items, _ = scan(p["path"])
                item = next((it for it in items if it["id"] == data.get("item")), None)
                if not item:
                    return self.error("Фразу не знайдено", 404)
                want = data.get("ref")
                want = str(want).lower() if want else None
                lang, rf = resolve_ref(p, item, want)
                job = agents.add_job(p, item, comment, lang, rf and rf["path"])
                with lock:                                   # фраза в черзі завжди позначена «Виправити»
                    fb = load_feedback(p)
                    e = fb["items"].get(item["id"]) or {}
                    if e.get("status") != "fix":
                        e = {**e, "status": "fix", "heard": True, "heardAt": round(time.time(), 2),
                             "updated": time.strftime("%Y-%m-%dT%H:%M:%S")}
                        e.setdefault("comment", comment.splitlines()[0][:200])
                        fb["items"][item["id"]] = e
                        write_json(feedback_path(p), fb)
                self.send_json({"ok": True, "job": job})
            elif path == "/api/queue/cancel":
                self.send_json({"ok": agents.cancel_job(str(data.get("id")))})
            elif path == "/api/queue/retry":
                j = agents.retry_job(str(data.get("id")))
                self.send_json({"ok": bool(j), "job": j})
            elif path == "/api/limits/refresh":
                self.send_json({"ok": agents.refresh_limits()})
            elif path == "/api/agent/compact":
                if agents.AGENT.ctx is None or not agents.AGENT.alive():
                    return self.error("Агент ще нічого не робив — стискати нічого")
                agents.request_compact()
                self.send_json({"ok": True})
            elif path == "/api/agent/restart":
                if agents.AGENT.state in ("working", "compacting"):
                    return self.error("Агент зараз працює — зачекай, поки закінчить")
                agents.AGENT.start(agents.load_settings(), agents._project_dirs(find_project))
                self.send_json({"ok": True})
            elif path == "/api/queue/clear":
                agents.clear_finished()
                self.send_json({"ok": True})
            elif path == "/api/audio-undo":
                p = find_project(q.get("p", ""))
                rel = str(data.get("f") or "")
                full = safe_join(p["path"], rel) if p else None
                if not full or not os.path.isfile(full):
                    return self.error("Файл не знайдено", 404)
                try:
                    h = agents.history_step(full, bool(data.get("redo")))
                except RuntimeError as e:
                    return self.error(str(e))
                self.send_json({"ok": True, "mtime": round(os.path.getmtime(full), 2), "history": h})
            elif path == "/api/audio-history":
                p = find_project(q.get("p", ""))
                full = safe_join(p["path"], str(data.get("f") or "")) if p else None
                self.send_json(agents.history_state(full) if full and os.path.isfile(full) else {"undo": 0, "redo": 0})
            elif path in ("/api/volume", "/api/audio-edit"):
                p = find_project(q.get("p", ""))
                rel = str(data.get("f") or "")
                full = safe_join(p["path"], rel) if p else None
                if not full or not os.path.isfile(full):
                    return self.error("Файл не знайдено", 404)
                ref = safe_join(p["path"], str(data.get("ref") or "")) if data.get("ref") else None
                try:
                    if data.get("op") == "echo":
                        # луна: amount (%), tail (с), tone (Гц, необов'язково); весь файл або start/end
                        info = agents.audio_echo(full, rel, data.get("amount"), data.get("tail"),
                                                 data.get("start"), data.get("end"), data.get("tone"))
                    elif data.get("op") == "tempo":
                        # темп без зміни висоти: speed (множник) або length (с); fit_ref — довжина як в еталоні
                        info = agents.audio_tempo(full, rel, data.get("speed"), data.get("length"),
                                                  data.get("start"), data.get("end"),
                                                  ref if data.get("fit_ref") else None)
                    else:
                        info = agents.audio_edit(full, rel, data.get("op", "gain"), data.get("db", 0),
                                                 data.get("start"), data.get("end"), ref)
                except (RuntimeError, ValueError, TypeError) as e:
                    return self.error(str(e))
                self.send_json({"ok": True, "mtime": round(os.path.getmtime(full), 2), "info": info})
            elif path == "/api/dictate":
                # {audio: base64, ext: "webm"|"mp4"|"wav"} → {text}
                import base64
                try:
                    raw = base64.b64decode(str(data.get("audio") or ""), validate=True)
                except ValueError:
                    return self.error("Некоректний запис")
                if not raw:
                    return self.error("Порожній запис")
                ext = re.sub(r"[^a-z0-9]", "", str(data.get("ext") or "webm").lower())[:5] or "webm"
                try:
                    text = dictation.transcribe(agents.FFMPEG, raw, ext, agents.load_settings())
                except (RuntimeError, subprocess.TimeoutExpired) as e:
                    return self.error(str(e))
                self.send_json({"ok": True, "text": text})
            elif path in ("/api/setup/start", "/api/setup/stop", "/api/setup/finish", "/api/setup/reveal"):
                p = find_project(q.get("p", ""))
                if not p or not p.get("workspace"):
                    return self.error("Це не проєкт з гри", 404)
                ws = p["workspace"]
                if path == "/api/setup/start":
                    kind = str(data.get("kind") or "")
                    if kind not in ("survey", "extract", "talk"):
                        return self.error("Невідомий крок")
                    err = setup_agent.start(ws, kind, str(data.get("text") or "")[:4000])
                    if err:
                        return self.error(err)
                    self.send_json({"ok": True})
                elif path == "/api/setup/stop":
                    self.send_json({"ok": setup_agent.stop(ws)})
                elif path == "/api/setup/reveal":
                    platform_util.open_folder(ws)            # робоча тека у Finder / Explorer
                    self.send_json({"ok": True})
                else:
                    extra, err = setup_agent.finish(ws)
                    if err:
                        return self.error(err)
                    with lock:
                        projects = load_projects()
                        for x in projects:
                            if x["id"] == p["id"]:
                                x.update(extra)
                        save_projects(projects)
                    self.send_json({"ok": True})
            elif path == "/api/projects/add" and data.get("game"):
                # проєкт з гри: робоча тека + агент налаштування
                name = str(data.get("name") or "").strip()
                game = os.path.abspath(os.path.expanduser(str(data.get("game") or "").strip()))
                if not os.path.isdir(game):
                    return self.error("Такої теки гри немає: " + game)
                ws = str(data.get("workspace") or "").strip()
                ws = os.path.abspath(os.path.expanduser(ws)) if ws else \
                    os.path.join(os.path.expanduser("~/Holosii"), setup_agent.slug(name or os.path.basename(game)))
                if ws == game or ws.startswith(game + os.sep):
                    return self.error("Робоча тека не може бути всередині теки гри — туди нічого не пишемо")
                if game.startswith(ws + os.sep):
                    return self.error("Робоча тека не може містити теку гри")
                if os.path.isdir(ws) and os.listdir(ws) and not any(os.path.isdir(os.path.join(ws, x)) for x in (".holosii", ".byear")):
                    return self.error("Робоча тека вже існує і не порожня — вибери іншу: " + ws)
                listen = os.path.join(ws, "listen")
                with lock:
                    projects = load_projects()
                    if any(x["path"] == listen for x in projects):
                        return self.error("Цей проєкт уже є у списку")
                    setup_agent.create(ws, game, name or os.path.basename(game))
                    projects.append({"name": name or os.path.basename(game), "path": listen, "agent_cwd": ws,
                                     "workspace": ws, "game_dir": game})
                    save_projects(projects)
                self.send_json({"ok": True, "id": project_id(listen)})
            elif path == "/api/projects/add":
                name = str(data.get("name") or "").strip()
                folder = os.path.abspath(os.path.expanduser(str(data.get("path") or "").strip()))
                if not os.path.isdir(folder):
                    return self.error("Такої папки немає: " + folder)
                with lock:
                    projects = load_projects()
                    if any(p["path"] == folder for p in projects):
                        return self.error("Цей проєкт уже є у списку")
                    projects.append({"name": name or os.path.basename(folder), "path": folder})
                    save_projects(projects)
                self.send_json({"ok": True, "id": project_id(folder)})
            elif path == "/api/projects/remove":
                with lock:
                    projects = [p for p in load_projects() if p["id"] != data.get("id")]
                    save_projects(projects)
                self.send_json({"ok": True})
            elif path == "/api/projects/rename":
                with lock:
                    projects = load_projects()
                    for p in projects:
                        if p["id"] == data.get("id") and str(data.get("name") or "").strip():
                            p["name"] = str(data["name"]).strip()
                    save_projects(projects)
                self.send_json({"ok": True})
            elif path == "/api/pick-folder":
                folder = platform_util.pick_folder(str(data.get("prompt") or "Виберіть папку проєкту"))
                self.send_json({"path": folder})
            elif path == "/api/reveal":
                p = find_project(q.get("p", ""))
                full = safe_join(p["path"], str(data.get("f") or "")) if p else None
                if not full or not os.path.exists(full):
                    return self.error("Не знайдено", 404)
                if data.get("open") and os.path.isdir(full):
                    platform_util.open_folder(full)          # відкрити теку у Finder / Explorer
                else:
                    platform_util.reveal(full)               # показати у Finder / Explorer (виділити)
                self.send_json({"ok": True})
            else:
                self.error("Немає такої дії", 404)
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    platform_util.utf8_console()
    url = f"http://localhost:{PORT}"
    try:
        httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        print(f"Голосій уже запущений — відкриваю {url}")
        webbrowser.open(url)
        return
    if not os.path.exists(PROJECTS_FILE):
        save_projects([])
    agents.start_workers(find_project, TARGET_TAGS, SOURCE_TAGS)
    lim = agents.claude_limits()
    if not lim.get("available") or time.time() - (lim.get("seen") or 0) > 3600:
        agents.refresh_limits()                      # ліміти Claude застаріли — дізнатися у фоні
    print(f"Голосій працює: {url}")
    print("Щоб зупинити — закрийте це вікно або натисніть Ctrl+C.")
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    # Holosii.app зупиняє сервер через SIGTERM, Holosii.exe — закриваючи stdin (--stdin-stop)
    platform_util.on_terminate(lambda: threading.Thread(target=httpd.shutdown, daemon=True).start())
    try:
        httpd.serve_forever()
        print("\nЗупинено.")
    except KeyboardInterrupt:
        print("\nЗупинено.")
    finally:
        try:
            agents.AGENT.stop()                      # закрити агента Claude разом із сервером
        except Exception:                            # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
