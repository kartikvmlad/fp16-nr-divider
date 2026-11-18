# FP16 Newton-Raphson divider with fault detection and correction (Tiny Tapeout, 1x1)

IEEE 754 binary16 divider: seed ROM + one Goldschmidt/NR step + exact remainder, correctly rounded
(nearest-even, subnormals, all flags), remainder check and automatic retry. Same byte protocol as the FP32 divider.
Default build: 20 clocks per divide, ~10.3k um2 post-synthesis estimate (see docs/info.md, docs/area_log.md).
Top module tt_um_vikaskumart176_fp16_nr_div. Not yet through the Tiny Tapeout GDS flow.
