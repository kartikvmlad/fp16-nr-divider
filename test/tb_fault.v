// Fault-injection campaign for the built-in checks and the retry.
//
// For every vector one single-bit fault is injected into the core while it divides:
//   flip     : the bit is inverted once, at a random clock of the first attempt (single-event upset);
//              the retry therefore runs fault-free
//   stuck0/1 : the bit is held at 0 / 1 from the first clock until the divide finishes (permanent
//              defect); the retry sees the same defect
// Targets (uniform over bits): the working registers MA MB ER QR H L ph cnt run rem_r tiny_r spec_r
// rty (direct hierarchical writes at the negative clock edge) and the combinational buses y0 (seed ROM),
// Msel (multiplicand mux), nxtH / sum_lo (multiplier-adder), Qf (corrected quotient) and res (packed
// result) through the `FAULT_INJECT taps in the core.
//
// Every run is classified as
//   masked      result and flags correct, nothing flagged
//   corrected   result and flags correct, the `corrected` flag is set (detected, repeated, passed)
//   detected    `fault` flag set (detected, repeat failed or not possible); result may or may not be right
//   silent      result or flags wrong although no fault was flagged
//   hang        no `done` within the timeout
//
//   python ../model/gen_vectors.py finite finite.hex
//   iverilog -DFAULT_INJECT -o tb_fault tb_fault.v ../src/fp16_div_core.v
//   vvp tb_fault +VEC=finite.hex [+SEED=n] [+TYPES=mask] [+NCYC=n]
//     TYPES: bit mask of flip(1) / stuck0(2) / stuck1(4), default 7;  NCYC: clocks of a normal divide
//     (flips land uniformly in 1..NCYC of the first attempt; default 19 = the K=2 build, use 10 for K=4)
`default_nettype none
`timescale 1ns / 1ps
module tb_fault;
    reg         clk = 0, rst_n = 0, start = 0;
    reg  [15:0] a = 0, b = 0;
    wire [15:0] result;
    wire [4:0]  flags;
    wire        fault, corrected, busy, done;
    fp16_div_core dut (.clk(clk), .rst_n(rst_n), .start(start), .a(a), .b(b),
                       .result(result), .flags(flags), .fault(fault), .corrected(corrected),
                       .busy(busy), .done(done));
    always #5 clk = ~clk;

    localparam NT = 19;
    // target ids: 0 MA 1 MB 2 ER 3 QR 4 H 5 L 6 ph 7 cnt 8 run 9 rem_r 10 tiny_r 11 spec_r 12 rty
    //             13 y0 14 Msel 15 nxtH 16 sum_lo 17 Qf 18 res
    integer tw [0:NT-1];
    reg [8*8-1:0] tn [0:NT-1];
    integer total_bits;

    reg [55:0]   vec;
    reg [1023:0] path;
    integer fd, code, n, seed, i, t, bit_, typ, at, cyc, types_mask, ncyc;
    integer n_masked, n_corr, n_det, n_silent, n_hang, n_inj;
    integer c_masked [0:2], c_corr [0:2], c_det [0:2], c_silent [0:2], c_hang [0:2], c_tot [0:2];
    integer tt_tot [0:NT-1], tt_silent [0:NT-1], tt_det [0:NT-1], tt_corr [0:NT-1], tt_masked [0:NT-1], tt_hang [0:NT-1];
    reg [31:0] mask;
    reg done_seen;
    wire wrong = (result !== vec[23:8]) || (flags !== vec[4:0]);

    // ---- register faults: v = 2 flip, 0 stuck-at-0, 1 stuck-at-1
    task poke_reg(input integer tg, input integer bt, input integer how);
        reg nv;
        begin
            case (tg)
                0:  begin nv = (how == 2) ? ~dut.MA[bt]  : how; dut.MA[bt]  = nv; end
                1:  begin nv = (how == 2) ? ~dut.MB[bt]  : how; dut.MB[bt]  = nv; end
                2:  begin nv = (how == 2) ? ~dut.ER[bt]  : how; dut.ER[bt]  = nv; end
                3:  begin nv = (how == 2) ? ~dut.QR[bt]  : how; dut.QR[bt]  = nv; end
                4:  begin nv = (how == 2) ? ~dut.H[bt]   : how; dut.H[bt]   = nv; end
                5:  begin nv = (how == 2) ? ~dut.L[bt]   : how; dut.L[bt]   = nv; end
                6:  begin nv = (how == 2) ? ~dut.ph[bt]  : how; dut.ph[bt]  = nv; end
                7:  begin nv = (how == 2) ? ~dut.cnt[bt] : how; dut.cnt[bt] = nv; end
                8:  begin nv = (how == 2) ? ~dut.run     : how; dut.run     = nv; end
                9:  begin nv = (how == 2) ? ~dut.rem_r   : how; dut.rem_r   = nv; end
                10: begin nv = (how == 2) ? ~dut.tiny_r  : how; dut.tiny_r  = nv; end
                11: begin nv = (how == 2) ? ~dut.spec_r  : how; dut.spec_r  = nv; end
                12: begin nv = (how == 2) ? ~dut.rty     : how; dut.rty     = nv; end
                default: ;
            endcase
        end
    endtask

    // ---- bus faults through the masks: kind 0 xor (flip), 1 set (stuck-1), 2 clear (stuck-0)
    task poke_tap(input integer tg, input integer bt, input integer kind, input integer on);
        begin
            mask = on ? (32'd1 << bt) : 32'd0;
            case (tg)
                13: case (kind) 0: dut.fi_y0_x = mask; 1: dut.fi_y0_s = mask; 2: dut.fi_y0_c = mask; endcase
                14: case (kind) 0: dut.fi_m_x  = mask; 1: dut.fi_m_s  = mask; 2: dut.fi_m_c  = mask; endcase
                15: case (kind) 0: dut.fi_h_x  = mask; 1: dut.fi_h_s  = mask; 2: dut.fi_h_c  = mask; endcase
                16: case (kind) 0: dut.fi_l_x  = mask; 1: dut.fi_l_s  = mask; 2: dut.fi_l_c  = mask; endcase
                17: case (kind) 0: dut.fi_q_x  = mask; 1: dut.fi_q_s  = mask; 2: dut.fi_q_c  = mask; endcase
                18: case (kind) 0: dut.fi_r_x  = mask; 1: dut.fi_r_s  = mask; 2: dut.fi_r_c  = mask; endcase
                default: ;
            endcase
        end
    endtask

    // apply (on=1) or remove (on=0) the fault; typ 0 flip, 1 stuck0, 2 stuck1
    task inject(input integer tg, input integer bt, input integer ty, input integer on);
        begin
            if (tg < 13) begin
                if (on) poke_reg(tg, bt, (ty == 0) ? 2 : (ty == 1) ? 0 : 1);
            end else
                poke_tap(tg, bt, (ty == 0) ? 0 : (ty == 1) ? 2 : 1, on);
        end
    endtask

    initial begin
        tw[0] = 11; tn[0] = "MA";   tw[1] = 11; tn[1] = "MB";   tw[2] = 7;  tn[2] = "ER";
        tw[3] = 15; tn[3] = "QR";   tw[4] = 13; tn[4] = "H";    tw[5] = 16; tn[5] = "L";
        tw[6] = 3;  tn[6] = "ph";   tw[7] = 2;  tn[7] = "cnt";  tw[8] = 1;  tn[8] = "run";
        tw[9] = 1;  tn[9] = "rem_r"; tw[10] = 1; tn[10] = "tiny_r"; tw[11] = 1; tn[11] = "spec_r";
        tw[12] = 1; tn[12] = "rty"; tw[13] = 7; tn[13] = "y0";  tw[14] = 12; tn[14] = "Msel";
        tw[15] = 13; tn[15] = "nxtH"; tw[16] = 4; tn[16] = "sum_lo"; tw[17] = 12; tn[17] = "Qf";
        tw[18] = 16; tn[18] = "res";
        total_bits = 0;
        for (i = 0; i < NT; i = i + 1) total_bits = total_bits + tw[i];
        if (!$value$plusargs("VEC=%s", path)) begin
            $display("usage: vvp tb_fault +VEC=file.hex [+SEED=n] [+TYPES=mask]");
            $finish;
        end
        if (!$value$plusargs("SEED=%d", seed)) seed = 12345;
        if (!$value$plusargs("TYPES=%d", types_mask)) types_mask = 7;
        if (!$value$plusargs("NCYC=%d", ncyc)) ncyc = 19;       // clocks of a normal divide (K=2: 20 incl. start)
        fd = $fopen(path, "r");
        n = 0; n_masked = 0; n_corr = 0; n_det = 0; n_silent = 0; n_hang = 0; n_inj = 0;
        for (i = 0; i < 3; i = i + 1) begin
            c_masked[i] = 0; c_corr[i] = 0; c_det[i] = 0; c_silent[i] = 0; c_hang[i] = 0; c_tot[i] = 0;
        end
        for (i = 0; i < NT; i = i + 1) begin
            tt_tot[i] = 0; tt_silent[i] = 0; tt_det[i] = 0; tt_corr[i] = 0; tt_masked[i] = 0; tt_hang[i] = 0;
        end
        repeat (3) @(posedge clk);
        rst_n = 1;
        code = $fscanf(fd, "%h", vec);
        while (code == 1) begin
            // pick the fault: a type allowed by TYPES, a target bit uniform over all state / bus bits
            typ = {$random(seed)} % 3;
            while (!((types_mask >> typ) & 1)) typ = {$random(seed)} % 3;
            bit_ = {$random(seed)} % total_bits;
            t = 0;
            while (bit_ >= tw[t]) begin bit_ = bit_ - tw[t]; t = t + 1; end
            at = (typ == 0) ? 1 + ({$random(seed)} % ncyc) : 1;    // flip: any clock of the first attempt
            @(negedge clk);
            a = vec[55:40];
            b = vec[39:24];
            start = 1;
            @(negedge clk);
            start = 0;
            cyc = 1; done_seen = 0;
            while (!done_seen && cyc < 200) begin
                if (typ == 0) begin
                    if (cyc == at) inject(t, bit_, typ, 1);
                    if (cyc == at + 1) inject(t, bit_, typ, 0);      // taps are one-clock pulses
                end else
                    inject(t, bit_, typ, 1);                         // stuck: hold it every clock
                @(negedge clk);
                cyc = cyc + 1;
                if (done) done_seen = 1;
            end
            // remove every fault before looking at the answer
            inject(t, bit_, typ, 0);
            if (typ == 0) inject(t, bit_, typ, 0);
            n_inj = n_inj + 1;
            c_tot[typ] = c_tot[typ] + 1;
            tt_tot[t] = tt_tot[t] + 1;
            if (!done_seen) begin
                n_hang = n_hang + 1; c_hang[typ] = c_hang[typ] + 1; tt_hang[t] = tt_hang[t] + 1;
                rst_n = 0; @(negedge clk); @(negedge clk); rst_n = 1;     // recover
            end else if (fault) begin
                n_det = n_det + 1; c_det[typ] = c_det[typ] + 1; tt_det[t] = tt_det[t] + 1;
            end else if (wrong) begin
                n_silent = n_silent + 1; c_silent[typ] = c_silent[typ] + 1; tt_silent[t] = tt_silent[t] + 1;
            end else if (corrected) begin
                n_corr = n_corr + 1; c_corr[typ] = c_corr[typ] + 1; tt_corr[t] = tt_corr[t] + 1;
            end else begin
                n_masked = n_masked + 1; c_masked[typ] = c_masked[typ] + 1; tt_masked[t] = tt_masked[t] + 1;
            end
            @(negedge clk);
            @(negedge clk);
            code = $fscanf(fd, "%h", vec);
        end
        $display("injected=%0d  masked=%0d  corrected=%0d  detected(fault flag)=%0d  silent_wrong=%0d  hang=%0d",
                 n_inj, n_masked, n_corr, n_det, n_silent, n_hang);
        $display("  flip   : n=%0d masked=%0d corrected=%0d detected=%0d silent=%0d hang=%0d",
                 c_tot[0], c_masked[0], c_corr[0], c_det[0], c_silent[0], c_hang[0]);
        $display("  stuck0 : n=%0d masked=%0d corrected=%0d detected=%0d silent=%0d hang=%0d",
                 c_tot[1], c_masked[1], c_corr[1], c_det[1], c_silent[1], c_hang[1]);
        $display("  stuck1 : n=%0d masked=%0d corrected=%0d detected=%0d silent=%0d hang=%0d",
                 c_tot[2], c_masked[2], c_corr[2], c_det[2], c_silent[2], c_hang[2]);
        for (i = 0; i < NT; i = i + 1)
            $display("  target %-7s bits=%2d  n=%6d masked=%6d corrected=%6d detected=%6d silent=%6d hang=%5d",
                     tn[i], tw[i], tt_tot[i], tt_masked[i], tt_corr[i], tt_det[i], tt_silent[i], tt_hang[i]);
        $finish;
    end
endmodule
