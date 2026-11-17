# ============================================================
# create_block_design.tcl
# Vivado Block Design Script for ZedBoard CNN Accelerator
#
# Creates: Zynq PS + CNN HLS IP + AXI Interconnect
# Generates bitstream and exports XSA for Vitis SDK
#
# Usage:
#   vivado -mode batch -source create_block_design.tcl
# ============================================================

# ---- Project Settings ----
set PROJECT_NAME  "zedboard_cnn"
set PROJECT_DIR   "/tmp/vivado_build/vivado_project"
set PART          "xc7z020clg484-1"

# HLS IP is in the project's hls_output directory
set SCRIPT_DIR    [file dirname [info script]]
set HLS_IP_DIR    [file normalize "${SCRIPT_DIR}/../hls/hls_output/ip"]

puts "=============================================="
puts "  ZedBoard CNN Accelerator - Vivado Build"
puts "  Part: ${PART}"
puts "  HLS IP: ${HLS_IP_DIR}"
puts "=============================================="

# ============================================================
# Step 1: Create Vivado Project
# ============================================================
file mkdir ${PROJECT_DIR}
create_project ${PROJECT_NAME} ${PROJECT_DIR} -part ${PART} -force

# Add HLS IP repository
set_property ip_repo_paths [list ${HLS_IP_DIR}] [current_project]
update_ip_catalog

# ============================================================
# Step 2: Create Block Design
# ============================================================
create_bd_design "cnn_system"

# ---- Add Zynq Processing System ----
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7

# Configure Zynq PS for ZedBoard
# Based on ZedBoard HW User Guide:
#   - DDR3: MT41K128M16JT-125 (2x16 = 32-bit, 512 MB)
#   - PS clock: 33.333 MHz
#   - UART1 on MIO48/49
#   - SD0 on MIO40-47
#   - USB0 on MIO28-39
#   - Ethernet on MIO16-27
#   - FCLK_CLK0: 100 MHz for PL
set_property -dict [list \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_USE_S_AXI_HP0 {1} \
    CONFIG.PCW_USE_FABRIC_INTERRUPT {1} \
    CONFIG.PCW_IRQ_F2P_INTR {1} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
    CONFIG.PCW_PRESET_BANK1_VOLTAGE {LVCMOS 1.8V} \
    CONFIG.PCW_CRYSTAL_PERIPHERAL_FREQMHZ {33.333333} \
    CONFIG.PCW_UIPARAM_DDR_PARTNO {MT41K128M16JT-125} \
    CONFIG.PCW_UIPARAM_DDR_FREQ_MHZ {533.333313} \
    CONFIG.PCW_UART1_PERIPHERAL_ENABLE {1} \
    CONFIG.PCW_UART1_UART1_IO {MIO 48 .. 49} \
    CONFIG.PCW_SD0_PERIPHERAL_ENABLE {1} \
    CONFIG.PCW_SD0_SD0_IO {MIO 40 .. 45} \
    CONFIG.PCW_USB0_PERIPHERAL_ENABLE {1} \
    CONFIG.PCW_ENET0_PERIPHERAL_ENABLE {1} \
    CONFIG.PCW_ENET0_ENET0_IO {MIO 16 .. 27} \
    CONFIG.PCW_ENET0_GRP_MDIO_ENABLE {1} \
    CONFIG.PCW_ENET0_GRP_MDIO_IO {MIO 52 .. 53} \
    CONFIG.PCW_QSPI_PERIPHERAL_ENABLE {1} \
    CONFIG.PCW_TTC0_PERIPHERAL_ENABLE {1} \
] [get_bd_cells ps7]

# ---- Add CNN Accelerator (HLS IP) ----
create_bd_cell -type ip -vlnv user:hls:cnn_top:1.0 cnn_accel

# ---- Add AXI Interconnect for Control (GP0) ----
# PS GP0 Master → Interconnect → HLS s_axi_control
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_gp_ic
set_property -dict [list CONFIG.NUM_MI {1}] [get_bd_cells axi_gp_ic]

# ---- Add AXI Interconnect for Data (HP0) ----
# HLS m_axi gmem0-3 → Interconnect → PS HP0 Slave (DDR access)
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_hp_ic
set_property -dict [list CONFIG.NUM_SI {4} CONFIG.NUM_MI {1}] [get_bd_cells axi_hp_ic]

# ---- Add Processor System Reset ----
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 sys_reset

# ============================================================
# Step 3: Connect Clocks and Resets
# ============================================================

# PS FCLK_CLK0 (100 MHz) drives everything
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] \
    [get_bd_pins sys_reset/slowest_sync_clk] \
    [get_bd_pins cnn_accel/ap_clk] \
    [get_bd_pins axi_gp_ic/ACLK] \
    [get_bd_pins axi_gp_ic/M00_ACLK] \
    [get_bd_pins axi_gp_ic/S00_ACLK] \
    [get_bd_pins axi_hp_ic/ACLK] \
    [get_bd_pins axi_hp_ic/M00_ACLK] \
    [get_bd_pins axi_hp_ic/S00_ACLK] \
    [get_bd_pins axi_hp_ic/S01_ACLK] \
    [get_bd_pins axi_hp_ic/S02_ACLK] \
    [get_bd_pins axi_hp_ic/S03_ACLK] \
    [get_bd_pins ps7/M_AXI_GP0_ACLK] \
    [get_bd_pins ps7/S_AXI_HP0_ACLK]

