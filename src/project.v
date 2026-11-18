/*
 * Copyright (c) 2026 Vikas, Shreekara, SreeHarsha, Girish, Kartik, Tharun
 * SPDX-License-Identifier: Apache-2.0
 *
 * FP16 Newton-Raphson divider with fault detection and correction - Tiny Tapeout wrapper.
 *
 * Host interface (byte-wide, same protocol as the FP32 divider):
 *   ui_in[7:0]   data in
 *   address      {uio_in[4], uio_in[1:0]}
 *                write: 0 = A[7:0]  1 = A[15:8]  2 = B[7:0]  3 = B[15:8]   (4..7 ignored)
 *                read:  0 = Q[7:0]  1 = Q[15:8]  2,3 = 0x00  4 = flags  5..7 = status
 *   uio_in[2]    write strobe (one write per strobe; addr/data must be stable while it is high)
 *   uio_in[3]    start (rising edge)
 *   uo_out[7:0]  data out (register selected by address)
 *   uio_out[7]   done (sticky until next start)
 *   uio_out[6]   busy
 *   flags byte  = {fault, corrected, 1'b0, invalid, divzero, overflow, underflow, inexact}
 *                 fault     = a fault was detected and the retry did not clear it (result untrusted)
 *                 corrected = a fault was detected, the divide was repeated and the repeat passed
 *   status byte = {6'b0, busy, done}
 */
`default_nettype none

module tt_um_vikaskumart176_fp16_nr_div (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

    // Only the two strobes are synchronised. Address and data are taken straight
    // from the pins, once per write strobe, when the strobe has been seen high on
    // two consecutive clocks - inside the window where the host holds them stable.
    // A strobe that arrives while the core is busy is not lost: the write is
    // performed when the divide finishes, provided the strobe is still high.
    reg  [1:0] wr_sync, st_sync;
    reg        wr_done, st_prev;
    wire       busy, done;
    wire       start = st_sync[1] & ~st_prev;
    wire       wr    = wr_sync[1] & wr_sync[0] & ~wr_done & ~busy & ~start;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_sync <= 2'b00;
            st_sync <= 2'b00;
            wr_done <= 1'b0;
            st_prev <= 1'b0;
        end else begin
            wr_sync <= {wr_sync[0], uio_in[2]};
            st_sync <= {st_sync[0], uio_in[3]};
            st_prev <= st_sync[1];
            if (!wr_sync[1])
                wr_done <= 1'b0;
            else if (wr)
                wr_done <= 1'b1;
        end
    end

    wire [2:0]  addr = {uio_in[4], uio_in[1:0]};

    reg  [15:0] a_reg, b_reg;
    reg         done_flag;
    wire [15:0] q;
    wire [4:0]  flags;
    wire        fault, corrected;

    // Operand registers have no reset: they are undefined until the host has
    // written all four bytes. The core reads them directly while busy, so they
    // are frozen from the start pulse until the divide finishes.
    always @(posedge clk) begin
        if (wr) begin
            case (addr)
                3'd0: a_reg[7:0]  <= ui_in;
                3'd1: a_reg[15:8] <= ui_in;
                3'd2: b_reg[7:0]  <= ui_in;
                3'd3: b_reg[15:8] <= ui_in;
                default: ;
            endcase
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            done_flag <= 1'b0;
        else if (start)
            done_flag <= 1'b0;
        else if (done)
            done_flag <= 1'b1;
    end

    fp16_div_core u_core (
        .clk       (clk),
        .rst_n     (rst_n),
        .start     (start),
        .a         (a_reg),
        .b         (b_reg),
        .result    (q),
        .flags     (flags),
        .fault     (fault),
        .corrected (corrected),
        .busy      (busy),
        .done      (done)
    );

    reg [7:0] dout;
    always @(*) begin
        case (addr)
            3'd0:    dout = q[7:0];
            3'd1:    dout = q[15:8];
            3'd2:    dout = 8'h00;
            3'd3:    dout = 8'h00;
            3'd4:    dout = {fault, corrected, 1'b0, flags};
            default: dout = {6'd0, busy, done_flag};
        endcase
    end

    assign uo_out  = dout;
    assign uio_out = {done_flag, busy, 6'd0};
    assign uio_oe  = 8'b1100_0000;

    wire _unused = &{ena, uio_in[7:5], 1'b0};

endmodule
