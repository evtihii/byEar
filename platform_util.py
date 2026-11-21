"""Everything that differs between macOS and Windows, in one place.

- trash_dir(name)      — folder for old versions and rotated logs (nothing is deleted for good):
                         macOS ~/.Trash/<name>; Windows %LOCALAPPDATA%\\Holosii\\Trash\\<name>,
                         which sweep_trash() empties into the Recycle Bin after a few days.
- reveal(path) / open_folder(path) — Finder / Explorer.
- pick_folder(prompt)  — native folder dialog (osascript / PowerShell FolderBrowserDialog).
- which(name, extra)   — tool lookup on PATH plus the usual install folders (Homebrew, winget, scoop…).
- new_group_kwargs() / kill_tree(proc) — run a tool in its own process group and stop it with its children.
- on_terminate(fn)     — how a shell asks the server to stop (SIGTERM on macOS, stdin EOF on Windows).

Linux is not a target, but the POSIX branches work there too (xdg-open, zenity if installed).
"""
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
ENC = {"encoding": "utf-8", "errors": "replace"}   # text pipes: Windows defaults to the ANSI code page

REVEAL_LABEL = "Показати у Провіднику" if IS_WIN else "Показати у Finder"   # menu item / button title
SWEEP_DAYS = 7          # Windows: Holosii trash entries older than this go to the Recycle Bin


def _env_dir(var, *rest):
    base = os.environ.get(var)
    return os.path.join(base, *rest) if base else None


# ---------- per-user folder and access key ----------

def user_dir():
    """Per-user folder other accounts on this computer cannot read (the access key lives here)."""
    if IS_WIN:
        return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Holosii")
    if IS_MAC:
        return os.path.expanduser("~/Library/Application Support/Holosii")
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "holosii")


def load_token(path):
    """The server's access key: created once (random, 256 bit), readable by this user only.

    The app shells read the same file and open the page with ?t=<key>; the server then keeps it in a cookie.
    On Windows %LOCALAPPDATA% is already private to the user; on POSIX the file is 0600 in a 0700 folder.
    """
    d = os.path.dirname(path)
    os.makedirs(d, mode=0o700, exist_ok=True)
    try:
        with open(path, encoding="utf-8") as f:
            tok = f.read().strip()
        if len(tok) >= 32:
            if not IS_WIN and os.stat(path).st_mode & 0o077:
                os.chmod(path, 0o600)
            return tok
    except OSError:
        pass
    tok = secrets.token_urlsafe(32)
    tmp = f"{path}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(tok)
    os.replace(tmp, path)
    return tok


# ---------- trash ----------

def trash_root():
    if IS_WIN:
        return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Holosii", "Trash")
    if IS_MAC:
        return os.path.expanduser("~/.Trash")
    return os.path.expanduser("~/.local/share/Trash/files")


def trash_dir(name):
    """Folder (not created) where Holosii keeps things it would otherwise delete."""
    return os.path.join(trash_root(), name)


def agent_trash_hint():
    """Extra words for the fix agent's prompt: where to put the old version on Windows ('' on macOS)."""
    return "" if not IS_WIN else f" — тека {trash_dir('Holosii_agent')}"


_PS_RECYCLE = r"""
Add-Type -AssemblyName Microsoft.VisualBasic
$paths = [Console]::In.ReadToEnd() | ConvertFrom-Json
foreach ($p in $paths) {
  try {
    if (Test-Path -LiteralPath $p -PathType Container) {
      [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($p, 'OnlyErrorDialogs', 'SendToRecycleBin')
    } elseif (Test-Path -LiteralPath $p) {
      [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p, 'OnlyErrorDialogs', 'SendToRecycleBin')
    }
  } catch { Write-Output ("fail: " + $p) }
}
"""


def recycle(paths):
    """Windows: move files/folders to the Recycle Bin in one PowerShell call. Returns True on success."""
    paths = [os.path.abspath(p) for p in paths if os.path.exists(p)]
    if not paths or not IS_WIN:
        return not paths
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_RECYCLE],
                           input=json.dumps(paths), capture_output=True, text=True, timeout=120,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), **ENC)
        return r.returncode == 0 and "fail:" not in r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def sweep_trash(days=SWEEP_DAYS):
    """Windows only: entries of the Holosii trash older than `days` go to the Recycle Bin."""
    if not IS_WIN:
        return
    root = trash_root()
    old = []
    cutoff = time.time() - days * 86400
    try:
        for name in os.listdir(root):
            sub = os.path.join(root, name)
            for e in (os.listdir(sub) if os.path.isdir(sub) else []):
                f = os.path.join(sub, e)
                if os.path.getmtime(f) < cutoff:
                    old.append(f)
    except OSError:
        return
    if old:
        recycle(old)


# ---------- Finder / Explorer ----------

def _bg(cmd, **kw):
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
    except OSError:
        pass


def reveal(path):
    """Show the file or folder selected in Finder / Explorer."""
    path = os.path.abspath(path)
    if IS_WIN:
        _bg(f'explorer /select,"{path}"')            # explorer wants exactly this quoting; paths cannot hold "
    elif IS_MAC:
        subprocess.run(["open", "-R", path])
    else:
        _bg(["xdg-open", os.path.dirname(path) or path])


