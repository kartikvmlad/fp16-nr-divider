/* C ports for the exhaustive 2^32 run:
 *   ref_int : exact IEEE binary16 division on integers (port of model/ref_exact.py: ref_int)
 *   model   : the Newton-Raphson algorithm of model/fp16_div_model.py (and of src/fp16_div_core.v)
 *
 *   gcc -O2 -fopenmp -o exhaustive model16.c && ./exhaustive
 *       runs all 2^32 operand pairs, counts disagreements between model and reference (bits and flags)
 *       and prints checksums of both result streams; verify_exhaustive.py computes the same
 *       checksum from the numpy model so the python model is tied to the exact reference as well.
 *   ./exhaustive pairs.txt out.txt   evaluates the pairs listed in a file (hex a b per line),
 *                                    writes "a b ref_bits ref_flags model_bits model_flags" (used to
 *                                    cross-check this C port against the Fraction reference).
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef unsigned __int128 u128;
static const int ROM[64] = {127,125,123,121,120,118,116,115,113,111,110,109,107,106,104,103,102,101,99,98,97,96,95,94,93,92,91,90,89,88,87,86,85,84,83,82,82,81,80,79,78,78,77,76,76,75,74,73,73,72,72,71,70,70,69,69,68,67,67,66,66,65,65,64};
#define QNAN 0x7E00
#define INF 0x7C00

static int bitlen(u128 x) { int n = 0; while (x) { n++; x >>= 1; } return n; }

static int classify(unsigned a, unsigned b, unsigned *res, unsigned *fl) {
    unsigned sa = a >> 15, ea = (a >> 10) & 31, fa = a & 1023;
    unsigned sb = b >> 15, eb = (b >> 10) & 31, fb = b & 1023, s = sa ^ sb;
    int an = ea == 31 && fa, bn = eb == 31 && fb, ai = ea == 31 && !fa, bi = eb == 31 && !fb;
    int az = !ea && !fa, bz = !eb && !fb;
    int snan = (an && !(fa >> 9)) || (bn && !(fb >> 9));
    if (an || bn) { *res = QNAN; *fl = snan ? 16 : 0; return 1; }
    if ((ai && bi) || (az && bz)) { *res = QNAN; *fl = 16; return 1; }
    if (ai || bz) { *res = (s << 15) | INF; *fl = ai ? 0 : 8; return 1; }
    if (az || bi) { *res = s << 15; *fl = 0; return 1; }
    return 0;
}

void ref_int(unsigned a, unsigned b, unsigned *res, unsigned *fl) {
    if (classify(a, b, res, fl)) return;
    unsigned sa = a >> 15, ea = (a >> 10) & 31, fa = a & 1023;
    unsigned sb = b >> 15, eb = (b >> 10) & 31, fb = b & 1023, s = sa ^ sb;
    int xa = ea ? (int)ea - 25 : -24, xb = eb ? (int)eb - 25 : -24;
    u128 num = ea ? (fa | 1024) : fa, den = eb ? (fb | 1024) : fb;
    int x = xa - xb;
    if (x >= 0) num <<= x; else den <<= -x;
    int e = bitlen(num) - bitlen(den);
    u128 l = num << (e < 0 ? -e : 0), r = den << (e > 0 ? e : 0);
    if (l < r) e--;
    /* round at lsb = e-10 */
    int lsbs[2] = {e - 10, e - 10 > -24 ? e - 10 : -24};
    uint64_t kk[2]; int inex[2];
    for (int i = 0; i < 2; i++) {
        int lsb = lsbs[i];
        u128 n = lsb < 0 ? num << -lsb : num, d = lsb < 0 ? den : den << lsb;
        u128 k = n / d, rem = n % d;
        if (2 * rem > d || (2 * rem == d && (k & 1))) k++;
        kk[i] = (uint64_t)k; inex[i] = rem != 0;
    }
    int e_unb = kk[0] == 2048 ? e + 1 : e;
    int tiny = e_unb < -14;
    int lsb = lsbs[1];
    uint64_t k = kk[1]; int inexact = inex[1];
    if (k == 0) { *res = s << 15; *fl = 3; return; }
    int blen = bitlen(k), top = blen - 1 + lsb;
    if (top > 15) { *res = (s << 15) | INF; *fl = 5; return; }
    unsigned bits;
    if (top < -14) bits = (unsigned)k;
    else bits = ((unsigned)(top + 15) << 10) | (unsigned)((k << (10 - (blen - 1))) & 1023);
    *res = (s << 15) | bits;
    *fl = (inexact ? 1 : 0) | ((tiny && inexact) ? 2 : 0);
}

