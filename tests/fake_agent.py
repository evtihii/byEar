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
    except json.JSONDecodeError:                     # plain prompt (the limits probe)
        rate_limits()
        print(json.dumps({"type": "result", "subtype": "success", "result": "ok"}), flush=True)
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
    rate_limits()
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "Готово (тест).",
                      "session_id": "s1", "total_cost_usd": 0.01}), flush=True)