def open_folder(path):
    """Open a folder in Finder / Explorer. Only folders: on Windows os.startfile would *run* a file."""
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return reveal(path)
    if IS_WIN:
        try:
            os.startfile(path)                       # noqa: S606 — a folder, opens in Explorer
        except OSError:
            _bg(["explorer", path])
    elif IS_MAC:
        subprocess.run(["open", path])
    else:
        _bg(["xdg-open", path])


# ---------- folder picker ----------

_PS_PICK = r"""
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = $env:HOLOSII_PROMPT
$d.ShowNewFolderButton = $true
$owner = New-Object System.Windows.Forms.Form -Property @{TopMost = $true; ShowInTaskbar = $false}
if ($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $d.SelectedPath }
"""


def pick_folder(prompt):
    """Native 'choose folder' dialog. Returns the path or None (cancelled / no dialog available)."""
    prompt = str(prompt or "")[:80]
    try:
        if IS_WIN:
            r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", _PS_PICK],
                               capture_output=True, text=True, env={**os.environ, "HOLOSII_PROMPT": prompt},
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), **ENC)
            folder = r.stdout.strip().rstrip("\\") if r.returncode == 0 else ""
            if len(folder) == 2 and folder[1] == ":":
                folder += "\\"                       # a drive root: keep C:\
        elif IS_MAC:
            script = ('tell application "System Events" to activate\n'
                      'tell application "System Events" to return POSIX path of '
                      '(choose folder with prompt "' + prompt.replace('"', "'").replace("\\", "/") + '")')
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, **ENC)
            folder = r.stdout.strip().rstrip("/") if r.returncode == 0 else ""
        else:
            r = subprocess.run(["zenity", "--file-selection", "--directory", "--title", prompt],
                               capture_output=True, text=True, **ENC)
            folder = r.stdout.strip() if r.returncode == 0 else ""
    except OSError:
        return None
    return folder or None


# ---------- tools ----------

def tool_dirs():
    """Folders to search after PATH (an app started from the Dock/Start menu may get a short PATH)."""
    if IS_WIN:
        dirs = [os.path.expanduser("~/.local/bin"),                         # claude native installer
                _env_dir("APPDATA", "npm"),                                 # npm i -g @anthropic-ai/claude-code
                _env_dir("LOCALAPPDATA", "Microsoft", "WinGet", "Links"),   # winget install ffmpeg / whisper
                os.path.expanduser("~/scoop/shims"),
                _env_dir("ChocolateyInstall", "bin") or r"C:\ProgramData\chocolatey\bin",
                _env_dir("ProgramFiles", "ffmpeg", "bin"),
                r"C:\ffmpeg\bin",
                _env_dir("LOCALAPPDATA", "Programs", "whisper-cpp")]
        return [d for d in dirs if d]
    return [os.path.expanduser("~/.local/bin"), "/opt/homebrew/bin", "/usr/local/bin"]


def whisper_model_dirs():
    if IS_WIN:
        return [d for d in (_env_dir("LOCALAPPDATA", "Programs", "whisper-cpp", "models"),
                            _env_dir("LOCALAPPDATA", "whisper-cpp", "models")) if d]
    return ["/opt/homebrew/share/whisper-cpp/models", "/usr/local/share/whisper-cpp/models"]


def which(name, extra=None):
    """PATH first, then `extra` (default: tool_dirs()). On Windows .exe/.cmd/.bat are found as well."""
    p = shutil.which(name)
    if p:
        return p
    dirs = [os.path.expanduser(d) for d in (tool_dirs() if extra is None else extra)]
    return shutil.which(name, path=os.pathsep.join(dirs)) if dirs else None


# ---------- processes ----------

def new_group_kwargs():
    """Popen kwargs: own process group, so kill_tree() also stops what the tool started."""
    if IS_WIN:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {"start_new_session": True}


def no_window_kwargs():
    """Popen kwargs: no console window flashing on Windows (nothing on macOS)."""
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WIN else {}


def kill_tree(proc):
    """Stop a process started with new_group_kwargs() together with its children."""
    if proc.poll() is not None:
        return
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            os.killpg(proc.pid, signal.SIGTERM)
    except OSError:
        pass
    if proc.poll() is None:
        try:
            proc.terminate()
        except OSError:
            pass


def on_terminate(stop):
    """Call stop() when the app shell asks the server to quit.

    macOS (Holosii.app): SIGTERM. Windows (Holosii.exe): the shell keeps our stdin open and closes it on
    exit (also if it crashes), so stdin EOF means 'quit'. Only with --stdin-stop, so a console run is
    not stopped by an empty stdin. Ctrl+C / Ctrl+Break work in a console in both cases.
    """
    def _sig(*_):
        stop()
    if hasattr(signal, "SIGTERM"):
        try:
            signal.signal(signal.SIGTERM, _sig)
        except (ValueError, OSError):
            pass
    if hasattr(signal, "SIGBREAK"):                  # Windows console: Ctrl+Break
        signal.signal(signal.SIGBREAK, _sig)
    if "--stdin-stop" in sys.argv:
        def _watch():
            try:                                     # raw fd: a buffered read would hold a lock at exit
                fd = sys.stdin.fileno()
                while os.read(fd, 1024):
                    pass
            except (OSError, ValueError, AttributeError):
                pass
            stop()
        threading.Thread(target=_watch, daemon=True).start()


def utf8_console():
    """Windows: print Ukrainian to a console or a log file without UnicodeEncodeError."""
    if not IS_WIN:
        return
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
