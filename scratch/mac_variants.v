// reference: current MAC
module mac_ref #(parameter K = 8) (
    input  wire signed [12:0] h, input wire [11:0] m, input wire [K-1:0] dig, input wire sgn,
    output wire signed [12:0] nxt_h, output wire [K-1:0] sum_lo);
    localparam SW = 13 + K;
    wire                 t    = dig[K-1];
    wire        [SW-1:0] mt   = {{(SW-12-(K-1)){1'b0}}, m, {(K-1){1'b0}}} & {SW{t}};
    wire        [SW-1:0] row  = mt ^ {SW{t & sgn}};
    wire        [SW-1:0] pp   = m * dig[K-2:0];
    wire        [SW-1:0] hx   = {{(SW-13){h[12]}}, h};
    wire        [SW-1:0] sum  = hx + pp + row + {{(SW-1){1'b0}}, t & sgn};
    wire signed [SW-1:0] sum_s = sum;
    assign nxt_h  = sum_s >>> K;
    assign sum_lo = sum[K-1:0];
endmodule

// radix-4 Booth: the K-bit digit (two's complement when sgn and its top bit is set, else unsigned)
module mac_booth #(parameter K = 8) (
    input  wire signed [12:0] h, input wire [11:0] m, input wire [K-1:0] dig, input wire sgn,
    output wire signed [12:0] nxt_h, output wire [K-1:0] sum_lo);
    localparam SW = 13 + K;
    localparam ND = (K + 2) / 2;                 // digits for K+1 bits
    wire xs = sgn & dig[K-1];
    wire [2*ND:0] xe = {{(2*ND+1-K){xs}}, dig};  // xe[-1] handled as 0 below; index shifted by 1
    // xb[j] = bit j-1 of the extended digit, xb[0] = 0
    wire [2*ND:0] xb = {xe[2*ND-1:0], 1'b0};
    wire [SW-1:0] hx = {{(SW-13){h[12]}}, h};
    reg  [SW-1:0] acc;
    reg  [SW-1:0] cins;
    integer i;
    always @(*) begin : ADD
        reg b2, b1, b0, sel1, sel2, neg;
        reg [SW-1:0] mag;
        acc  = hx;
        cins = 0;
        for (i = 0; i < ND; i = i + 1) begin
            b2 = xb[2*i+2]; b1 = xb[2*i+1]; b0 = xb[2*i];
            sel1 = b1 ^ b0;
            sel2 = (b2 & ~b1 & ~b0) | (~b2 & b1 & b0);
            neg  = b2 & ~(b1 & b0);
            mag  = sel2 ? ({{(SW-13){1'b0}}, m, 1'b0}) : sel1 ? {{(SW-12){1'b0}}, m} : {SW{1'b0}};
            acc  = acc + (((mag ^ {SW{neg}})) << (2*i));
            cins = cins | ({{(SW-1){1'b0}}, neg} << (2*i));
        end
        acc = acc + cins;
    end
    wire signed [SW-1:0] sum_s = acc;
    assign nxt_h  = sum_s >>> K;
    assign sum_lo = acc[K-1:0];
endmodule

// Booth with the sign-extension trick: every row is 14 bits with an inverted sign bit, one constant corrects all
module mac_booth2 #(parameter K = 8) (
    input  wire signed [12:0] h, input wire [11:0] m, input wire [K-1:0] dig, input wire sgn,
    output wire signed [12:0] nxt_h, output wire [K-1:0] sum_lo);
    localparam SW = 13 + K;
    localparam ND = (K + 2) / 2;
    wire xs = sgn & dig[K-1];
    wire [2*ND:0] xe = {{(2*ND+1-K){xs}}, dig};
    wire [2*ND:0] xb = {xe[2*ND-1:0], 1'b0};
    // constant: -(2^12) for h, -(2^13 << 2i) for each row, modulo 2^SW
    function [SW-1:0] kconst;
        input integer dummy;
        integer j;
        reg [SW-1:0] c;
        begin
            c = {SW{1'b0}} - (({{(SW-1){1'b0}}, 1'b1}) << 12);
            for (j = 0; j < ND; j = j + 1) c = c - (({{(SW-1){1'b0}}, 1'b1}) << (13 + 2*j));
            kconst = c;
        end
    endfunction
    reg  [SW-1:0] acc;
    reg  [SW-1:0] cins;
    integer i;
    always @(*) begin : ADD
        reg b2, b1, b0, sel1, sel2, neg;
        reg [12:0] mag;
        reg [13:0] row;
        acc  = {{(SW-13){1'b0}}, ~h[12], h[11:0]} + kconst(0);
        cins = 0;
        for (i = 0; i < ND; i = i + 1) begin
            b2 = xb[2*i+2]; b1 = xb[2*i+1]; b0 = xb[2*i];
            sel1 = b1 ^ b0;
            sel2 = (b2 & ~b1 & ~b0) | (~b2 & b1 & b0);
            neg  = b2 & ~(b1 & b0);
            mag  = sel2 ? {m, 1'b0} : sel1 ? {1'b0, m} : 13'd0;
            row  = {~neg, mag ^ {13{neg}}};
            acc  = acc + ({{(SW-14){1'b0}}, row} << (2*i));
            cins = cins | ({{(SW-1){1'b0}}, neg} << (2*i));
        end
        acc = acc + cins;
    end
    wire signed [SW-1:0] sum_s = acc;
    assign nxt_h  = sum_s >>> K;
    assign sum_lo = acc[K-1:0];
endmodule
