#!/usr/bin/env python3
"""Stand-in for `claude -p --input-format stream-json` used by the tests.

For each user message it finds the file marked «← це треба виправити» and, depending on FAKE_MODE:
  edit   — rewrites it (pitch-shifted copy of the reference via ffmpeg) and reports success;
  noop   — leaves the file alone;
  burn   — reports a huge token usage and waits for the interrupt (token limit test).
"""
import json
import os
import re
import subprocess
import sys

mode = os.environ.get("FAKE_MODE", "edit")
for _s in (sys.stdin, sys.stdout):                   # like Claude Code: UTF-8 pipes (Windows defaults to cp1252)
    _s.reconfigure(encoding="utf-8")


def say(text):
    print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}],
                                                       "usage": {"input_tokens": 100, "output_tokens": 20}}}), flush=True)


def setup_step(prompt):
    """Setup agent stand-in: a survey writes plan.json + a sample, an extraction fills listen/ + result.json."""
    print(json.dumps({"type": "system", "subtype": "init", "session_id": "setup-s1"}), flush=True)
    ws = re.search(r"Workspace \(everything you make goes here\): (.+)", prompt).group(1).strip()
    game = re.search(r"Game folder \(READ ONLY[^)]*\): (.+)", prompt).group(1).strip()
    by = os.path.join(ws, ".holosii")
    src = os.path.join(game, "voice_en.wav")
    print(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash",
          "input": {"command": "ls " + game}}], "usage": {"input_tokens": 100}}}), flush=True)
    if "THIS STEP: SURVEY" in prompt:
        os.makedirs(os.path.join(by, "samples"), exist_ok=True)
        subprocess.run(["cp", src, os.path.join(by, "samples", "01_en.wav")], check=True)
        json.dump({"engine": "Test", "audio": "wav", "recipe": None, "blocked": "encrypted" if "LOCKED" in game else None,
                   "languages": [{"code": "en", "name": "англійська", "lines": 2}],
                   "samples": [{"file": "samples/01_en.wav", "lang": "en", "text": "hello"}],
                   "steps": ["видобути 2 фрази"], "questions": []}, open(os.path.join(by, "plan.json"), "w"))
        say("Знайшла 2 фрази англійською.")
    elif "THIS STEP: EXTRACTION" in prompt:
        for i in (1, 2):
            d = os.path.join(ws, "listen", "ch01", f"{i:03d}_Line{i}")
            os.makedirs(d, exist_ok=True)
            subprocess.run(["cp", src, os.path.join(d, "en.wav")], check=True)
            open(os.path.join(d, "текст.txt"), "w").write(f"EN: line {i}")
        open(os.path.join(ws, "BRIEF.md"), "w").write("brief")
        json.dump({"lines": 2, "languages": ["en"], "default_ref": "en",
                   "extract_cmd": ["python3", ws + "/tools/extract.py"], "pack_cmd": ["python3", ws + "/tools/pack.py"],
                   "notes": "усе"}, open(os.path.join(by, "result.json"), "w"))
        say("Видобуто 2 фрази.")
    else:
        say("Відповідь: " + prompt.rsplit("User:", 1)[-1].strip()[:80])
FIVE = float(os.environ.get("FAKE_FIVE_HOUR", "0.42"))


def rate_limits():
    """What Claude Code reports about the plan limits after each reply."""
    w = {"five_hour": {"utilization": FIVE, "resetsAt": 4102444800, "status": "allowed"},
         "seven_day": {"utilization": 0.3, "resetsAt": 4102444800, "status": "allowed"}}
    print(json.dumps({"type": "rate_limit_event", "rate_limit_info": {
        "status": "allowed", "rateLimitType": "five_hour", "unifiedWindows": w}}), flush=True)


for line in sys.stdin:
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:                     # plain prompt: the limits probe or a setup step
        prompt = line + sys.stdin.read()
        if "project setup agent" in prompt:
            setup_step(prompt)
        rate_limits()
        print(json.dumps({"type": "result", "subtype": "success", "result": "ok", "total_cost_usd": 0.02}), flush=True)
        break
    if msg.get("type") == "control_request":
        print(json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True,
                          "result": "", "session_id": "s1"}), flush=True)
        continue
    text = (msg.get("message") or {}).get("content") or ""
    if text.startswith("/compact"):
        print(json.dumps({"type": "result", "subtype": "success", "result": "", "session_id": "s1"}), flush=True)
        continue
    target = re.search(r"- (.+?)   ← це треба виправити", text)
    ref = re.search(r"Еталон: (.+?) \(мова", text)
    if mode == "burn":
        print(json.dumps({"type": "assistant", "message": {"content": [], "usage": {"input_tokens": 5000000}}}),
              flush=True)
        continue                                     # the result comes after the interrupt
    if mode == "edit" and target:
        src = ref.group(1) if ref else target.group(1)
        out = target.group(1)
        tmp = out + ".tmp.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", "asetrate=48000*1.5,aresample=48000",
                        "-ac", "1", "-c:a", "pcm_s16le", tmp], check=True)
        os.replace(tmp, out)
        uf = os.environ.get("FAKE_USAGE_FILE")       # "spend" 340 generation credits
        if uf:
            used = int(open(uf).read()) if os.path.exists(uf) else 1000
            open(uf, "w").write(str(used + 340))
    print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "ok"}],
                                                       "usage": {"input_tokens": 1000, "output_tokens": 50}}}),
          flush=True)
    rate_limits()
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "Готово (тест).",
                      "session_id": "s1", "total_cost_usd": 0.01}), flush=True)
