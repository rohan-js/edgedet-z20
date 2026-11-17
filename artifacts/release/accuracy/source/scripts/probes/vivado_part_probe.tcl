set part_name xc7z020clg484-1
set matches [get_parts -quiet $part_name]
puts "EDZ_PART_COUNT=[llength $matches]"
if {[llength $matches] != 1} { exit 2 }
create_project -force edz_part_probe C:/fpga_build/edgedet_z20/vivado_part_probe -part $part_name
puts "EDZ_VIVADO_PART_PROJECT_OK"
close_project
exit 0
