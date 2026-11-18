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

| check | catches | area (flat, K=2, removed alone) |
| --- | --- | --- |
| remainder check (`hi_ok`, `R < 2*mb`) | wrong Q1 / Q0 / seed / any flip or stuck bit in the P2-P4 multiplier, adder, accumulator and shift path | 70 |
| ER == start value (normal operands) | flips / stuck bits of the exponent register | -5 (noise) |
| MA, MB == operand registers (normal operands) | flips / stuck bits of the mantissa registers | 190 |
| retry once (time redundancy) | transient faults: result is delivered with `corrected` set | 44 |

(The area column is the measured flat difference to the full build; differences of about +-150 are abc noise.
All checks together: 10,314 vs 9,711 with none.) P4 multiplies the held Q1, so a flip of Q1 is also seen by the remainder check.

**Behaviour.** A failed check repeats the whole divide once (the operands, `MA/MB/ER` are reloaded from the operand registers).
Repeat passes: result delivered, `corrected = 1`. Repeat fails: result delivered, `fault = 1` (do not trust it).
Specials never raise `fault`.

**Measured with test/tb_fault.v** (200,000 single-bit faults, uniform over 147 modelled bits of
registers and buses, 1/3 each: one-clock flip, stuck-at-0, stuck-at-1 from the first clock; seed 12345):

| | flip | stuck-at-0 | stuck-at-1 | all |
| --- | --- | --- | --- | --- |
| injected | 66,897 | 66,601 | 66,502 | 200,000 |
| masked (answer right, nothing flagged) | 34,014 | 24,543 | 22,695 | 81,252 |
| corrected (retry gave the right answer) | 30,510 | 193 | 694 | 31,397 |
| detected, `fault` flag | 0 | 33,751 | 33,725 | 67,476 |
| **silent wrong** | 1,946 | 6,071 | 8,117 | **16,134** |
| hang (no `done`) | 427 | 2,043 | 1,271 | 3,741 |

Leave-one-out on 20,000 faults: no checks at all 8,391 silent wrong; remainder check removed 6,773; ER check removed 2,152
(full: 1,618); MA/MB check removed 2,261; retry removed leaves silent unchanged but turns 3,163 corrected into detected.

**What is not covered (honest list).**
- The logic after the check: corrected quotient `Qf`, rounder and result pack (about 11.7k of the 16.1k silent cases).
- `spec_r`, `ph`, `rem_r`, `tiny_r` flips, subnormal-operand / subnormal-result paths for the ER and MA/MB checks.
- Faults that make the FSM hang (`run`, `ph`, `cnt`, `ER` in the shift loops): 1.9% of injections. There is no watchdog; the host must time out and reset.
- Retry fixes transient faults, not permanent stuck-at defects: stuck-at faults mostly end as `fault = 1` (detected, not corrected); `corrected` after a stuck-at is rare (0.7%) and only when the defect is masked on the second pass.
- The operand registers and the wrapper are unprotected. The diverse fallback (slow restoring division) was NOT built: the area budget is used up.

## How to test

```sh
cd test && make -B                                   # cocotb, RTL (9 tests)
make -f Makefile.gl_local -B                         # same tests on the yosys gate netlist (scripts/synth.sh first)
./run_vectors.sh ; ./run_exhaustive.sh               # core-level regressions
cd ../model && python3 verify_mantissa.py && python3 verify_reference.py && python3 verify_exhaustive.py <checksum>
cd c && gcc -O2 -fopenmp -o exhaustive model16.c && ./exhaustive
```

Measured results: 16 exponent/sign combinations x all 2^20 fraction pairs through the RTL = 16,777,216 divides, 0 mismatches,
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
