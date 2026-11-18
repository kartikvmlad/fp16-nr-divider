<!---
Documentation of the FP16 Newton-Raphson divider. Every number below was measured in this repo
(see scripts/ and test/); nothing is an estimate unless it says so.
--->

## How it works

An IEEE 754 binary16 divider: round-to-nearest-even, full subnormal support, flags
`invalid / divzero / overflow / underflow / inexact` exactly as in the FP32 core (canonical quiet NaN
`0x7E00`, overflow also sets inexact, tininess detected after rounding).

### Quotient datapath (all mantissas are 11-bit normalised integers in [1024, 2047])

```
N   = ma >= mb ? ma : 2*ma                  dividend scaled into [mb, 2*mb)
Y0  = ROM[mb[9:4]]                          64 entries x 7 bits, ~2^17 / mb
P2  Q0 = (N * Y0) >> 4                      first quotient estimate (2 extra fraction bits)
P1  e  = (2^17 - mb*Y0) >> 4                signed 8-bit residual of the seed
P3  dQ = ((Q0 >> 4) * e) >> 9               the one Newton-Raphson (Goldschmidt) step
    Q1 = (Q0 + dQ) >> 2                     always Q or Q-1                      (proved, 2^20 pairs)
P4  R  = N*2^11 - Q1*mb                     exact remainder, 0 <= R < 2*mb
    Q  = Q1 + (R >= mb)                     exactly floor(N*2^11/mb), 12 bits: 11 kept + round bit
    sticky = (R mod mb) != 0
```

The rounding decision needs only the round bit `Q[0]` and the sticky bit, so the result is the correctly
rounded IEEE quotient. `model/verify_mantissa.py` proves the `Q1 in {Q-1, Q}` claim for all 2^20 mantissa pairs.

### Hardware

One multiply-accumulate engine, K bits of the scanned operand per clock (`FP16_K`, default **2**).
Registers: `MA/MB` (normalised mantissas), `ER` (exponent), `QR` (Q0, then Q1), `H` accumulator,
`L` (scanned operand / low product bits / finally the packed result - there is no result register).
Subnormal inputs are normalised one bit per clock; subnormal results are shifted one bit per clock
(extra clocks only for those operands). Specials take 2 clocks.

The accumulator is pre-loaded with constants that make the arithmetic free: `4095` turns the one's
complement of the product bits into `2^17 - T` exactly; `{~N0, 11'h7FF}` makes the upper bits of the P4
product equal `N >> 1` iff `Q1` was a legal estimate - that comparison is the built-in remainder check.

### Cycles per divide (start edge to done, normal operands) and area

| K | clocks | flat area um2 (yosys 0.9 + abc) |
| --- | --- | --- |
| **2 (default)** | **20** | **10,314** |
| 3 | 15 | 11,041 |
| 4 | 11 | 11,445 |
| 6 | 10 | 12,466 |
| 8 | 7 | 13,310 |
| 12 (one parallel 12x12 multiplier, time-shared) | 6 | 15,312 |

Worst case (subnormal operands and subnormal result) K=2: 42 clocks, plus about 20 if a retry happens.
Only K=2 is under the 10,500 um2 target; K=4 gives the 8-12 clock figure but is about 9% over.
Two parallel multipliers (not built) would be larger than the K=12 line (one 12x12 multiplier alone is 5.8k um2 hierarchical).
Critical path (abc `stime`, flop to flop, K=2): about 8.2 ns of a 30 ns clock.

Change the build with `-DFP16_K=n` (the default is the macro at the top of `src/fp16_div_core.v`).

## Register map (same byte protocol as the FP32 divider)

Address `{uio_in[4], uio_in[1:0]}`, write strobe `uio_in[2]` (must be seen high on 2 consecutive clocks),
start `uio_in[3]` (rising edge), `uio_out[7]` DONE (sticky), `uio_out[6]` BUSY, `uio_oe = 8'b1100_0000`.

| address | write | read |
| --- | --- | --- |
| 0 | A[7:0] | Q[7:0] |
| 1 | A[15:8] | Q[15:8] |
| 2 | B[7:0] | 0x00 |
| 3 | B[15:8] | 0x00 |
| 4 | ignored | flags `{fault, corrected, 0, invalid, divzero, overflow, underflow, inexact}` |
| 5-7 | ignored | status `{6'b0, busy, done}` |

Writes during BUSY are held off until the divide ends (the strobe must still be high). BUSY stays high across a retry.

