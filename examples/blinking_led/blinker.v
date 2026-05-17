module blinker(input clk, rst, output reg led);
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