static int clz11(unsigned f) { int n = 0; for (int b = 10; b >= 0 && !((f >> b) & 1); b--) n++; return n; }

void model(unsigned a, unsigned b, unsigned *res, unsigned *fl) {
    if (classify(a, b, res, fl)) return;
    unsigned sa = a >> 15, ea = (a >> 10) & 31, fa = a & 1023;
    unsigned sb = b >> 15, eb = (b >> 10) & 31, fb = b & 1023, s = sa ^ sb;
    int lza = ea ? 0 : clz11(fa), lzb = eb ? 0 : clz11(fb);
    int ma = ea ? (fa | 1024) : (fa << lza), mb = eb ? (fb | 1024) : (fb << lzb);
    int Ea = ea ? (int)ea : 1 - lza, Eb = eb ? (int)eb : 1 - lzb;
    int ge = ma >= mb, n = ge ? ma : ma << 1;
    int y0 = ROM[(mb >> 4) & 63];
    int t = mb * y0, e = ((1 << 17) - t) >> 4;
    int q0 = (n * y0) >> 4;
    int dq = ((q0 >> 4) * e) >> 9;
    int q1 = (q0 + dq) >> 2;
    int rr = (n << 11) - q1 * mb;
    int ge2 = rr >= mb, q = q1 + ge2, rem_nz = (rr - (ge2 ? mb : 0)) != 0;
    int E = Ea - Eb + 15 - (ge ? 0 : 1);
    int keep_u = q >> 1, rnd_u = q & 1, inc_u = rnd_u & (rem_nz | (keep_u & 1));
    int tiny = (E + ((keep_u + inc_u) >> 11)) <= 0;
    int sh = 1 - E; sh = sh < 0 ? 0 : sh > 13 ? 13 : sh;
    int shifted_out = (q & ((1 << sh) - 1)) != 0, qd = q >> sh;
    int Er = E <= 0 ? 0 : E;
    int keep = qd >> 1, rnd = qd & 1, stk = rem_nz | shifted_out, inexact = rnd | stk;
    keep += rnd & (stk | (keep & 1));
    if (keep >> 11) { keep >>= 1; Er++; }
    if (E <= 0 && (keep >> 10)) Er = 1;
    int ovf = Er >= 31;
    *res = ovf ? ((s << 15) | INF) : ((s << 15) | (Er << 10) | (keep & 1023));
    *fl = ovf ? 5 : ((tiny && inexact ? 2 : 0) | (inexact ? 1 : 0));
}

int main(int argc, char **argv) {
    if (argc == 3) {
        FILE *f = fopen(argv[1], "r"), *o = fopen(argv[2], "w");
        unsigned a, b, r1, f1, r2, f2;
        while (fscanf(f, "%x %x", &a, &b) == 2) {
            ref_int(a, b, &r1, &f1); model(a, b, &r2, &f2);
            fprintf(o, "%04x %04x %04x %02x %04x %02x\n", a, b, r1, f1, r2, f2);
        }
        return 0;
    }
    uint64_t hr = 0, hm = 0, bad = 0;
    #pragma omp parallel for reduction(+:hr,hm,bad) schedule(static)
    for (int64_t i = 0; i < (1LL << 32); i++) {
        unsigned a = (unsigned)(i >> 16), b = (unsigned)(i & 0xFFFF), r1, f1, r2, f2;
        ref_int(a, b, &r1, &f1); model(a, b, &r2, &f2);
        uint64_t w = (uint64_t)i * 0x9E3779B97F4A7C15ULL + 0xD1B54A32D192ED03ULL;
        hr += ((uint64_t)(r1 | (f1 << 16)) + 1) * w;
        hm += ((uint64_t)(r2 | (f2 << 16)) + 1) * w;
        if (r1 != r2 || f1 != f2) bad++;
    }
    printf("pairs=4294967296 mismatches(model vs exact reference)=%llu\n", (unsigned long long)bad);
    printf("checksum_ref=%016llx\nchecksum_model=%016llx\n", (unsigned long long)hr, (unsigned long long)hm);
    return bad != 0;
}
