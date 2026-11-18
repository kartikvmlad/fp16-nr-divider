#!/bin/bash
# Area and fault-injection coverage of every fault-tolerance feature, one at a time:
# the full design, then the design with exactly one feature switched off (compile-time macros in
# src/fp16_div_core.v), then everything off. Prints one line per build:
#   area (flat, um2), flops, then the injection summary line of test/tb_fault.v.
#
#   scripts/ablate_checks.sh [n_vectors] [K]      (default 20000 vectors, K=2)
#
# The injection campaign is test/tb_fault.v (same seed for every build, so builds are comparable).
set -e
cd "$(dirname "$0")/.."
N=${1:-20000}
K=${2:-2}
NCYC=$(python3 - <<EOF
k=$K
c=lambda a,b:-(-a//b)
print(2*c(7,k)+c(8,k)+c(11,k)+1)
EOF
)
python3 model/gen_vectors.py finite test/finite_abl.hex $N > /dev/null
OUT=synth_out/ablate
mkdir -p $OUT
run() {
    name=$1; shift
    defs="-DFP16_K=$K $*"
    sdefs=""
    for d in $*; do sdefs="$sdefs -D ${d#-D}"; done
    area=$(scripts/synth.sh -D FP16_K=$K $sdefs -o $OUT/$name | sed 's/.*flat area=\([0-9.]*\).*flops=\([0-9]*\).*/\1 \2/')
    iverilog -g2005 -DFAULT_INJECT $defs -o $OUT/tb_$name.vvp test/tb_fault.v src/fp16_div_core.v 2>&1 | grep -v timescale || true
    res=$(vvp $OUT/tb_$name.vvp +VEC=test/finite_abl.hex +NCYC=$NCYC | head -1)
    echo "$name | area/flops: $area | $res"
}
run full
run no_retry      -DFP16_NO_RETRY
run no_er_check   -DFP16_NO_CHK_ER
run no_src_check  -DFP16_NO_CHK_SRC
run no_rem_check  -DFP16_NO_CHK_REM
run no_checks     -DFP16_NO_RETRY -DFP16_NO_CHK_ER -DFP16_NO_CHK_SRC -DFP16_NO_CHK_REM
rm -f test/finite_abl.hex
