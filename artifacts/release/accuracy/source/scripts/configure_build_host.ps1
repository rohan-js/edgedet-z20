[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$ApplyPageFile,
    [string]$BuildRoot = 'D:\fpga_build\edgedet_z20'
)

$ErrorActionPreference = 'Stop'
Write-Host 'Current page-file configuration:'
Get-CimInstance Win32_PageFileSetting -ErrorAction SilentlyContinue |
    Select-Object Name, InitialSize, MaximumSize | Format-Table -AutoSize

$drive = Split-Path -Qualifier $BuildRoot
$driveInfo = Get-PSDrive ($drive.TrimEnd(':'))
if ($driveInfo.Free -lt 80GB) {
    throw "$drive has less than 80 GB free; choose another build root."
}
New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
Write-Host "Build root ready: $BuildRoot"

if ($ApplyPageFile) {
    $pageFile = 'D:\pagefile.sys'
    if ($PSCmdlet.ShouldProcess($pageFile, 'Configure a 32 GB fixed page file; reboot required')) {
        $system = Get-CimInstance Win32_ComputerSystem
        Set-CimInstance -InputObject $system -Property @{ AutomaticManagedPagefile = $false } | Out-Null
        Get-CimInstance Win32_PageFileSetting -ErrorAction SilentlyContinue | Remove-CimInstance
        New-CimInstance -ClassName Win32_PageFileSetting -Property @{
            Name = $pageFile
            InitialSize = 32768
            MaximumSize = 32768
        } | Out-Null
        Write-Warning 'Page-file configuration changed. Reboot Windows before running Vivado.'
    }
} else {
    Write-Host 'Page file was not changed. Re-run as Administrator with -ApplyPageFile after reviewing -WhatIf.'
}