## Fault detection and correction

Checks (all compare against information that is independent of the fault being looked for):

| check | catches | flat area when it is the only one removed (K=2) |
| --- | --- | --- |
| remainder check: upper bits of the P4 product == `N >> 1` | wrong Q1 / Q0 / seed, any flip or stuck bit in the multiplier, adder, accumulator and shift path of P2-P4 | 145 |
| ER == its start value (normal operands) | flips / stuck bits of the exponent register | -9 (noise) |
| MA, MB == operand registers (normal operands) | flips / stuck bits of the mantissa registers | 205 |
| **pack check** (`fp16_incchk`): Qf vs Q1, result fraction vs kept bits, exponent vs E, sign, subnormal pack | the quotient incrementer, the rounding incrementer, the exponent increment, sign and subnormal packing - everything after the remainder check | 105 |
| **watchdog**: 6-bit LFSR, restarted at every start / retry, 56 clocks | any divide that does not finish (FSM, `run`, `ph`, `cnt`, shift loops): ends with `done = 1`, `fault = 1` | 205 (7 flops) |
| retry once (time redundancy) | transient faults: result is delivered with `corrected` set | 74 |

The pack check needs no spare copy of the result: an increment by 0 or 1 flips a run of trailing ones, so `out ^ in`
must be `0..01..1` and its bit 0 must equal the increment. It does not check the forced results (specials,
overflow to infinity, flush to zero) or the flags.
The extra range compare `R < 2*mb` is available as `-DFP16_CHK_RANGE` (+92 um2, silent 483 -> 408 per 20,000 faults)
but is off in the default build because it does not fit under 10,500 um2.

**Behaviour.** A failed check repeats the whole divide once (operands, `MA/MB/ER` are reloaded from the operand registers).
Repeat passes: result delivered, `corrected = 1`. Repeat fails: result delivered, `fault = 1` (do not trust it).
A subnormal-pack mismatch in the last clock cannot be repeated and sets `fault`. Watchdog timeout sets `fault`, `done`; BUSY drops.
Specials never raise `fault`.

### Area and silent/hang counts after each step (K=2)

Flat post-synthesis area; counts per 50,000 injections (same vectors and seed; the first four rows), last row 20,000.

| step | flat area um2 | silent | hang | corrected | detected |
| --- | --- | --- | --- | --- | --- |
| before (previous commit) | 10,314 | 3,919 | 926 | 7,864 | 16,897 |
| + watchdog | 10,694 (+380) | 3,779 | 0 | 7,864 | 17,963 |
| + pack check | 10,818 (+124) | 1,299 | 0 | 7,989 | 20,645 |
| + area recovery (`spec_r` is a wire, ROM re-encoded, range compare off) | **10,484** | see below | 0 | | |
| final, 20,000 faults | 10,484 | 483 | 0 | 3,097 | 8,308 |

Area recovery, each measured: `spec_r` flop removed 10,818 -> 10,810; seed ROM stored as `63 - seed - i` plus a 6-bit adder
(the table column is smoother: ROM 636 -> 260 um2 alone) 10,810 -> 10,576; range compare off 10,576 -> 10,484.
Tried and dropped: folding the subnormal sticky bit into `L[12]` (+44), 11-bit form of the range compare (+25).
Margin to the 10,500 target is 16 um2, below the +-1.5% abc noise: the number must be re-checked in the real flow.

### Campaign: 200,000 single-bit faults (test/tb_fault.v, seed 12345)

Uniform over 146 modelled bits (registers `MA MB ER QR H L ph cnt run rem_r tiny_r rty` and buses `y0 Msel nxtH sum_lo Qf res`),
one third each of: one-clock flip at a random clock, stuck-at-0, stuck-at-1 from the first clock (permanent defect, the retry sees it too).
`spec_r` is no longer a flop, so the modelled bit count is one lower than in the previous campaign.

| | flip | stuck-at-0 | stuck-at-1 | all | previous commit (all) |
| --- | --- | --- | --- | --- | --- |
| injected | 66,897 | 66,601 | 66,502 | 200,000 | 200,000 |
| masked (right answer, nothing flagged) | 34,626 | 24,144 | 22,394 | 81,164 | 81,252 |
| corrected (retry gave the right answer) | 30,530 | 220 | 650 | 31,400 | 31,397 |
| detected (`fault` flag set) | 674 | 40,388 | 41,302 | 82,364 | 67,476 |
| **silent wrong** | 1,067 | 1,849 | 2,156 | **5,072** | 16,134 |
| **hang** | 0 | 0 | 0 | **0** | 3,741 |

