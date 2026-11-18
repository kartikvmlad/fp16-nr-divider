# FP16 Newton-Raphson divider with fault detection and correction (Tiny Tapeout, 1x1)

IEEE 754 binary16 divider: seed ROM + one Goldschmidt/NR step + exact remainder, correctly rounded
(nearest-even, subnormals, all flags), remainder check and automatic retry. Same byte protocol as the FP32 divider.
Default build K=8: 7 clocks per divide, 12,817 um2 post-synthesis estimate (K=7: 8 clocks 12,279; K=6: 10 clocks 11,988; K=2: 20 clocks 10,484).
See docs/info.md, docs/area_log.md, docs/progress.md.
Top module tt_um_vikaskumart176_fp16_nr_div. Not yet through the Tiny Tapeout GDS flow.
