# ============================================================
# run_hls.tcl
# Vitis HLS Build Script for CNN Accelerator
# 
# Usage: vitis_hls -f run_hls.tcl
# ============================================================

# Project settings
set PROJECT_NAME "cnn_accel"
set TOP_FUNCTION "cnn_top"
set PART         "xc7z020clg484-1"   ;# ZedBoard Zynq part
set CLOCK_PERIOD 10                   ;# 100 MHz (10ns period)

# Create project
open_project ${PROJECT_NAME}
set_top ${TOP_FUNCTION}

# Add source files
add_files src/cnn_types.h
add_files src/conv2d.cpp
add_files src/maxpool.cpp
add_files src/fc_layer.cpp
add_files src/cnn_top.cpp

# Add testbench
add_files -tb tb/test_cnn.cpp

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
# Step 3: Co-Simulation (verify RTL matches C)
# Optional — uncomment to run (takes longer)
# ============================================================
# puts "=============================================="
# puts "  Running Co-Simulation..."
# puts "=============================================="
# cosim_design

# ============================================================
# Step 4: Export IP for Vivado
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
