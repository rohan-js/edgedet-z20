# ============================================================
# run_hls_build.tcl
# Vitis HLS Build Script — uses /tmp build dir to avoid spaces
# 
# Usage: cd /tmp/hls_build && vitis_hls -f <this_script>
# ============================================================

# Source directory (where the actual code lives)
set SRC_DIR "/media/rohanjs/HDD/UVM/PROJECTS/Real-Time Object Detection Using Hardware-Accelerated CNN on Xilinx Zynq FPGA with Arm Processor/hls"

# Project settings
set PROJECT_NAME "cnn_accel"
set TOP_FUNCTION "cnn_top"
set PART         "xc7z020clg484-1"   ;# ZedBoard Zynq part
set CLOCK_PERIOD 10                   ;# 100 MHz (10ns period)

# Create project (in current dir = /tmp/hls_build)
open_project ${PROJECT_NAME}
set_top ${TOP_FUNCTION}

# Add source files (using absolute paths)
add_files "${SRC_DIR}/src/cnn_types.h"
add_files "${SRC_DIR}/src/conv2d.cpp"
add_files "${SRC_DIR}/src/maxpool.cpp"
add_files "${SRC_DIR}/src/fc_layer.cpp"
add_files "${SRC_DIR}/src/cnn_top.cpp"

# Add testbench
add_files -tb "${SRC_DIR}/tb/test_cnn.cpp"

# Create solution
open_solution "solution1"
set_part ${PART}
create_clock -period ${CLOCK_PERIOD} -name default

# ============================================================
# Step 1: C Simulation (verify functional correctness)
# ============================================================
puts "=============================================="
puts "  Running C Simulation..."
puts "=============================================="
csim_design

# ============================================================
# Step 2: C Synthesis (generate RTL from C++)
# ============================================================
puts "=============================================="
puts "  Running C Synthesis..."
puts "=============================================="
csynth_design

# ============================================================
# Step 3: Export IP for Vivado
# ============================================================
puts "=============================================="
puts "  Exporting IP to Vivado..."
puts "=============================================="
export_design -format ip_catalog \
    -description "CNN Accelerator for ZedBoard" \
    -vendor "user" \
    -library "hls" \
    -version "1.0" \
    -display_name "CNN_Accelerator"

puts "=============================================="
puts "  HLS Flow Complete!"
puts "  IP exported to: ${PROJECT_NAME}/solution1/impl/ip"
puts "=============================================="

exit
