module logic_gates(
    input a, b,
    output out_and, out_or, out_not_a, out_nand, out_nor, out_xor, out_xnor
);
    assign out_and = a & b;
    assign out_or = a | b;
    assign out_not_a = ~a;
    assign out_nand = ~(a & b);
    assign out_nor = ~(a | b);
    assign out_xor = a ^ b;
    assign out_xnor = ~(a ^ b);
endmodule
