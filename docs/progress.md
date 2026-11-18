# Progress log (one line per kept step; a new session continues from the last line)

Task B: K=8 (7 clocks) under a 13,000 um2 flat cap (also report < 12,500), all fault features and exact IEEE kept.
Area = scripts/synth.sh (flat, yosys 0.9 + abc, tt_025C_1v80 without the flow's excluded cells); abc noise about +-1.5%.
Cheap check per step: `cd test && COMPILE_ARGS=-DFP16_K=8 FP16_K=8 make -B` (10 cocotb tests) and the 20k mantissa vector run
(`python3 ../model/gen_vectors.py mant m.hex 1 20; head -20000 m.hex > ms.hex; iverilog -g2005 -DFP16_K=8 -o tb_vectors tb_vectors.v ../src/fp16_div_core.v; vvp tb_vectors +VEC=ms.hex`).
Long verification only once at the end (exhaustive RTL, 600k wide/directed, gate-level cocotb, 200k fault campaign).

| step | commit | K=8 area | clocks (K=8) | next |
| --- | --- | --- | --- | --- |
| start (previous task end) | 6f7cb83 | 13,359 (K=7 12,867, K=6 12,437, K=2 10,484 default) | 7 | Booth radix-4 MAC (standalone: 3,837 -> 3,316 um2, equivalent on 400k random stimuli) |
| 1. Booth radix-4 MAC (K>=6) | (this commit) | 12,817 (K=7 12,279, K=6 11,988) | 7 | carry-save / residue-3 / flop sharing; target < 12,500 |
| 2. abc-script survey, mod-3 reducer measurement, sharing tries (all rejected, see area_log) ; default K=8 | (this commit) | 12,817 | 7 | final long verification, docs |
| 3. final long verification on K=8: exhaustive 16.8M divides 0 mismatches, 600k+484 vectors 0 errors, cocotb 10/10 RTL and gate level, 200k campaign silent 5,149 hang 0 | (docs commit) | 12,817 | 7 | done; optional: squeeze K=8 below 12,500 (needs about -320 um2) |