# Reset from PS
connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] \
    [get_bd_pins sys_reset/ext_reset_in]

connect_bd_net [get_bd_pins sys_reset/peripheral_aresetn] \
    [get_bd_pins cnn_accel/ap_rst_n] \
    [get_bd_pins axi_gp_ic/ARESETN] \
    [get_bd_pins axi_gp_ic/M00_ARESETN] \
    [get_bd_pins axi_gp_ic/S00_ARESETN] \
    [get_bd_pins axi_hp_ic/ARESETN] \
    [get_bd_pins axi_hp_ic/M00_ARESETN] \
    [get_bd_pins axi_hp_ic/S00_ARESETN] \
    [get_bd_pins axi_hp_ic/S01_ARESETN] \
    [get_bd_pins axi_hp_ic/S02_ARESETN] \
    [get_bd_pins axi_hp_ic/S03_ARESETN]

# ============================================================
# Step 4: Connect AXI Interfaces
# ============================================================

# Control path: PS GP0 → Interconnect → HLS s_axi_control
connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP0] \
    [get_bd_intf_pins axi_gp_ic/S00_AXI]

connect_bd_intf_net [get_bd_intf_pins axi_gp_ic/M00_AXI] \
    [get_bd_intf_pins cnn_accel/s_axi_control]

# Data path: HLS m_axi (gmem0-3) → Interconnect → PS HP0
connect_bd_intf_net [get_bd_intf_pins cnn_accel/m_axi_gmem0] \
    [get_bd_intf_pins axi_hp_ic/S00_AXI]

connect_bd_intf_net [get_bd_intf_pins cnn_accel/m_axi_gmem1] \
    [get_bd_intf_pins axi_hp_ic/S01_AXI]

connect_bd_intf_net [get_bd_intf_pins cnn_accel/m_axi_gmem2] \
    [get_bd_intf_pins axi_hp_ic/S02_AXI]

connect_bd_intf_net [get_bd_intf_pins cnn_accel/m_axi_gmem3] \
    [get_bd_intf_pins axi_hp_ic/S03_AXI]

connect_bd_intf_net [get_bd_intf_pins axi_hp_ic/M00_AXI] \
    [get_bd_intf_pins ps7/S_AXI_HP0]

# Connect interrupt
connect_bd_net [get_bd_pins cnn_accel/interrupt] \
    [get_bd_pins ps7/IRQ_F2P]

# ============================================================
# Step 5: Connect DDR and FIXED_IO external ports
# ============================================================
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR"} [get_bd_cells ps7]

# ============================================================
# Step 6: Assign Addresses
# ============================================================
assign_bd_address

# ============================================================
# Step 7: Validate and Save
# ============================================================
validate_bd_design
save_bd_design

# ============================================================
# Step 8: Generate Output Products
# ============================================================
# Disable OOC per-IP synthesis to save RAM (Global Synthesis)
set_property synth_checkpoint_mode None [get_files cnn_system.bd]
generate_target all [get_files cnn_system.bd]

# Create HDL wrapper (Vivado 2025.2 puts it in .gen/, not .srcs/)
make_wrapper -files [get_files cnn_system.bd] -top
add_files -norecurse ${PROJECT_DIR}/${PROJECT_NAME}.gen/sources_1/bd/cnn_system/hdl/cnn_system_wrapper.v

# ============================================================
# Step 9: Run Synthesis
# ============================================================
puts "=============================================="
puts "  Running Synthesis (Global, 1 Job)..."
puts "=============================================="
launch_runs synth_1 -jobs 1
wait_on_run synth_1

if {[get_property STATUS [get_runs synth_1]] != "synth_design Complete!"} {
    puts "ERROR: Synthesis failed!"
    exit 1
}

# ============================================================
# Step 10: Run Implementation + Bitstream
# ============================================================
puts "=============================================="
puts "  Running Implementation (1 Job)..."
puts "=============================================="
launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1

if {[get_property STATUS [get_runs impl_1]] != "write_bitstream Complete!"} {
    puts "ERROR: Implementation failed!"
    exit 1
}

# ============================================================
# Step 11: Export Hardware for Vitis SDK
# ============================================================
puts "=============================================="
puts "  Exporting Hardware (XSA)..."
puts "=============================================="
write_hw_platform -fixed -include_bit \
    -file ${PROJECT_DIR}/cnn_system_wrapper.xsa

puts "=============================================="
puts "  Vivado Flow Complete!"
puts "  Bitstream: ${PROJECT_DIR}/${PROJECT_NAME}.runs/impl_1/cnn_system_wrapper.bit"
puts "  Hardware:  ${PROJECT_DIR}/cnn_system_wrapper.xsa"
puts "=============================================="
