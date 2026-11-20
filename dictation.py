"""Dictation: speech → text with a local Whisper (whisper.cpp `whisper-cli`), nothing leaves the machine.

ByEar records the reviewer's voice in the page, sends it here, and puts the text into the comment.
Available only when `whisper-cli` is installed and a multilingual ggml model is found (English-only
`*.en.bin` models cannot recognise Ukrainian). How to install: static/docs/whisper.html.
"""
import glob
import os
import re
import shutil
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CLI_DIRS = ["/opt/homebrew/bin", "/usr/local/bin"]
MODEL_DIRS = [os.path.expanduser("~/.cache/whisper"), os.path.join(HERE, "models"),
              "/opt/homebrew/share/whisper-cpp/models", "/usr/local/share/whisper-cpp/models"]
# best first; quantised variants (…-q5_0) are accepted too
PREFER = ["large-v3-turbo", "large-v3", "large-v2", "large", "medium", "small", "base", "tiny"]
MAX_SECONDS = 120


def find_cli():
    p = shutil.which("whisper-cli")
    if p:
        return p
    for d in CLI_DIRS:
        f = os.path.join(d, "whisper-cli")
        if os.access(f, os.X_OK):
            return f
    return None


def find_model(settings, lang="uk"):
    """(path, note). An explicit settings["whisper_model"] wins; otherwise the best model found."""
    want = (settings or {}).get("whisper_model") or ""
    if want:
        want = os.path.expanduser(want)
        return (want, "") if os.path.isfile(want) else (None, f"немає файлу моделі {want}")
    found = []
    for d in MODEL_DIRS:
        found += glob.glob(os.path.join(d, "ggml-*.bin"))
    usable = [f for f in found if lang == "en" or ".en." not in os.path.basename(f)]
    if not usable:
        if found:
            return None, "знайдено лише англійські моделі (*.en.bin) — вони не розпізнають українську"
        return None, "не знайдено жодної моделі Whisper"

    def rank(f):
        n = os.path.basename(f)
        for i, k in enumerate(PREFER):
            if f"ggml-{k}" in n:
                return i
        return len(PREFER)
    return sorted(usable, key=rank)[0], ""


def status(settings):
    lang = (settings or {}).get("dictation_lang") or "uk"
    cli = find_cli()
    if not cli:
        return {"available": False, "reason": "Whisper не встановлено (немає whisper-cli)", "lang": lang}
    model, note = find_model(settings, lang)
    if not model:
        return {"available": False, "reason": "Whisper встановлено, але " + note, "cli": cli, "lang": lang}
    return {"available": True, "cli": cli, "model": model, "model_name": os.path.basename(model), "lang": lang}


def transcribe(ffmpeg, data, ext, settings):
    """Audio bytes (any format ffmpeg reads) → text."""
    st = status(settings)
    if not st["available"]:
        raise RuntimeError(st["reason"])
    if not ffmpeg:
        raise RuntimeError("Не знайдено ffmpeg")
    tmp = tempfile.mkdtemp(prefix="byear_dict_")
    try:
        src = os.path.join(tmp, "in" + (ext if ext.startswith(".") else "." + ext))
        wav = os.path.join(tmp, "in.wav")
        with open(src, "wb") as f:
            f.write(data)
        r = subprocess.run([ffmpeg, "-v", "error", "-y", "-i", src, "-t", str(MAX_SECONDS), "-ac", "1", "-ar", "16000",
                            "-c:a", "pcm_s16le", wav], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.isfile(wav):
            raise RuntimeError("Не вдалося прочитати запис: " + r.stderr.strip()[-200:])
        cmd = [st["cli"], "-m", st["model"], "-l", st["lang"], "-f", wav, "-nt", "-np",
               "-t", str(max(2, min(8, (os.cpu_count() or 4) - 2)))]
        prompt = (settings or {}).get("dictation_prompt") or ""
        if prompt:
            cmd += ["--prompt", prompt]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            raise RuntimeError("Whisper: " + (r.stderr.strip()[-300:] or "помилка"))
        text = " ".join(line.strip() for line in r.stdout.splitlines() if line.strip())
        text = re.sub(r"\[[A-Z_ ]+\]|\((?:музика|music|тиша|silence)\)", "", text, flags=re.I)   # [BLANK_AUDIO] тощо
        return re.sub(r"\s+", " ", text).replace(" ,", ",").strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
