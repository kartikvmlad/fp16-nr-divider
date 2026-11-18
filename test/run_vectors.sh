#!/bin/bash
# Core-level regression without cocotb: the proofs of the model, the directed corner set and a wide
# sweep of every operand class, then a short fault-injection campaign. Needs python3 + numpy and iverilog.
# (The long exhaustive run is test/run_exhaustive.sh.)
set -e
cd "$(dirname "$0")"
K=${FP16_K:-2}
python3 ../model/verify_mantissa.py
python3 ../model/verify_reference.py 20000
iverilog -g2005 -DFP16_K=$K -o tb_vectors tb_vectors.v ../src/fp16_div_core.v
for mode in directed wide; do
    python3 ../model/gen_vectors.py $mode $mode.hex
    vvp tb_vectors +VEC=$mode.hex
done
iverilog -g2005 -DFP16_K=$K -DFAULT_INJECT -o tb_fault tb_fault.v ../src/fp16_div_core.v
python3 ../model/gen_vectors.py finite finite.hex 20000
vvp tb_fault +VEC=finite.hex | head -5
