module tb_logic_gates;
    reg a, b;
    wire out_and, out_or, out_not_a, out_nand, out_nor, out_xor, out_xnor;
    logic_gates uut (
        .a(a), .b(b),
        .out_and(out_and), .out_or(out_or), .out_not_a(out_not_a),
        .out_nand(out_nand), .out_nor(out_nor), .out_xor(out_xor), .out_xnor(out_xnor)
    );
    initial begin
        $dumpfile("sim.vcd");
        $dumpvars(0, tb_logic_gates);
        a=0; b=0; #10;
        a=0; b=1; #10;
        a=1; b=0; #10;
        a=1; b=1; #10;
        $finish;
    end
endmodule
