[CmdletBinding()]
param(
    [string]$Version = '2025.2',
    [string]$OutputPath = '',
    [switch]$FailOnError
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'amd_toolchain.ps1')

$repo = Split-Path -Parent $PSScriptRoot
$buildRoot = if ($env:EDZ20_BUILD_ROOT) { $env:EDZ20_BUILD_ROOT } else { 'D:\fpga_build\edgedet_z20' }
if (-not $OutputPath) { $OutputPath = Join-Path $repo 'artifacts\work\toolchain_preflight.json' }
$checks = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param([string]$Name, [bool]$Passed, [string]$Detail)
    $checks.Add([ordered]@{ name = $Name; passed = $Passed; detail = $Detail })
    $prefix = if ($Passed) { '[OK]' } else { '[FAIL]' }
    Write-Host "$prefix $Name - $Detail"
}

try {
    $layout = Get-EdzAmdLayout -Version $Version
    Add-Check 'AMD layout' $true "$($layout.Layout): $($layout.BaseRoot)"
} catch {
    Add-Check 'AMD layout' $false $_.Exception.Message
    $layout = $null
}

foreach ($pathCheck in @(
    @{ Name = 'Repository volume'; Path = $repo },
    @{ Name = 'Build volume'; Path = $buildRoot },
    @{ Name = 'AMD installation volume'; Path = if ($layout) { $layout.BaseRoot } else { $repo } }
)) {
    $health = Get-EdzVolumeHealth -Path $pathCheck.Path
    Add-Check $pathCheck.Name $health.Healthy "$($health.Root) health=$($health.HealthStatus), status=$($health.OperationalStatus)"
}

foreach ($name in 'python', 'git') {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    Add-Check $name ([bool]$command) $(if ($command) { $command.Source } else { 'not on PATH' })
}

if ($layout) {
    foreach ($toolName in 'Vivado', 'Hls', 'Xsct', 'Vitis', 'Bootgen') {
        try {
            $tool = Resolve-EdzAmdTool -Name $toolName -Version $Version
            Add-Check "$toolName executable" $true "$($tool.Path) (direct=$($tool.Direct), flavor=$($tool.Flavor))"
        } catch {
            Add-Check "$toolName executable" $false $_.Exception.Message
        }
    }

    try {
        $vivado = Resolve-EdzAmdTool -Name Vivado -Version $Version
        $saved = Push-EdzAmdEnvironment -Tool $vivado
        try {
            $text = (& $vivado.Path -version 2>&1 | Out-String).Trim()
            $launcherExit = $LASTEXITCODE
            $passed = ($text -match "Vivado v$([regex]::Escape($Version))")
            Add-Check 'Vivado version probe' $passed "$(($text -split "`r?`n" | Select-Object -First 1) -join ''); launcher_exit=$launcherExit"
        } finally { Pop-EdzAmdEnvironment -Saved $saved }
    } catch { Add-Check 'Vivado version probe' $false $_.Exception.Message }

    try {
        $xsct = Resolve-EdzAmdTool -Name Xsct -Version $Version
        $saved = Push-EdzAmdEnvironment -Tool $xsct
        try {
            $text = (& $xsct.Path -eval 'puts EDZ_XSCT_PROBE_OK; exit' 2>&1 | Out-String)
            Add-Check 'XSCT Tcl startup' ($LASTEXITCODE -eq 0 -and $text -match 'EDZ_XSCT_PROBE_OK') 'portable project-management Tcl initialized'
        } finally { Pop-EdzAmdEnvironment -Saved $saved }
    } catch { Add-Check 'XSCT Tcl startup' $false $_.Exception.Message }

    try {
        $hls = Resolve-EdzAmdTool -Name Hls -Version $Version
        $saved = Push-EdzAmdEnvironment -Tool $hls
        try {
            $probe = Join-Path $PSScriptRoot 'probes\amd_tcl_probe.tcl'
            if ($hls.Flavor -eq 'vitis-run') {
                $text = (& $hls.Path --mode hls --tcl $probe 2>&1 | Out-String)
            } else {
                $text = (& $hls.Path -f $probe 2>&1 | Out-String)
            }
            Add-Check 'Vitis HLS Tcl startup' ($LASTEXITCODE -eq 0 -and $text -match 'EDZ_AMD_TCL_PROBE_OK') 'HLS command and Tcl task package initialized'
        } finally { Pop-EdzAmdEnvironment -Saved $saved }
    } catch { Add-Check 'Vitis HLS Tcl startup' $false $_.Exception.Message }

    try {
        $hls = Resolve-EdzAmdTool -Name Hls -Version $Version
        $saved = Push-EdzAmdEnvironment -Tool $hls
        try {
            $probe = Join-Path $PSScriptRoot 'probes\hls_part_probe.tcl'
            if ($hls.Flavor -eq 'vitis-run') {
                $text = (& $hls.Path --mode hls --tcl $probe 2>&1 | Out-String)
            } else {
                $text = (& $hls.Path -f $probe 2>&1 | Out-String)
            }
            $passed = ($LASTEXITCODE -eq 0 -and $text -match 'EDZ_HLS_ZYNQ_PART_OK')
            $detail = if ($passed) { 'xc7z020clg484-1 device library initialized' } else { 'xc7z020clg484-1 is listed but its device library cannot initialize; repair Zynq-7000 device support' }
            Add-Check 'HLS Zynq-7020 device' $passed $detail
        } finally { Pop-EdzAmdEnvironment -Saved $saved }
    } catch { Add-Check 'HLS Zynq-7020 device' $false $_.Exception.Message }
}

$computer = Get-CimInstance Win32_ComputerSystem
$ramGB = [math]::Round($computer.TotalPhysicalMemory / 1GB, 1)
Add-Check 'Host RAM policy' ($ramGB -ge 7.5) "$ramGB GB usable RAM; builds remain limited to one job"

$failed = @($checks | Where-Object { -not $_.passed }).Count
$report = [ordered]@{
    schema = 'edgedet-z20-toolchain-preflight-v1'
    generated_utc = [DateTime]::UtcNow.ToString('o')
    amd_version = $Version
    build_root = $buildRoot
    ready = ($failed -eq 0)
    failed_checks = $failed
    checks = $checks
}
$parent = Split-Path -Parent $OutputPath
if ($parent) { New-Item -ItemType Directory -Force $parent | Out-Null }
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "Preflight report: $OutputPath"

if ($FailOnError -and $failed -gt 0) { throw "AMD toolchain preflight failed $failed check(s)." }
