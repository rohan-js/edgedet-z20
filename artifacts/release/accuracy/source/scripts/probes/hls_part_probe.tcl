set project_dir C:/fpga_build/edgedet_z20/hls_part_probe
open_project -reset $project_dir
open_solution -reset solution -flow_target vivado
set_part xc7z020clg484-1
puts "EDZ_HLS_ZYNQ_PART_OK"
close_project
exit 0
