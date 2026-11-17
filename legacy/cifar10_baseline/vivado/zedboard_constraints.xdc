# ============================================================
# zedboard_constraints.xdc
# Xilinx Design Constraints for ZedBoard
# 
# Based on ZedBoard Hardware User's Guide v1.1
# Part: XC7Z020-1CLG484
# ============================================================

# ============================================================
# System Clock (100 MHz PL clock from Fox oscillator IC17)
# ============================================================
# Note: We use the PS FCLK_CLK0 output for our design,
# but this constraint is here if you need the PL clock directly.
set_property PACKAGE_PIN Y9 [get_ports {sys_clk}]
set_property IOSTANDARD LVCMOS33 [get_ports {sys_clk}]
create_clock -period 10.000 -name sys_clk [get_ports {sys_clk}]

# ============================================================
# User LEDs (Active High, 390Ω to 3.3V)
# Bank 33, LVCMOS33
# ============================================================
set_property PACKAGE_PIN T22 [get_ports {led[0]}]
set_property PACKAGE_PIN T21 [get_ports {led[1]}]
set_property PACKAGE_PIN U22 [get_ports {led[2]}]
set_property PACKAGE_PIN U21 [get_ports {led[3]}]
set_property PACKAGE_PIN V22 [get_ports {led[4]}]
set_property PACKAGE_PIN W22 [get_ports {led[5]}]
set_property PACKAGE_PIN U19 [get_ports {led[6]}]
set_property PACKAGE_PIN U14 [get_ports {led[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {led[*]}]

# ============================================================
# User Push Buttons (Active High, pull-down to GND)
# Bank 34/35
# ============================================================
set_property PACKAGE_PIN T18 [get_ports {btn_up}]
set_property PACKAGE_PIN R18 [get_ports {btn_right}]
set_property PACKAGE_PIN R16 [get_ports {btn_down}]
set_property PACKAGE_PIN P16 [get_ports {btn_center}]
set_property PACKAGE_PIN N15 [get_ports {btn_left}]
set_property IOSTANDARD LVCMOS25 [get_ports {btn_*}]

# ============================================================
# User DIP Switches (8 switches)
# Bank 35
# ============================================================
set_property PACKAGE_PIN F22 [get_ports {sw[0]}]
set_property PACKAGE_PIN G22 [get_ports {sw[1]}]
set_property PACKAGE_PIN H22 [get_ports {sw[2]}]
set_property PACKAGE_PIN F21 [get_ports {sw[3]}]
set_property PACKAGE_PIN H19 [get_ports {sw[4]}]
set_property PACKAGE_PIN H18 [get_ports {sw[5]}]
set_property PACKAGE_PIN H17 [get_ports {sw[6]}]
set_property PACKAGE_PIN M15 [get_ports {sw[7]}]
set_property IOSTANDARD LVCMOS25 [get_ports {sw[*]}]

# ============================================================
# OLED Display (128x32, SPI interface)
# Bank 33
# ============================================================
set_property PACKAGE_PIN U10 [get_ports {oled_dc}]
set_property PACKAGE_PIN U9  [get_ports {oled_res}]
set_property PACKAGE_PIN AB12 [get_ports {oled_sclk}]
set_property PACKAGE_PIN AA12 [get_ports {oled_sdin}]
set_property PACKAGE_PIN U11 [get_ports {oled_vbat}]
set_property PACKAGE_PIN U12 [get_ports {oled_vdd}]
set_property IOSTANDARD LVCMOS33 [get_ports {oled_*}]

# ============================================================
# HDMI Output (ADV7511 Transmitter)
# Bank 35, LVCMOS33
# ============================================================
set_property PACKAGE_PIN W18 [get_ports {hdmi_clk}]
set_property PACKAGE_PIN W17 [get_ports {hdmi_vsync}]
set_property PACKAGE_PIN V17 [get_ports {hdmi_hsync}]
set_property PACKAGE_PIN U16 [get_ports {hdmi_de}]
set_property PACKAGE_PIN Y13 [get_ports {hdmi_d[0]}]
set_property PACKAGE_PIN AA12 [get_ports {hdmi_d[1]}]
set_property PACKAGE_PIN AA14 [get_ports {hdmi_d[2]}]
set_property PACKAGE_PIN Y14 [get_ports {hdmi_d[3]}]
set_property PACKAGE_PIN AB15 [get_ports {hdmi_d[4]}]
set_property PACKAGE_PIN AB16 [get_ports {hdmi_d[5]}]
set_property PACKAGE_PIN AA16 [get_ports {hdmi_d[6]}]
set_property PACKAGE_PIN AB17 [get_ports {hdmi_d[7]}]
set_property PACKAGE_PIN AA17 [get_ports {hdmi_d[8]}]
set_property PACKAGE_PIN Y15 [get_ports {hdmi_d[9]}]
set_property PACKAGE_PIN W13 [get_ports {hdmi_d[10]}]
set_property PACKAGE_PIN W15 [get_ports {hdmi_d[11]}]
set_property PACKAGE_PIN V15 [get_ports {hdmi_d[12]}]
set_property PACKAGE_PIN U17 [get_ports {hdmi_d[13]}]
set_property PACKAGE_PIN V14 [get_ports {hdmi_d[14]}]
set_property PACKAGE_PIN V13 [get_ports {hdmi_d[15]}]
set_property IOSTANDARD LVCMOS33 [get_ports {hdmi_*}]

# HDMI I2C
set_property PACKAGE_PIN AA18 [get_ports {hdmi_scl}]
set_property PACKAGE_PIN Y16 [get_ports {hdmi_sda}]
set_property IOSTANDARD LVCMOS33 [get_ports {hdmi_scl}]
set_property IOSTANDARD LVCMOS33 [get_ports {hdmi_sda}]

# HDMI Interrupt
set_property PACKAGE_PIN W16 [get_ports {hdmi_int}]
set_property IOSTANDARD LVCMOS33 [get_ports {hdmi_int}]

# ============================================================
# VGA Output (12-bit color via resistor ladder)
# Bank 33
# ============================================================
set_property PACKAGE_PIN V20 [get_ports {vga_r[3]}]
set_property PACKAGE_PIN U20 [get_ports {vga_r[2]}]
set_property PACKAGE_PIN V19 [get_ports {vga_r[1]}]
set_property PACKAGE_PIN V18 [get_ports {vga_r[0]}]
set_property PACKAGE_PIN AB22 [get_ports {vga_g[3]}]
set_property PACKAGE_PIN AA22 [get_ports {vga_g[2]}]
set_property PACKAGE_PIN AB21 [get_ports {vga_g[1]}]
set_property PACKAGE_PIN AA21 [get_ports {vga_g[0]}]
set_property PACKAGE_PIN Y21 [get_ports {vga_b[3]}]
set_property PACKAGE_PIN Y20 [get_ports {vga_b[2]}]
set_property PACKAGE_PIN AB20 [get_ports {vga_b[1]}]
set_property PACKAGE_PIN AB19 [get_ports {vga_b[0]}]
set_property PACKAGE_PIN AA19 [get_ports {vga_hsync}]
set_property PACKAGE_PIN Y19 [get_ports {vga_vsync}]
set_property IOSTANDARD LVCMOS33 [get_ports {vga_*}]

# ============================================================
# Timing Constraints
# ============================================================
# Allow PS clock to drive PL logic
set_false_path -from [get_clocks clk_fpga_0] -to [get_clocks sys_clk]
set_false_path -from [get_clocks sys_clk] -to [get_clocks clk_fpga_0]
