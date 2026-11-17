[CmdletBinding()]
param(
    [string]$Vivado = "",
    [string]$IpRepository = "D:\fpga_build\edgedet_z20\ip_repo\accuracy_pe8_simd8",
    [string]$BuildRoot = "D:\fpga_build\edgedet_z20\platform_accuracy_pe8_simd8",
    [string]$Saif = "",
    [switch]$AllowUnhealthyVolume
)

$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
. (Join-Path $repository 'scripts\amd_toolchain.ps1')
$tcl = Join-Path (Split-Path -Parent $PSScriptRoot) "tcl\build_platform.tcl"
if (-not (Test-Path -LiteralPath $IpRepository -PathType Container)) {
    throw "HLS IP repository does not exist: $IpRepository"
}
$health = Get-EdzVolumeHealth -Path $BuildRoot
if (-not $health.Healthy -and -not $AllowUnhealthyVolume) {
    throw "Build volume $($health.Root) is not healthy: $($health.HealthStatus), $($health.OperationalStatus). Repair it or use -AllowUnhealthyVolume explicitly."
}
$tool = Resolve-EdzAmdTool -Name Vivado -ExplicitPath $Vivado
New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
$arguments = @("-mode", "batch", "-nojournal", "-nolog", "-source", $tcl,
    "-tclargs", $IpRepository, $BuildRoot)
if ($Saif) { $arguments += $Saif }
$amdEnvironment = Push-EdzAmdEnvironment -Tool $tool
try {
    & $tool.Path @arguments
    if ($LASTEXITCODE -ne 0) { throw "Vivado failed with exit code $LASTEXITCODE" }
} finally {
    Pop-EdzAmdEnvironment -Saved $amdEnvironment
}
