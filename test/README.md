# Tests

Everything here runs with Icarus Verilog 11, cocotb 2.1 and Python 3 + numpy (`pip install -r requirements.txt`).
`~/.local/bin` must be on `PATH` for `cocotb-config`.

## cocotb (pins only: same tests for RTL and gate level)

```sh
make -B                       # RTL: test.py against src/project.v + src/fp16_div_core.v
N_RANDOM=20000 make -B        # more random pairs (default 1000)
FP16_K=4 make -B              # nothing to do for the RTL (K is a compile-time macro); the env var only
                              # tells test_cycle_count which digit width the build under test has
make -B GATES=yes             # gate level of the Tiny Tapeout GDS action netlist (gate_level_netlist.v)
make -f Makefile.gl_local -B  # gate level of the yosys netlist of scripts/synth.sh (synth_out/flat.v)
```

`test.py` checks reset, byte writes, start, DONE/BUSY, result and flags, corner pairs, random pairs,
back-to-back divides, a write strobe held across a divide, a start pulse during a divide, reset in the
middle of a divide and the register map. Expected values come from `../model/fp16_div_model.py`.
To build with another multiplier digit width add `COMPILE_ARGS=-DFP16_K=4` to the make line.

## Core-level regressions (plain Verilog, no cocotb)

All of them take their vectors from `../model/gen_vectors.py` (`a b result flags` per line).

| script / testbench | what it does |
| --- | --- |
| `tb_vectors.v` | drives `fp16_div_core` with a vector file, compares result, flags, `fault`; prints min/avg/max clocks per divide |
| `run_vectors.sh` | the proofs of the model, `directed` (all pairs of 22 corner values), `wide` (600k pairs of every operand class) |
| `run_exhaustive.sh` | ALL 2^20 fraction pairs for 16 exponent/sign combinations (about 16.8 M divides) |
| `tb_fault.v` | fault injection: flips / stuck-at on registers and buses, classified masked / corrected / detected / silent / hang |

```sh
./run_vectors.sh
./run_exhaustive.sh 6          # 6 jobs side by side, one private vector file per job
FP16_K=4 ./run_exhaustive.sh   # same, other multiplier digit width
python3 ../model/gen_vectors.py finite finite.hex 200000
iverilog -g2005 -DFAULT_INJECT -o tb_fault tb_fault.v ../src/fp16_div_core.v
vvp tb_fault +VEC=finite.hex +SEED=1 +NCYC=19
```

Long simulations write only into private files (`mktemp -d`); do not start two `run_exhaustive.sh` at once
if you also run other jobs that create `*.hex` files in this directory.
