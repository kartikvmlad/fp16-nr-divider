#!/usr/bin/env python3
"""Write a copy of the sky130_fd_sc_hd liberty file without the cells the Tiny Tapeout /
LibreLane flow never uses (DONT_USE: lpflow_*, probe_*, plus this project's
EXTRA_EXCLUDED_CELLS from src/config.json), so that yosys + abc maps the way the real flow would.

    python3 scripts/mklib.py <in.lib> <out.lib>
"""
import json
import os
import re
import sys

src, dst = sys.argv[1], sys.argv[2]
cfg = os.path.join(os.path.dirname(__file__), "..", "src", "config.json")
extra = json.load(open(cfg)).get("EXTRA_EXCLUDED_CELLS", [])
drop = [re.compile(r"sky130_fd_sc_hd__lpflow_"), re.compile(r"sky130_fd_sc_hd__probe")] + \
       [re.compile("^" + re.escape(c) + "$") for c in extra]

text = open(src).read()
out, i, n_drop = [], 0, 0
pat = re.compile(r'^\s*cell\s*\(\s*"?([^")]+)"?\s*\)\s*\{', re.M)
while True:
    m = pat.search(text, i)
    if not m:
        out.append(text[i:])
        break
    out.append(text[i:m.start()])
    depth, j = 1, m.end()
    while depth:
        c = text[j]
        depth += (c == "{") - (c == "}")
        j += 1
    if any(p.search(m.group(1)) for p in drop):
        n_drop += 1
    else:
        out.append(text[m.start():j])
    i = j
open(dst, "w").write("".join(out))
print(f"{dst}: dropped {n_drop} cells")
