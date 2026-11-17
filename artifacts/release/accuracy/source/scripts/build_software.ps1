[CmdletBinding()]
param(
    [ValidateSet('accuracy', 'eco')][string]$Profile = 'accuracy',
    [string]$Xsct = '',
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
$tool = Resolve-EdzAmdTool -Name Xsct -ExplicitPath $Xsct
$xsa = Join-Path $buildRoot "vivado_$Profile\artifacts\edgedet_z20.xsa"
if (-not (Test-Path $xsa)) { throw "Missing XSA: $xsa" }
$runtimeHeader = Join-Path $repo "artifacts\work\$Profile\edz_model_runtime.h"
if (-not (Test-Path -LiteralPath $runtimeHeader -PathType Leaf)) {
    throw "Missing generated runtime model metadata: $runtimeHeader"
}
$amdEnvironment = Push-EdzAmdEnvironment -Tool $tool
try {
    python (Join-Path $repo 'platform\vitis\build_software.py') --xsa $xsa --workspace (Join-Path $buildRoot "vitis_$Profile") --repo $repo --xsct $tool.Path --runtime-header $runtimeHeader
    if ($LASTEXITCODE -ne 0) { throw "Vitis software build failed with exit code $LASTEXITCODE" }
} finally {
    Pop-EdzAmdEnvironment -Saved $amdEnvironment
}
