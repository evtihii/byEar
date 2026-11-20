#!/usr/bin/env python3
"""Add an orchestrator comment to a line (shown read-only in Holosii, in «Коментарі» next to the agent's reply).

    python3 review.py <project listen folder> <item id> "comment" [--by "Opus"]
Comments live in <project>/reviews.json: {item_id: [{"text", "by", "time"}]}.
"""
import argparse, json, os, time

ap = argparse.ArgumentParser()
ap.add_argument("project"); ap.add_argument("item"); ap.add_argument("text"); ap.add_argument("--by", default="оркестратор")
a = ap.parse_args()
p = os.path.join(a.project, "reviews.json")
d = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
d.setdefault(a.item, []).append({"text": a.text, "by": a.by, "time": time.strftime("%Y-%m-%dT%H:%M:%S")})
tmp = p + ".tmp"
json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
os.replace(tmp, p)
print(f"{a.item}: {len(d[a.item])} коментар(і)")
