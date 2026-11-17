set expected_part xc7z020clg484-1
set part_matches [get_parts -quiet $expected_part]
puts "EDZ_PART_COUNT=[llength $part_matches]"

create_project -in_memory -part $expected_part edz_catalog_probe
update_ip_catalog -rebuild

set required_patterns [list \
    "*processing_system7*" \
    "*axi_dma*" \
    "*proc_sys_reset*" \
    "*xlconcat*" \
    "*smartconnect*"]
set missing 0
foreach pattern $required_patterns {
    set matches [get_ipdefs -all -quiet $pattern]
    puts "EDZ_IP_PATTERN=$pattern COUNT=[llength $matches]"
    if {[llength $matches] == 0} { incr missing }
}

if {[llength $part_matches] != 1 || $missing != 0} {
    puts "EDZ_VIVADO_CATALOG_PROBE_FAILED"
    exit 2
}
puts "EDZ_VIVADO_CATALOG_PROBE_OK"
close_project
exit 0
