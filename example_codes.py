EXAMPLES = {
    "Half Adder": {
        "verilog": '''module half_adder(
    input a,
    input b,
    output sum,
    output carry
);
    assign sum = a ^ b;
    assign carry = a & b;
endmodule
''',
        "testbench": '''module tb_half_adder;
    reg a, b;
    wire sum, carry;

    half_adder uut (
        .a(a), 
        .b(b), 
        .sum(sum), 
        .carry(carry)
    );

    initial begin
        $dumpfile("sim.vcd");
        $dumpvars(0, tb_half_adder);
        
        a = 0; b = 0; #10;
        a = 0; b = 1; #10;
        a = 1; b = 0; #10;
        a = 1; b = 1; #10;
        
        $display("Simulation complete");
        $finish;
    end
endmodule
'''
    },
    "Full Adder": {
        "verilog": '''module full_adder(
    input a,
    input b,
    input cin,
    output sum,
    output cout
);
    assign sum = a ^ b ^ cin;
    assign cout = (a & b) | (cin & (a ^ b));
endmodule
''',
        "testbench": '''module tb_full_adder;
    reg a, b, cin;
    wire sum, cout;

    full_adder uut (
        .a(a), .b(b), .cin(cin),
        .sum(sum), .cout(cout)
    );

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
        
        $display("Simulation complete");
        $finish;
    end
endmodule
'''
    },
    "Logic Gates (NOR/NOT)": {
        "verilog": '''module logic_gates(
    input a,
    input b,
    output out_nor,
    output out_not_a
);
    assign out_nor = ~(a | b);
    assign out_not_a = ~a;
endmodule
''',
        "testbench": '''module tb_logic_gates;
    reg a, b;
    wire out_nor, out_not_a;

    logic_gates uut (
        .a(a), .b(b),
        .out_nor(out_nor), .out_not_a(out_not_a)
    );

    initial begin
        $dumpfile("sim.vcd");
        $dumpvars(0, tb_logic_gates);
        
        a=0; b=0; #10;
        a=0; b=1; #10;
        a=1; b=0; #10;
        a=1; b=1; #10;
        
        $display("Simulation complete");
        $finish;
    end
endmodule
'''
    },
    "Blinking LED (Counter)": {
        "verilog": '''module blinker(
    input clk,
    input rst,
    output reg led
);
    reg [3:0] count;
    
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            count <= 0;
            led <= 0;
        end else begin
            if (count == 4'd5) begin
                count <= 0;
                led <= ~led;
            end else begin
                count <= count + 1;
            end
        end
    end
endmodule
''',
        "testbench": '''module tb_blinker;
    reg clk, rst;
    wire led;

    blinker uut (
        .clk(clk), .rst(rst), .led(led)
    );

    always #5 clk = ~clk;

    initial begin
        $dumpfile("sim.vcd");
        $dumpvars(0, tb_blinker);
        
        clk = 0; rst = 1;
        #15 rst = 0;
        
        #200;
        $display("Simulation complete");
        $finish;
    end
endmodule
'''
    }
}
