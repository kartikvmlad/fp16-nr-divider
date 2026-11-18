#!/bin/bash
# Reusable area / timing measurement: yosys + abc against sky130_fd_sc_hd tt_025C_1v80.
#
#   scripts/synth.sh [-t top] [-p period_ps] [-D define] [-o outdir] [files...]
#
# Default: top = tt_um_vikaskumart176_fp16_nr_div, sources = src/project.v src/fp16_div_core.v.
# Writes into <outdir> (default synth_out/):
#   hier.txt   hierarchical `stat -liberty` (area per module, cells, flops)
#   flat.txt   flattened `stat -liberty`    (the number that matters)
#   timing.txt abc `stime -p` critical path of the flattened, mapped netlist
#   flat.v     flattened gate-level netlist
# and prints a summary. The area is post-synthesis cell area only (no placement, CTS, buffers,
# fill); see docs/info.md for how this relates to the tile.
set -e
cd "$(dirname "$0")/.."
RAWLIB=${RAWLIB:-$HOME/pdks/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib}
TOP=tt_um_vikaskumart176_fp16_nr_div
PERIOD=30000
OUT=synth_out
DEFS=""
while getopts "t:p:D:o:" o; do
    case $o in
        t) TOP=$OPTARG ;;
        p) PERIOD=$OPTARG ;;
        D) DEFS="$DEFS -D$OPTARG" ;;
        o) OUT=$OPTARG ;;
    esac
done
shift $((OPTIND - 1))
SRC=${@:-"src/project.v src/fp16_div_core.v"}
mkdir -p "$OUT"
# the library without the cells the real flow never uses (lpflow_*, probes, EXTRA_EXCLUDED_CELLS)
LIB=$OUT/lib_dontuse.lib
[ -s "$LIB" ] || python3 scripts/mklib.py "$RAWLIB" "$LIB" >/dev/null
# generic abc script: area-oriented mapping with a delay target, then buffering / sizing and timing report
ABC="strash;ifraig;scorr;dc2;dretime;strash;dch,-f;map,-M,1,{D};topo;stime,-p"

# hierarchical
yosys -q -l "$OUT/hier.log" -p "
    read_verilog $DEFS $SRC
    hierarchy -top $TOP
    synth -top $TOP
    dfflibmap -liberty $LIB
    abc -liberty $LIB -D $PERIOD
    opt_clean
    tee -o $OUT/hier.txt stat -liberty $LIB
" >/dev/null 2>&1

# flattened
yosys -q -l "$OUT/flat.log" -p "
    read_verilog $DEFS $SRC
    hierarchy -top $TOP
    synth -top $TOP -flatten
    dfflibmap -liberty $LIB
    abc -liberty $LIB -D $PERIOD -script +$ABC
    opt_clean
    tee -o $OUT/flat.txt stat -liberty $LIB
    write_verilog -noattr $OUT/flat.v
" >/dev/null 2>&1

grep -A200 "Printing statistics" "$OUT/flat.txt" > /dev/null
AREA=$(grep -i "Chip area for module" "$OUT/flat.txt" | tail -1 | awk '{print $NF}')
FLOPS=$(grep -E "sky130_fd_sc_hd__(df|edf|sdf|dl)" "$OUT/flat.txt" | awk '{n+=$2} END{print n+0}')
CELLS=$(grep -E "^ +[0-9]+ +cells$|Number of cells" "$OUT/flat.txt" | tail -1 | awk '{print $1}')
grep -E "ABC: (WireLoad|Start-point|End-point|Path)" "$OUT/flat.log" | tail -40 > "$OUT/timing.txt" || true
DELAY=$(grep -E "ABC: WireLoad" "$OUT/flat.log" | tail -1 | sed -n 's/.*Delay = *\([0-9.]*\) ps.*/\1/p')
echo "top=$TOP  flat area=${AREA} um2  flops=${FLOPS}  cells=${CELLS}  abc delay=${DELAY:-n/a} ps (period ${PERIOD} ps)"
