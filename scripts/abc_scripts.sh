#!/bin/bash
# Flat area of the current RTL under several abc scripts (idea 7: does the script matter?).
#   scripts/abc_scripts.sh [K]
cd "$(dirname "$0")/.."
K=${1:-8}
LIB=synth_out/lib_dontuse.lib
[ -s $LIB ] || python3 scripts/mklib.py $HOME/pdks/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib $LIB > /dev/null
while IFS='|' read -r n s; do
    yosys -q -p "read_verilog -DFP16_K=$K src/project.v src/fp16_div_core.v; hierarchy -top tt_um_vikaskumart176_fp16_nr_div; synth -top tt_um_vikaskumart176_fp16_nr_div -flatten; dfflibmap -liberty $LIB; abc -liberty $LIB -script +$s; opt_clean; tee -o /tmp/abc_$n.txt stat -liberty $LIB" > /dev/null 2>&1
    echo "$n: $(grep -i 'chip area' /tmp/abc_$n.txt 2>/dev/null | tail -1 | sed 's/.*: //')   [$s]"
done <<'EOF'
H(current)|strash;ifraig;scorr;dc2;dretime;strash;dch,-f;map,-M,1,-D,30000;topo;stime,-p
G|strash;dc2;strash;dch,-f;map,-M,1,-D,30000;topo;stime,-p
I|strash;ifraig;scorr;dc2;dretime;strash;dch,-f;map,-M,1,-D,30000;topo;buffer;upsize,-D,30000;dnsize,-D,30000;stime,-p
M|strash;ifraig;scorr;dc2;dretime;strash;dch,-f;amap;topo;stime,-p
N|strash;ifraig;scorr;dc2;dretime;strash;dch,-f;map,-M,1,-a,-D,30000;topo;stime,-p
O|strash;dc2;dc2;strash;dch,-f;map,-M,1,-D,30000;topo;stime,-p
EOF
