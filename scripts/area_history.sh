#!/bin/bash
# Flat post-synthesis area of the RTL at every commit that changed src/ (K = 4 for all, plus the
# shipped default of the latest commit). Each commit is exported to a temporary directory, so the
# working tree is not touched.
#
#   scripts/area_history.sh
set -e
cd "$(dirname "$0")/.."
printf "%-9s %-62s %12s %6s\n" commit subject "area um2" flops
for c in $(git log --reverse --format=%h -- src/fp16_div_core.v); do
    d=$(mktemp -d)
    git archive "$c" src scripts 2>/dev/null | tar -x -C "$d"
    [ -x "$d/scripts/synth.sh" ] || chmod +x "$d/scripts/synth.sh" 2>/dev/null || continue
    [ -f "$d/scripts/synth.sh" ] || { rm -rf "$d"; continue; }
    subj=$(git log -1 --format=%s "$c" | cut -c1-60)
    line=$( (cd "$d" && scripts/synth.sh -D FP16_K=4 -o synth_out 2>/dev/null | tail -1) )
    a=$(echo "$line" | sed 's/.*flat area=\([0-9.]*\).*/\1/'); f=$(echo "$line" | sed 's/.*flops=\([0-9]*\).*/\1/')
    printf "%-9s %-62s %12s %6s   (K=4)\n" "$c" "$subj" "$a" "$f"
    rm -rf "$d"
done
c=$(git log -1 --format=%h -- src/fp16_div_core.v)
d=$(mktemp -d)
git archive "$c" src scripts | tar -x -C "$d"
line=$( (cd "$d" && scripts/synth.sh -o synth_out 2>/dev/null | tail -1) )
a=$(echo "$line" | sed 's/.*flat area=\([0-9.]*\).*/\1/'); f=$(echo "$line" | sed 's/.*flops=\([0-9]*\).*/\1/')
printf "%-9s %-62s %12s %6s   (shipped default)\n" "$c" "latest, default K" "$a" "$f"
rm -rf "$d"
