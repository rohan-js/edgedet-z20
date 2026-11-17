[CmdletBinding()]
param(
    [string]$VitisHls = "",
    [string]$BuildRoot = "D:\fpga_build\edgedet_z20",
    [string]$GeneratedRoot = "",
    [ValidateSet("accuracy", "eco", "all")]
    [string]$Profile = "all",
    [switch]$RunCosim,
    [switch]$AllowPlaceholder,
    [switch]$AllowUnhealthyVolume
)

$ErrorActionPreference = "Stop"
$accelerator = Split-Path -Parent $PSScriptRoot
$repository = Split-Path -Parent $accelerator
$buildScript = Join-Path $repository "scripts\build_hls.ps1"
$variants = @(
    @{ Name = "accuracy_pe4_simd8"; Profile = "accuracy"; PE = 4; SIMD = 8 },
    @{ Name = "accuracy_pe8_simd8"; Profile = "accuracy"; PE = 8; SIMD = 8 },
    @{ Name = "accuracy_pe8_simd16"; Profile = "accuracy"; PE = 8; SIMD = 16 },
    @{ Name = "eco_pe4_simd8"; Profile = "eco"; PE = 4; SIMD = 8 },
    @{ Name = "eco_pe8_simd8"; Profile = "eco"; PE = 8; SIMD = 8 },
    @{ Name = "eco_pe8_simd16"; Profile = "eco"; PE = 8; SIMD = 16 }
)

foreach ($variant in $variants) {
    if ($Profile -ne "all" -and $variant.Profile -ne $Profile) { continue }
    Write-Host "Building $($variant.Name)"
    $arguments = @{
        Profile = $variant.Profile
        PE = $variant.PE
        SIMD = $variant.SIMD
        VitisHls = $VitisHls
    }
    if ($RunCosim) { $arguments.RunCosim = $true }
    if ($AllowPlaceholder) { $arguments.AllowPlaceholder = $true }
    if ($AllowUnhealthyVolume) { $arguments.AllowUnhealthyVolume = $true }
    if ($GeneratedRoot) {
        $arguments.GeneratedHeader = Join-Path $GeneratedRoot "$($variant.Profile)\generated_model.hpp"
    }
    $previousBuildRoot = $env:EDZ20_BUILD_ROOT
    $env:EDZ20_BUILD_ROOT = $BuildRoot
    try { & $buildScript @arguments }
    finally { $env:EDZ20_BUILD_ROOT = $previousBuildRoot }
}
