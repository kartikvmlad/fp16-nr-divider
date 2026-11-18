#!/bin/bash
# Exhaustive RTL regression of the divider core: ALL 2^20 fraction pairs for each of the exponent /
# sign combinations below (normal/normal, overflow and underflow boundaries, every subnormal-result
# depth, flush-to-zero, subnormal operands), checked against the golden model (which the proofs in
# model/ tie to exact rational arithmetic). Every combination uses its own private vector file, so
# jobs can run side by side without sharing any file.
#
#   test/run_exhaustive.sh [jobs]        (default 6 parallel jobs; one 2^20 run takes ~1.5 min at K=8, ~4.5 min at K=2)
#   FP16_K=4 test/run_exhaustive.sh      other digit width (the result must not change)
set -e
cd "$(dirname "$0")"
JOBS=${1:-6}
K=${FP16_K:-8}
WORK=$(mktemp -d exh.XXXXXX)
iverilog -g2005 -DFP16_K=$K -o "$WORK/tb" tb_vectors.v ../src/fp16_div_core.v 2>&1 | grep -v timescale || true

# ea eb sa sb
COMBOS="15 15 0 0
15 15 1 0
30 15 0 1
30 14 0 0
29 15 1 1
1 15 0 0
1 16 0 1
1 20 0 0
1 25 1 0
1 26 0 0
1 27 0 0
2 17 0 0
0 15 0 0
15 0 0 0
0 0 0 1
0 1 1 1"

run_one() {
    set -- $1
    ea=$1; eb=$2; sa=$3; sb=$4
    f="$WORK/v_${ea}_${eb}_${sa}_${sb}.hex"
    python3 ../model/gen_vectors.py mant "$f" $ea $eb $sa $sb >/dev/null
    res=$(vvp "$WORK/tb" +VEC="$f" | tail -1)
    rm -f "$f"
    echo "ea=$ea eb=$eb sa=$sa sb=$sb : $res"
}
export -f run_one
export WORK
echo "$COMBOS" | xargs -P "$JOBS" -I{} bash -c 'run_one "{}"' | tee "$WORK/summary.txt"
tot=$(awk '{for(i=1;i<=NF;i++) if($i ~ /^vectors=/){split($i,a,"=");n+=a[2]}} END{print n}' "$WORK/summary.txt")
err=$(awk '{for(i=1;i<=NF;i++) if($i ~ /^errors=/){split($i,a,"=");n+=a[2]}} END{print n+0}' "$WORK/summary.txt")
flt=$(awk '{for(i=1;i<=NF;i++) if($i ~ /^faults=/){split($i,a,"=");n+=a[2]}} END{print n+0}' "$WORK/summary.txt")
echo "TOTAL: $tot divides, $err mismatches, $flt spurious fault flags (K=$K)"
cp "$WORK/summary.txt" exhaustive_K$K.log
rm -rf "$WORK"
[ "$err" = 0 ] && [ "$flt" = 0 ]
