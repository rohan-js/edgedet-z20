[CmdletBinding()]
param([switch]$FullSoak)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "pytest failed with exit code $LASTEXITCODE" }
    python -m compileall -q model client verification benchmarks scripts
    if ($LASTEXITCODE -ne 0) { throw "compileall failed with exit code $LASTEXITCODE" }
    & (Join-Path $repo 'runtime\tests\build_and_test.ps1')
    $frames = if ($FullSoak) { 10000 } else { 100 }
    $report = if ($FullSoak) {
        'artifacts\work\verification\virtual_board_soak.json'
    } else {
        'artifacts\work\verification\virtual_board_smoke.json'
    }
    python -m verification.soak_virtual_board --frames $frames --fragment-size 7 --output $report
    if ($LASTEXITCODE -ne 0) { throw "virtual-board soak failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}
