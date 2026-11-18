#!/usr/bin/env python3
"""Cell-type area breakdown of a yosys `stat -liberty` report.
    python3 scripts/cellbreak.py synth_out/flat.txt synth_out/lib_dontuse.lib [n]"""
import re
import sys

stat, lib = sys.argv[1], sys.argv[2]
top = int(sys.argv[3]) if len(sys.argv) > 3 else 25
area, cur = {}, None
for line in open(lib):
    m = re.match(r'\s*cell\s*\(\s*"?(sky130_fd_sc_hd__\w+)"?\s*\)', line)
    if m:
        cur = m.group(1)
        continue
    m = re.match(r"\s*area\s*:\s*([0-9.]+)", line)
    if m and cur and cur not in area:
        area[cur] = float(m.group(1))
rows = []
for line in open(stat):
    m = re.match(r"\s+(sky130_fd_sc_hd__\w+)\s+(\d+)", line)
    if m:
        rows.append((int(m.group(2)) * area.get(m.group(1), 0.0), m.group(1), int(m.group(2))))
rows.sort(reverse=True)
tot = sum(r[0] for r in rows)
print(f"total {tot:.1f} um2 in {sum(r[2] for r in rows)} cells")
for a, n, c in rows[:top]:
    print(f"{n.replace('sky130_fd_sc_hd__', ''):16s} {c:5d} {a:9.1f}  {100 * a / tot:5.1f}%")
