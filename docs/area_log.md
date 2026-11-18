# Area log (flat post-synthesis um2, yosys 0.9 + abc, sky130_fd_sc_hd tt_025C_1v80 without the flow's excluded cells)

Repeat with scripts/synth.sh; abc noise between equivalent netlists is about +-1.5%.
Real LibreLane results will differ (newer yosys, buffering, CTS): treat as an estimate.

## Per step (K=4 for comparability; last line is the shipped K=2)
| commit | step | area | flops |
| --- | --- | --- | --- |
| 391acaf | baseline core + wrapper | 10,872 | 133 |
| c7f4f2a | unified result pack + retry + (inert) injection taps | 11,083 | 136 |
| 9c31db7 | + ER / MA-MB checks, Q1 via multiplicand | 11,570 | 137 |
| 9c31db7 | same, shipped K=2 | 10,469 (10,314 after the ablation macros) | 137 |

Cycles: baseline 11 (K=4), unchanged by later steps.

## Multiplier digit width (final RTL)
K=2: 20 clk 10,314 | K=3: 15 clk 11,041 | K=4: 11 clk 11,445 | K=5: 11 clk 11,900 | K=6: 10 clk 12,466 | K=8: 7 clk 13,310 | K=12: 6 clk 15,312.
Plain yosys multipliers alone: 12x12 4,711; 13x12 5,091; 12x8 2,898; 12x6 2,090; 8x8 1,881.
Two parallel multipliers: not built; larger than the K=12 row.

## Rejected / neutral ideas (measured)
- Signed top digit as an extra full adder row: MAC 2,083 -> 1,940 with a conditional ones-complement row (kept).
- Remainder compare as two subtractors instead of compares: +208 (rejected).
- Serial (A then B) subnormal normalisation: +300 (rejected).
- First version of ER parity + Q1 parity + source compare: +800 over retry-only; replaced by the compare/scan versions (+370 together).
- Seed ROM cheaper table: each entry has at most 2 legal values for error in {0,1} (model/explore/rom_slack.py): no slack, no saving.
- 32-entry ROM, sign-magnitude correction, truncated Q0 operand: error spread 3-4 ulp, needs a second correction compare (rejected numerically, model/explore).
- abc script variants on the same RTL: 10.9k - 12.2k (script and -D matter more than most RTL tweaks).
- Ablation (K=4 baseline): subnormal normalisation 390, subnormal result path ~180-600, remainder check 270, ROM 560, whole exponent path ~1,400.
- Not tried: latch-based operand registers, clock gating, in-place operand normalisation (risk / complexity), diverse restoring-division fallback (no area left).
