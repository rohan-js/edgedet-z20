# Creates the EdgeDet-Z20 ZedBoard block design in the current Vivado project.
# The caller must set EDZ_IP_REPO and source config/address_map.tcl first.

if {![info exists EDZ_IP_REPO]} { error "EDZ_IP_REPO is not set" }
if {![info exists EDZ_ACCEL_BASE]} { error "address_map.tcl was not sourced" }

set ip_defs [get_ipdefs -all -quiet *:edgedet_top:*]
if {[llength $ip_defs] == 0} {
    error "edgedet_top IP was not found under $EDZ_IP_REPO"
}
set edgedet_vlnv [get_property VLNV [lindex $ip_defs end]]

create_bd_design edgedet_system

set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 processing_system7_0]
# apply_board_preset is required: it supplies the ZedBoard DDR3/MIO electrical
# configuration. The build driver refuses to proceed without Digilent board files.
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps
set_property -dict [list \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_USE_S_AXI_HP0 {1} \
    CONFIG.PCW_USE_FABRIC_INTERRUPT {1} \
    CONFIG.PCW_IRQ_F2P_INTR {1} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100.000000}] $ps

set detector [create_bd_cell -type ip -vlnv $edgedet_vlnv edgedet_top_0]
set dma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma_0]
set_property -dict [list \
    CONFIG.c_include_sg {0} \
    CONFIG.c_include_mm2s {1} \
    CONFIG.c_include_s2mm {1} \
    CONFIG.c_include_mm2s_dre {1} \
    CONFIG.c_include_s2mm_dre {1} \
    CONFIG.c_m_axis_mm2s_tdata_width {64} \
    CONFIG.c_s_axis_s2mm_tdata_width {64} \
    CONFIG.c_mm2s_burst_size {16} \
    CONFIG.c_s2mm_burst_size {16}] $dma

set control_ic [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_control_ic]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {2}] $control_ic
set data_ic [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_data_ic]
set_property -dict [list CONFIG.NUM_SI {2} CONFIG.NUM_MI {1}] $data_ic
set reset [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 proc_sys_reset_0]
set_property CONFIG.C_EXT_RESET_HIGH {0} $reset
set reset_locked [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 reset_locked]
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] $reset_locked
set irqs [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 interrupt_concat]
set_property CONFIG.NUM_PORTS {3} $irqs

# Control and DDR paths.
connect_bd_intf_net [get_bd_intf_pins $ps/M_AXI_GP0] [get_bd_intf_pins $control_ic/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins $control_ic/M00_AXI] [get_bd_intf_pins $dma/S_AXI_LITE]
connect_bd_intf_net [get_bd_intf_pins $control_ic/M01_AXI] [get_bd_intf_pins $detector/s_axi_control]
connect_bd_intf_net [get_bd_intf_pins $dma/M_AXI_MM2S] [get_bd_intf_pins $data_ic/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins $dma/M_AXI_S2MM] [get_bd_intf_pins $data_ic/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins $data_ic/M00_AXI] [get_bd_intf_pins $ps/S_AXI_HP0]

# Stream direction is DDR -> detector -> DDR.
connect_bd_intf_net [get_bd_intf_pins $dma/M_AXIS_MM2S] [get_bd_intf_pins $detector/s_axis_pixels]
connect_bd_intf_net [get_bd_intf_pins $detector/m_axis_predictions] [get_bd_intf_pins $dma/S_AXIS_S2MM]

# One 100 MHz clock domain.
connect_bd_net [get_bd_pins $ps/FCLK_CLK0] \
    [get_bd_pins $ps/M_AXI_GP0_ACLK] [get_bd_pins $ps/S_AXI_HP0_ACLK] \
    [get_bd_pins $reset/slowest_sync_clk] [get_bd_pins $detector/ap_clk] \
    [get_bd_pins $dma/s_axi_lite_aclk] [get_bd_pins $dma/m_axi_mm2s_aclk] \
    [get_bd_pins $dma/m_axi_s2mm_aclk] \
    [get_bd_pins $control_ic/ACLK] [get_bd_pins $control_ic/S00_ACLK] \
    [get_bd_pins $control_ic/M00_ACLK] [get_bd_pins $control_ic/M01_ACLK] \
    [get_bd_pins $data_ic/ACLK] [get_bd_pins $data_ic/S00_ACLK] \
    [get_bd_pins $data_ic/S01_ACLK] [get_bd_pins $data_ic/M00_ACLK]
connect_bd_net [get_bd_pins $ps/FCLK_RESET0_N] [get_bd_pins $reset/ext_reset_in]
connect_bd_net [get_bd_pins $reset_locked/dout] [get_bd_pins $reset/dcm_locked]
connect_bd_net [get_bd_pins $reset/peripheral_aresetn] \
    [get_bd_pins $detector/ap_rst_n] [get_bd_pins $dma/axi_resetn] \
    [get_bd_pins $control_ic/ARESETN] [get_bd_pins $control_ic/S00_ARESETN] \
    [get_bd_pins $control_ic/M00_ARESETN] [get_bd_pins $control_ic/M01_ARESETN] \
    [get_bd_pins $data_ic/ARESETN] [get_bd_pins $data_ic/S00_ARESETN] \
    [get_bd_pins $data_ic/S01_ARESETN] [get_bd_pins $data_ic/M00_ARESETN]

# IRQ_F2P[0]=MM2S, [1]=S2MM, [2]=accelerator done.
connect_bd_net [get_bd_pins $dma/mm2s_introut] [get_bd_pins $irqs/In0]
connect_bd_net [get_bd_pins $dma/s2mm_introut] [get_bd_pins $irqs/In1]
connect_bd_net [get_bd_pins $detector/interrupt] [get_bd_pins $irqs/In2]
connect_bd_net [get_bd_pins $irqs/dout] [get_bd_pins $ps/IRQ_F2P]

# Fixed AXI-Lite control map.
assign_bd_address -offset $EDZ_DMA_BASE -range $EDZ_DMA_RANGE \
    [get_bd_addr_segs $dma/S_AXI_LITE/Reg]
assign_bd_address -offset $EDZ_ACCEL_BASE -range $EDZ_ACCEL_RANGE \
    [get_bd_addr_segs $detector/s_axi_control/Reg]
# Map both DMA address spaces to PS DDR/OCM. Software reserves the two buffers
# declared in address_map.tcl and edgedet_address_map.h.
assign_bd_address [get_bd_addr_segs $ps/S_AXI_HP0/HP0_DDR_LOWOCM]

validate_bd_design
save_bd_design
