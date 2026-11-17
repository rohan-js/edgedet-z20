# Compatibility entrypoint for scripts/build_vivado.ps1.
# Args: <repository_root> <platform_build_root> <accuracy|eco>
set repository_root [file normalize [lindex $argv 0]]
set platform_build_root [file normalize [lindex $argv 1]]
set profile [lindex $argv 2]

if {[info exists ::env(EDZ20_HLS_IP_REPO)] && $::env(EDZ20_HLS_IP_REPO) ne ""} {
    set ip_repo [file normalize $::env(EDZ20_HLS_IP_REPO)]
} else {
    set global_build_root "D:/fpga_build/edgedet_z20"
    if {[info exists ::env(EDZ20_BUILD_ROOT)] && $::env(EDZ20_BUILD_ROOT) ne ""} {
        set global_build_root [file normalize $::env(EDZ20_BUILD_ROOT)]
    }
    set ip_repo [file join $global_build_root ip_repo "${profile}_pe8_simd8"]
}
if {![file isdirectory $ip_repo]} {
    error "Expanded HLS IP repo not found at $ip_repo. Set EDZ20_HLS_IP_REPO to the directory containing component.xml."
}

set argv [list $ip_repo $platform_build_root]
source [file join $repository_root platform tcl build_platform.tcl]
