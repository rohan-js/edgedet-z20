param(
    [string]$BuildDir = "D:\fpga_build\edgedet_z20\runtime-host",
    [string]$Generator = ""
)

$ErrorActionPreference = "Stop"
$RuntimeDir = Split-Path -Parent $PSScriptRoot

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program failed with exit code $LASTEXITCODE"
    }
}

$configure = @("-S", $RuntimeDir, "-B", $BuildDir, "-DBUILD_TESTING=ON")
if (-not $Generator) {
    if ((Get-Command cl -ErrorAction SilentlyContinue) -and
        (Get-Command nmake -ErrorAction SilentlyContinue)) {
        $Generator = "NMake Makefiles"
    } elseif (Get-Command mingw32-make -ErrorAction SilentlyContinue) {
        $Generator = "MinGW Makefiles"
    }
}
if ($Generator) { $configure += @("-G", $Generator) }
Invoke-Checked cmake $configure
Invoke-Checked cmake @("--build", $BuildDir)
Invoke-Checked ctest @("--test-dir", $BuildDir, "--output-on-failure")
