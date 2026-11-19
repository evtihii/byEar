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
for line in sys.stdin:
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
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
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "Готово (тест).",
                      "session_id": "s1", "total_cost_usd": 0.01}), flush=True)
