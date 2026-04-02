module and2 # (
    parameter DWIDTH = 10
)(
    input wire [DWIDTH-1:0] a ,
    input [DWIDTH-1:0] b ,

    output [DWIDTH-1:0] c
);


parameter AWIDTH = 30;
localparam TEST = 1;

assign c = a & b;

endmodule