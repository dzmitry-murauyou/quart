// megafunction wizard: %LPM_FF%
// VERSION: WM1.0
// GENERATION: STANDARD
// VERSION: WM1.0
// MODULE: lpm_ff 

// ============================================================
// THIS FILE IS PROVIDED BY WIZARD AS-IS. 1-bit DFF used to build
// the Read-latency pipeline strobes (RD1/RD2) in Block1.bdf.
// ============================================================

`timescale 1 ps / 1 ps
module lpm_dff1 (
	clock,
	data,
	q);

	input	  clock;
	input	  data;
	output	  q;

	wire [0:0] sub_wire0;
	wire  q = sub_wire0[0:0];

	lpm_ff	lpm_ff_component (
				.clock (clock),
				.data (data),
				.q (sub_wire0)
				,
				.aclr (),
				.aload (),
				.aset (),
				.enable (),
				.sclr (),
				.sload (),
				.sset ());
	defparam
		lpm_ff_component.lpm_fftype = "DFF",
		lpm_ff_component.lpm_type = "LPM_FF",
		lpm_ff_component.lpm_width = 1;

endmodule
