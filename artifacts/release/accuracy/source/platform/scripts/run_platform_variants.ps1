[CmdletBinding()]
param(
    [string]$Vivado = '',
    [string]$BuildRoot = 'D:\fpga_build\edgedet_z20',
    [ValidateSet('accuracy', 'eco', 'all')][string]$Profile = 'all',
    [string]$Saif = '',
    [switch]$AllowUnhealthyVolume
)

$ErrorActionPreference = 'Stop'
$variants = @(
    'accuracy_pe4_simd8', 'accuracy_pe8_simd8', 'accuracy_pe8_simd16',
    'eco_pe4_simd8', 'eco_pe8_simd8', 'eco_pe8_simd16'
)
$builder = Join-Path $PSScriptRoot 'build_platform.ps1'
foreach ($variant in $variants) {
    if ($Profile -ne 'all' -and -not $variant.StartsWith("${Profile}_")) { continue }
    $ipRepository = Join-Path $BuildRoot "ip_repo\$variant"
    if (-not (Test-Path -LiteralPath $ipRepository -PathType Container)) {
        Write-Warning "Skipping $variant; HLS IP repository is missing: $ipRepository"
        continue
    }
    $arguments = @{
        Vivado = $Vivado
        IpRepository = $ipRepository
        BuildRoot = (Join-Path $BuildRoot "platform_$variant")
    }
    if ($Saif) { $arguments.Saif = $Saif }
    if ($AllowUnhealthyVolume) { $arguments.AllowUnhealthyVolume = $true }
    & $builder @arguments
}
