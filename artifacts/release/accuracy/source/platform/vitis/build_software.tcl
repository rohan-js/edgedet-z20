# XSCT/Vitis 2025.2 standalone application build.
# Args: <xsa> <workspace> <staged_source_directory>

set xsa [file normalize [lindex $argv 0]]
set workspace [file normalize [lindex $argv 1]]
set sources [file normalize [lindex $argv 2]]
if {![file exists $xsa]} { error "XSA not found: $xsa" }
if {![file isdirectory $sources]} { error "staged sources not found: $sources" }

setws $workspace
app create -name edgedet_app -hw $xsa -proc ps7_cortexa9_0 -os standalone \
    -lang C -template {Empty Application(C)}
bsp setlib -name lwip211
platform generate
importsources -name edgedet_app -path $sources
app config -name edgedet_app define-compiler-symbols EDZ_XILINX_BAREMETAL
app config -name edgedet_app -add compiler-misc {-std=c99 -O2}
app build -name edgedet_app
puts "INFO: EdgeDet standalone application built in $workspace"