Silent plus hang: 19,875 (9.9%) -> 5,072 (2.5%).
Where the remaining silent cases are (counts of 200,000): `res` 1,361 (forced results and flag-affecting bits are not checked),
`L` 918, `H` 368, `QR` 338, `ER` 325 (subnormal operands are exempt from the ER check), `Qf` 190, `ph` 195, `MA` 199, `MB` 114.

Leave-one-out on 20,000 faults (area, silent, hang): full 10,484 / 483 / 0; no watchdog 10,279 / 544 / 404; no pack check 10,379 / 1,540 / 0;
no MA/MB check 10,279 / 1,158 / 0; no ER check 10,493 / 996 / 0; no remainder check 10,339 / 5,543 / 0; no retry 10,410 / 483 / 0 (corrected 3,097 become detected);
with the range compare 10,576 / 408 / 0; no checks at all 9,482 / 8,309 / 404. (`corrected = 76` in the no-retry row comes from the `rty` bit itself being injected.)

**What is still not covered.**
- The forced results (specials, overflow, flush) and the flags after the remainder check; subnormal-operand ER/MA/MB corruption.
- Faults in the operand registers and the wrapper.
- A watchdog fault itself (a stuck `wd_act` / LFSR gives a spurious timeout or none).
- Retry fixes transient faults, not permanent stuck-at defects: stuck-at faults end with `fault = 1` (detected, not corrected); `corrected` after a stuck-at is 0.65% and only when the defect is masked on the second pass.
- The diverse fallback (slow restoring division) was NOT built: no area left.

## How to test

```sh
cd test && make -B                                   # cocotb, RTL (9 tests)
make -f Makefile.gl_local -B                         # same tests on the yosys gate netlist (scripts/synth.sh first)
./run_vectors.sh ; ./run_exhaustive.sh               # core-level regressions
cd ../model && python3 verify_mantissa.py && python3 verify_reference.py && python3 verify_exhaustive.py <checksum>
cd c && gcc -O2 -fopenmp -o exhaustive model16.c && ./exhaustive
```

Measured results (K=2, final RTL of the fault-coverage step): 16 exponent/sign combinations x all 2^20 fraction pairs = 16,777,216 divides, 0 mismatches, 0 spurious fault flags; 600,000 wide and 484 directed vectors, 0 errors; 10/10 cocotb tests on RTL and 9/9 on the synthesized gate netlist (the watchdog test needs an RTL signal); model vs exact reference on all 2^32 pairs (see model/); 1.2 M operands cross-checked against the Fraction reference.
0 spurious fault flags; 600,000 wide vectors and 484 directed pairs, 0 errors; 9/9 cocotb tests on RTL and on the synthesized
gate netlist; model vs exact reference on all 2^32 pairs, flags included (C: 0 mismatches; numpy: same checksum and 0 value
mismatches vs numpy float16); 1.2 M operands cross-checked against the Fraction reference.
Not run: the Tiny Tapeout GDS flow (no LibreLane here), so area/placement is unconfirmed.

## Worked examples (model/examples.py)

| case | a | b | ma | mb | N | Y0 | e | Q1 | R | Q | result | flags |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.0 / 3.0 | 3C00 | 4200 | 1024 | 1536 | 2048 | 85 | 32 | 2730 | 1024 | 2730 | 0x3555 | inexact |
| 10.0 / 1.5 | 4900 | 3E00 | 1280 | 1536 | 2560 | 85 | 32 | 3413 | 512 | 3413 | 0x46AB | inexact |
| 1.5 / 1.0009765625 | 3E00 | 3C01 | 1536 | 1025 | 1536 | 127 | 56 | 3068 | 1028 | 3069 | 0x3DFF | inexact |
| 65504 / 0.5 | 7BFF | 3800 | 2047 | 1024 | 2047 | 127 | 64 | 4093 | 1024 | 4094 | 0x7C00 | overflow, inexact |
| 1.0 / 65504 | 3C00 | 7BFF | 1024 | 2047 | 2048 | 64 | 4 | 2049 | 1 | 2049 | 0x0100 | underflow, inexact |
| 0 / 0 | 0000 | 0000 | | | | | | | | | 0x7E00 | invalid |

## External hardware

None. Drive the pins from a microcontroller or the Tiny Tapeout demo board with the same script as the FP32 divider
(four data bytes instead of eight).
