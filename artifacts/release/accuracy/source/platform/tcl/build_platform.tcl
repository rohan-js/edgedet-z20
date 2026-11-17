# Usage:
# vivado -mode batch -source build_platform.tcl -tclargs <ip_repo> <build_root> ?saif?

set script_dir [file dirname [file normalize [info script]]]
set platform_dir [file normalize [file join $script_dir ..]]
set EDZ_IP_REPO [file normalize [lindex $argv 0]]
set build_root [file normalize [lindex $argv 1]]
set saif_file ""
if {[llength $argv] >= 3 && [lindex $argv 2] ne ""} {
    set saif_file [file normalize [lindex $argv 2]]
}
if {![file isdirectory $EDZ_IP_REPO]} { error "IP repository not found: $EDZ_IP_REPO" }

source [file join $platform_dir config address_map.tcl]
set project_dir [file join $build_root vivado]
set artifact_dir [file join $build_root artifacts]
set report_dir [file join $build_root reports]
file mkdir $project_dir
file mkdir $artifact_dir
file mkdir $report_dir

create_project -force edgedet_z20 $project_dir -part xc7z020clg484-1
set board_parts [lsort -dictionary [get_board_parts -quiet *zedboard*]]
if {[llength $board_parts] == 0} {
    error "Digilent ZedBoard board files are required for the correct PS7 DDR/MIO preset"
}
set selected_board [lindex $board_parts end]
set_property board_part $selected_board [current_project]
puts "INFO: Using board preset $selected_board"

set_property ip_repo_paths [list $EDZ_IP_REPO] [current_project]
update_ip_catalog
source [file join $script_dir create_block_design.tcl]

set bd_file [get_files edgedet_system.bd]
set_property synth_checkpoint_mode None $bd_file
generate_target all $bd_file
make_wrapper -files $bd_file -top
set wrapper [file join $project_dir edgedet_z20.gen sources_1 bd edgedet_system hdl edgedet_system_wrapper.v]
if {![file exists $wrapper]} { error "Generated wrapper was not found: $wrapper" }
add_files -norecurse $wrapper
set_property top edgedet_system_wrapper [current_fileset]
update_compile_order -fileset sources_1

launch_runs synth_1 -jobs 1
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
    error "Synthesis did not complete: [get_property STATUS [get_runs synth_1]]"
}
launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "Implementation did not complete: [get_property STATUS [get_runs impl_1]]"
}

open_run impl_1
report_timing_summary -delay_type min_max -max_paths 10 -report_unconstrained \
    -check_timing_verbose -file [file join $report_dir timing_summary.rpt]
report_utilization -hierarchical -file [file join $report_dir utilization_hierarchical.rpt]
report_clock_interaction -file [file join $report_dir clock_interaction.rpt]
report_drc -file [file join $report_dir drc.rpt]
report_methodology -file [file join $report_dir methodology.rpt]

if {$saif_file ne "" && [file exists $saif_file]} {
    read_saif $saif_file
    report_power -file [file join $report_dir power_saif_estimate.rpt]
    puts "WARNING: Power is a post-route estimate based on supplied SAIF, not a board measurement."
} else {
    report_power -file [file join $report_dir power_vectorless_low_confidence.rpt]
    puts "WARNING: No SAIF supplied. Vectorless power report is low-confidence and not a board measurement."
}

write_hw_platform -fixed -include_bit -force \
    -file [file join $artifact_dir edgedet_z20.xsa]
set run_dir [get_property DIRECTORY [get_runs impl_1]]
set bitstream [file join $run_dir edgedet_system_wrapper.bit]
if {![file exists $bitstream]} { error "Bitstream was not produced: $bitstream" }
file copy -force $bitstream [file join $artifact_dir edgedet_z20.bit]
write_checkpoint -force [file join $artifact_dir edgedet_z20_post_route.dcp]
puts "INFO: Hardware artifacts are in $artifact_dir"
