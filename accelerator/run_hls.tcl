# Compatibility entrypoint used by repository-level build wrappers.
# Accepted Tcl args: <accuracy|eco> <PE> <SIMD>.
if {[llength $argv] >= 3 &&
    [lindex $argv 0] in {accuracy eco} &&
    [lindex $argv 1] in {4 8} &&
    [lindex $argv 2] in {8 16}} {
    set ::env(EDZ_PROFILE) [lindex $argv 0]
    set ::env(EDZ_PE) [lindex $argv 1]
    set ::env(EDZ_SIMD) [lindex $argv 2]
    set ::env(EDZ_VARIANT) "[lindex $argv 0]_pe[lindex $argv 1]_simd[lindex $argv 2]"
}
source [file join [file dirname [file normalize [info script]]] scripts build_hls.tcl]
