# Vitis HLS 2025.2 batch build for one EdgeDet folding candidate.
# Environment variables:
#   EDZ_VARIANT, EDZ_PROFILE, EDZ_PE, EDZ_SIMD, EDZ_BUILD_ROOT
#   EDZ_RUN_CSIM (default 1), EDZ_RUN_COSIM (default 0)
#   EDZ_ALLOW_PLACEHOLDER (must be 1 to synthesize checked-in placeholder)

proc env_or {name fallback} {
    if {[info exists ::env($name)] && $::env($name) ne ""} {
        return $::env($name)
    }
    return $fallback
}

set script_dir [file dirname [file normalize [info script]]]
set accelerator_dir [file normalize [file join $script_dir ..]]
set variant [env_or EDZ_VARIANT "accuracy_pe8_simd8"]
set profile [env_or EDZ_PROFILE "accuracy"]
set pe [env_or EDZ_PE "8"]
set simd [env_or EDZ_SIMD "8"]
set build_root [file normalize [env_or EDZ_BUILD_ROOT [file join $accelerator_dir build]]]
set run_csim [env_or EDZ_RUN_CSIM "1"]
set run_cosim [env_or EDZ_RUN_COSIM "0"]
set allow_placeholder [env_or EDZ_ALLOW_PLACEHOLDER "0"]
set generated_include [env_or EDZ_GENERATED_INCLUDE_DIR ""]

if {$profile ni {accuracy eco}} {
    error "EDZ_PROFILE must be accuracy or eco"
}
if {$pe ni {4 8} || $simd ni {8 16}} {
    error "Supported folding candidates are PE={4,8}, SIMD={8,16}"
}

set project_dir [file join $build_root hls $variant]
set export_dir [file join $build_root exports]
file mkdir $project_dir
file mkdir $export_dir

set cflags "-std=c++14"
if {$generated_include ne ""} {
    set generated_include [file normalize $generated_include]
    if {![file exists [file join $generated_include generated_model.hpp]]} {
        error "EDZ_GENERATED_INCLUDE_DIR lacks generated_model.hpp: $generated_include"
    }
    append cflags " -I$generated_include -DEDZ_MODEL_WEIGHTS_PRESENT=1"
}
append cflags " -I$accelerator_dir/include -I$accelerator_dir/src -DEDZ_PE=$pe -DEDZ_SIMD=$simd"
if {$profile eq "accuracy"} {
    append cflags " -DEDZ_PROFILE_ACCURACY=1"
} else {
    append cflags " -DEDZ_PROFILE_ECO=1"
}

open_project -reset $project_dir
set_top edgedet_top
add_files [file join $accelerator_dir src edgedet_top.cpp] -cflags $cflags
add_files [file join $accelerator_dir src preprocess.cpp] -cflags $cflags
add_files [file join $accelerator_dir src detector.cpp] -cflags $cflags
add_files [file join $accelerator_dir src detector_full.cpp] -cflags $cflags
add_files -tb [file join $accelerator_dir tb test_edgedet.cpp] -cflags $cflags

open_solution -reset solution -flow_target vivado

# Interface-only C simulation does not need a device database. Keep this path
# ahead of set_part so host verification can still run when device support is
# being repaired. Synthesis/IP export remain forbidden without generated model
# parameters unless EDZ_ALLOW_PLACEHOLDER=1 is explicitly set.
if {$generated_include eq "" && $allow_placeholder ne "1"} {
    if {$run_csim eq "1"} {
        csim_design -clean
    }
    puts "INFO: C simulation completed. Synthesis intentionally stopped because generated model weights are absent."
    puts "INFO: Set EDZ_ALLOW_PLACEHOLDER=1 only for interface/platform bring-up."
    close_project
    exit 0
}

set_part {xc7z020clg484-1}
create_clock -period 10.000 -name default
config_compile -name_max_length 80
config_interface -m_axi_addr64=false

if {$run_csim eq "1"} {
    csim_design -clean
}

csynth_design
if {$run_cosim eq "1"} {
    cosim_design -rtl verilog -tool xsim -trace_level port
}

set ip_zip [file join $export_dir "edgedet_top_${variant}.zip"]
if {$generated_include eq ""} {
    set display_name "EdgeDet-Z20 $variant (PLACEHOLDER)"
    set description "EdgeDet stream and detector scaffold; not trained"
} else {
    set display_name "EdgeDet-Z20 $variant"
    set description "Generated quantized EdgeDet-Z20 detector"
}
export_design -format ip_catalog -rtl verilog -vendor edgedet-z20.org \
    -library hls -version 1.0 -display_name $display_name \
    -description $description -output $ip_zip
puts "INFO: Exported $ip_zip"
close_project
