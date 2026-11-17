[CmdletBinding()]
param(
    [ValidateSet('accuracy', 'eco')][string]$Profile = 'accuracy',
    [string]$Vivado = '',
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
$tool = Resolve-EdzAmdTool -Name Vivado -ExplicitPath $Vivado
$stage = Join-Path $buildRoot "vivado_$Profile"
New-Item -ItemType Directory -Force $stage | Out-Null
$amdEnvironment = Push-EdzAmdEnvironment -Tool $tool
try {
    & $tool.Path -mode batch -notrace -source (Join-Path $repo 'platform\vivado\create_system.tcl') -tclargs $repo $stage $Profile
    if ($LASTEXITCODE -ne 0) { throw "Vivado failed with exit code $LASTEXITCODE" }
} finally {
    Pop-EdzAmdEnvironment -Saved $amdEnvironment
}
