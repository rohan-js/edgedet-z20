[CmdletBinding()]
param(
    [ValidateSet('accuracy', 'eco')][string]$Profile = 'accuracy',
    [ValidateSet(4, 8)][int]$PE = 8,
    [ValidateSet(8, 16)][int]$SIMD = 8,
    [string]$VitisHls = '',
    [string]$GeneratedHeader = '',
    [switch]$RunCosim,
    [switch]$AllowPlaceholder,
    [switch]$AllowUnhealthyVolume
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'amd_toolchain.ps1')
$buildRoot = if ($env:EDZ20_BUILD_ROOT) { $env:EDZ20_BUILD_ROOT } else { 'D:\fpga_build\edgedet_z20' }
$health = Get-EdzVolumeHealth -Path $buildRoot
if (-not $health.Healthy -and -not $AllowUnhealthyVolume) {
    throw "Build volume $($health.Root) is not healthy: $($health.HealthStatus), $($health.OperationalStatus). Repair it or use -AllowUnhealthyVolume explicitly."
}
$tool = Resolve-EdzAmdTool -Name Hls -ExplicitPath $VitisHls
$stage = Join-Path $buildRoot "hls_$($Profile)_pe$($PE)_simd$($SIMD)"
$variant = "${Profile}_pe${PE}_simd${SIMD}"
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item -Recurse -Force (Join-Path $repo 'accelerator\*') $stage
$defaultHeader = Join-Path $repo "artifacts\work\$Profile\generated_model.hpp"
if (-not $GeneratedHeader -and (Test-Path -LiteralPath $defaultHeader -PathType Leaf)) {
    $GeneratedHeader = $defaultHeader
}
$generatedInclude = ''
if ($GeneratedHeader) {
    if (-not (Test-Path -LiteralPath $GeneratedHeader -PathType Leaf)) {
        throw "Generated model header does not exist: $GeneratedHeader"
    }
    $generatedInclude = Join-Path $stage 'generated'
    New-Item -ItemType Directory -Force $generatedInclude | Out-Null
    Copy-Item -LiteralPath $GeneratedHeader -Destination (Join-Path $generatedInclude 'generated_model.hpp') -Force
} elseif (-not $AllowPlaceholder) {
    Write-Warning 'No generated model header was found. The flow will run C simulation only and intentionally skip synthesis.'
}

$saved = @{}
foreach ($name in 'EDZ_BUILD_ROOT','EDZ_GENERATED_INCLUDE_DIR','EDZ_RUN_CSIM','EDZ_RUN_COSIM','EDZ_ALLOW_PLACEHOLDER','EDZ_PROFILE','EDZ_PE','EDZ_SIMD','EDZ_VARIANT') {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$env:EDZ_BUILD_ROOT = Join-Path $stage 'build'
$env:EDZ_GENERATED_INCLUDE_DIR = $generatedInclude
$env:EDZ_RUN_CSIM = '1'
$env:EDZ_RUN_COSIM = if ($RunCosim) { '1' } else { '0' }
$env:EDZ_ALLOW_PLACEHOLDER = if ($AllowPlaceholder) { '1' } else { '0' }
$env:EDZ_PROFILE = $Profile
$env:EDZ_PE = [string]$PE
$env:EDZ_SIMD = [string]$SIMD
$env:EDZ_VARIANT = $variant
$amdEnvironment = Push-EdzAmdEnvironment -Tool $tool
Push-Location $stage
try {
    if ($tool.Flavor -eq 'vitis-run') {
        & $tool.Path --mode hls --tcl run_hls.tcl
    } else {
        & $tool.Path -f run_hls.tcl -tclargs $Profile $PE $SIMD
    }
    if ($LASTEXITCODE -ne 0) { throw "HLS failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
    Pop-EdzAmdEnvironment -Saved $amdEnvironment
    foreach ($name in $saved.Keys) {
        [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process')
    }
}

$ipZip = Join-Path $stage "build\exports\edgedet_top_${variant}.zip"
if (Test-Path -LiteralPath $ipZip -PathType Leaf) {
    $ipRepo = Join-Path $buildRoot "ip_repo\$variant"
    New-Item -ItemType Directory -Force $ipRepo | Out-Null
    Expand-Archive -LiteralPath $ipZip -DestinationPath $ipRepo -Force
    Write-Host "Expanded HLS IP repository: $ipRepo"
} else {
    Write-Host 'No IP archive was produced (expected for simulation-only placeholder runs).'
}
