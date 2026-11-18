// Drives fp16_div_core with vectors from model/gen_vectors.py and compares result,
// flags and the self-check bit (which must stay 0). Plain Verilog, no cocotb:
//
//   python ../model/gen_vectors.py wide wide.hex
//   iverilog -o tb_vectors tb_vectors.v ../src/fp16_div_core.v
//   vvp tb_vectors +VEC=wide.hex
//
// One 56-bit hex word per line: a (16) b (16) result (16) flags (8). Optional +K=<n> is not
// needed: the digit width is the parameter of the core (see -P tb_vectors.dut.K=6 for iverilog).
`default_nettype none
`timescale 1ns / 1ps
module tb_vectors;
    reg         clk = 0, rst_n = 0, start = 0;
    reg  [15:0] a = 0, b = 0;
    wire [15:0] result;
    wire [4:0]  flags;
    wire        fault, corrected, busy, done;
    fp16_div_core dut (.clk(clk), .rst_n(rst_n), .start(start), .a(a), .b(b),
                       .result(result), .flags(flags), .fault(fault), .corrected(corrected),
                       .busy(busy), .done(done));
    always #5 clk = ~clk;

    reg [55:0]      vec;
    reg [1023:0]    path;
    integer fd, code, n, errors, cycles, max_cycles, min_cycles, sum_cycles, n_fault, n_corr;
    initial begin
        if (!$value$plusargs("VEC=%s", path)) begin
            $display("usage: vvp tb_vectors +VEC=file.hex");
            $finish;
        end
        fd = $fopen(path, "r");
        if (fd == 0) begin
            $display("cannot open vector file");
            $finish;
        end
        n = 0; errors = 0; max_cycles = 0; min_cycles = 1000; sum_cycles = 0; n_fault = 0; n_corr = 0;
        repeat (3) @(posedge clk);
        rst_n = 1;
        code = $fscanf(fd, "%h", vec);
        while (code == 1) begin
            @(negedge clk);
            a = vec[55:40];
            b = vec[39:24];
            start = 1;
            @(negedge clk);
            start = 0;
            cycles = 1;
            while (!done) begin @(negedge clk); cycles = cycles + 1; end
            if (cycles > max_cycles) max_cycles = cycles;
            if (cycles < min_cycles) min_cycles = cycles;
            sum_cycles = sum_cycles + cycles;
            if (fault) n_fault = n_fault + 1;
            if (corrected) n_corr = n_corr + 1;
            if (result !== vec[23:8] || flags !== vec[4:0] || fault !== 1'b0) begin
                errors = errors + 1;
                if (errors <= 10)
                    $display("MISMATCH a=%h b=%h got %h/%b fault=%b exp %h/%b",
                             a, b, result, flags, fault, vec[23:8], vec[4:0]);
            end
            n = n + 1;
            code = $fscanf(fd, "%h", vec);
        end
        $display("vectors=%0d errors=%0d cycles min/avg/max=%0d/%0d.%0d/%0d faults=%0d corrected=%0d",
                 n, errors, min_cycles, sum_cycles / n, (sum_cycles * 10 / n) % 10, max_cycles, n_fault, n_corr);
        $finish;
    end
endmodule
