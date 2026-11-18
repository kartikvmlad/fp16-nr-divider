"""Print the seed ROM as the Verilog case body used in src/fp16_div_core.v.
Y0 is 7 bits and always 64..127, so only the low 6 bits are stored (the top bit is 1)."""
from fp16_div_model import SEED_ROM

lines = []
for i in range(0, 64, 4):
    lines.append("            " + " ".join(
        f"6'd{i + j}: seed = 6'd{int(SEED_ROM[i + j]) - 64};" for j in range(4)))
print("\n".join(lines))
