import os

base_dir = r"d:\Projects\Verilog_compiler\examples"

examples = {
    "full_adder": {
        "full_adder.v": """module full_adder(
    input a, b, cin,
    output sum, cout
);
    assign sum = a ^ b ^ cin;
    assign cout = (a & b) | (cin & (a ^ b));
endmodule
""",
        "tb_full_adder.v": """module tb_full_adder;
    reg a, b, cin;
    wire sum, cout;
    full_adder uut (.a(a), .b(b), .cin(cin), .sum(sum), .cout(cout));
    initial begin
        $dumpfile("sim.vcd");
        $dumpvars(0, tb_full_adder);
        a=0; b=0; cin=0; #10;
        a=0; b=0; cin=1; #10;
        a=0; b=1; cin=0; #10;
        a=0; b=1; cin=1; #10;
        a=1; b=0; cin=0; #10;
        a=1; b=0; cin=1; #10;
        a=1; b=1; cin=0; #10;
        a=1; b=1; cin=1; #10;
        $finish;
    end
endmodule
"""
    },
    "half_adder": {
        "half_adder.v": """module half_adder(input a, b, output sum, carry);
    assign sum = a ^ b;
    assign carry = a & b;
endmodule
""",
        "tb_half_adder.v": """module tb_half_adder;
    reg a, b;
    wire sum, carry;
    half_adder uut (.a(a), .b(b), .sum(sum), .carry(carry));
    initial begin
        $dumpfile("sim.vcd");
        $dumpvars(0, tb_half_adder);
        a=0; b=0; #10;
        a=0; b=1; #10;
        a=1; b=0; #10;
        a=1; b=1; #10;
        $finish;
    end
endmodule
"""
    },
    "logic_gates": {
        "logic_gates.v": """module logic_gates(
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
""",
        "tb_logic_gates.v": """module tb_logic_gates;
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
"""
    },
    "blinking_led": {
        "blinker.v": """module blinker(input clk, rst, output reg led);
    reg [3:0] count;
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            count <= 0;
            led <= 0;
        end else if (count == 4'd5) begin
            count <= 0;
            led <= ~led;
        end else begin
            count <= count + 1;
        end
    end
endmodule
""",
        "tb_blinker.v": """module tb_blinker;
    reg clk, rst;
    wire led;
    blinker uut (.clk(clk), .rst(rst), .led(led));
    always #5 clk = ~clk;
    initial begin
        $dumpfile("sim.vcd");
        $dumpvars(0, tb_blinker);
        clk = 0; rst = 1; #15; rst = 0; #200;
        $finish;
    end
endmodule
"""
    }
}

os.makedirs(base_dir, exist_ok=True)
for folder, files in examples.items():
    folder_path = os.path.join(base_dir, folder)
    os.makedirs(folder_path, exist_ok=True)
    for fname, content in files.items():
        with open(os.path.join(folder_path, fname), 'w') as f:
            f.write(content)
            
print("Examples generated successfully!")
