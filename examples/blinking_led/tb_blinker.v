module tb_blinker;
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
