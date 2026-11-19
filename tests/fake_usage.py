#!/usr/bin/env python3
"""Stand-in for a project's usage_cmd: prints the credit counter kept in FAKE_USAGE_FILE."""
import json
import os

p = os.environ["FAKE_USAGE_FILE"]
used = int(open(p).read()) if os.path.exists(p) else 1000
print(json.dumps({"used": used, "limit": 100000, "reset": 1800000000}))
