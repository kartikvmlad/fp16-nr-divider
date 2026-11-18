"""Standalone area of MAC variants and an equivalence check against mac_ref (random + corner stimuli, iverilog)."""
import re, subprocess, sys, random

LIB = "synth_out/lib_dontuse.lib"
K = int(sys.argv[1]) if len(sys.argv) > 1 else 8
files = sys.argv[2] if len(sys.argv) > 2 else "scratch/mac_variants.v"
mods = sys.argv[3:] or ["mac_ref", "mac_booth"]


def area(mod):
    script = (f"read_verilog {files}; hierarchy -top {mod}; chparam -set K {K} {mod}; "
              f"synth -top {mod} -flatten; abc -liberty {LIB} -script +strash;ifraig;scorr;dc2;dretime;strash;dch,-f;map,-M,1,-D,30000;topo;stime,-p; "
              f"opt_clean; tee -o scratch/m.txt stat -liberty {LIB}")
    subprocess.run(["yosys", "-q", "-p", script], capture_output=True, text=True)
    return float(re.search(r"Chip area for module '.*': ([0-9.]+)", open("scratch/m.txt").read()).group(1))


for m in mods:
    print(f"{m:14s} K={K} area {area(m):9.1f}")

# equivalence of every other module against the first one
ref = mods[0]
tb = f"""module t; reg signed [12:0] h; reg [11:0] m; reg [{K-1}:0] d; reg s;
wire signed [12:0] nh0; wire [{K-1}:0] sl0; integer i, bad;
{ref} #({K}) a(h,m,d,s,nh0,sl0);
""" + "".join(f"wire signed [12:0] nh{j+1}; wire [{K-1}:0] sl{j+1};\n{x} #({K}) b{j}(h,m,d,s,nh{j+1},sl{j+1});\n" for j, x in enumerate(mods[1:])) + """
initial begin bad=0;
 for (i=0;i<400000;i=i+1) begin
   h=$random; h = h % 4096; if ($random & 1) h = -h; m=$random; d=$random; s=$random;
   #1; """ + " ".join(f"if (nh0!==nh{j+1} || sl0!==sl{j+1}) bad=bad+1;" for j in range(len(mods) - 1)) + """
 end
 $display("mismatches=%0d", bad); $finish; end
endmodule
"""
open("scratch/mac_tb.v", "w").write(tb)
subprocess.run(["iverilog", "-g2005", "-o", "scratch/mac_tb.vvp", "scratch/mac_tb.v", files], check=True)
print(subprocess.run(["vvp", "scratch/mac_tb.vvp"], capture_output=True, text=True).stdout.strip())
