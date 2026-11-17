Set-StrictMode -Version Latest

function Get-EdzAmdLayout {
    [CmdletBinding()]
    param([string]$Version = '2025.2')

    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($env:EDZ_AMD_ROOT) { $candidates.Add($env:EDZ_AMD_ROOT) }
    $candidates.Add("D:\Xilinx\$Version")
    $candidates.Add("C:\Xilinx\$Version")
    $candidates.Add("D:\AMD\$Version")
    $candidates.Add("C:\AMD\$Version")
    $candidates.Add('D:\Xilinx')
    $candidates.Add('C:\Xilinx')
    $candidates.Add('D:\AMD')
    $candidates.Add('C:\AMD')

    foreach ($candidate in $candidates | Select-Object -Unique) {
        $root = [System.IO.Path]::GetFullPath($candidate)
        $modularVivado = Join-Path $root 'Vivado'
        $modularVitis = Join-Path $root 'Vitis'
        if ((Test-Path (Join-Path $modularVivado 'bin\vivado.bat')) -and
            (Test-Path (Join-Path $modularVitis 'bin\vitis-run.bat'))) {
            return [pscustomobject]@{
                BaseRoot = $root
                VivadoRoot = $modularVivado
                VitisRoot = $modularVitis
                SharedTps = Join-Path $root 'tps'
                Layout = 'modular'
                Version = $Version
            }
        }

        $versionedVivado = Join-Path $root "Vivado\$Version"
        $versionedVitis = Join-Path $root "Vitis\$Version"
        if ((Test-Path (Join-Path $versionedVivado 'bin\vivado.bat')) -and
            (Test-Path (Join-Path $versionedVitis 'bin\vitis-run.bat'))) {
            return [pscustomobject]@{
                BaseRoot = $root
                VivadoRoot = $versionedVivado
                VitisRoot = $versionedVitis
                SharedTps = Join-Path $root 'SharedData\tps'
                Layout = 'versioned-products'
                Version = $Version
            }
        }
    }
    throw "AMD Vivado/Vitis $Version installation was not found. Set EDZ_AMD_ROOT to its parent directory."
}

function Initialize-EdzAmdShim {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]$Layout,
        [string]$ShimRoot = ''
    )
    if ($Layout.Layout -ne 'modular') { return $null }
    if (-not $ShimRoot) {
        $ShimRoot = if ($env:EDZ_AMD_SHIM_ROOT) { $env:EDZ_AMD_SHIM_ROOT } else { 'C:\fpga_build\edgedet_z20\amd_shim' }
    }
    New-Item -ItemType Directory -Force -Path $ShimRoot | Out-Null
    foreach ($product in 'Vitis', 'Vivado') {
        $sourceRoot = Join-Path $Layout.BaseRoot $product
        $shimProduct = Join-Path $ShimRoot $product
        New-Item -ItemType Directory -Force -Path $shimProduct | Out-Null
        foreach ($directory in Get-ChildItem -LiteralPath $sourceRoot -Directory) {
            if ($directory.Name -in @('data', 'tps', 'win64')) { continue }
            $link = Join-Path $shimProduct $directory.Name
            if (-not (Test-Path -LiteralPath $link)) {
                New-Item -ItemType Junction -Path $link -Target $directory.FullName | Out-Null
            }
        }
        foreach ($mapping in @(
            @{ Name = 'data'; Target = (Join-Path $Layout.BaseRoot 'data') },
            @{ Name = 'tps'; Target = $Layout.SharedTps },
            @{ Name = 'win64'; Target = (Join-Path $Layout.BaseRoot 'win64') }
        )) {
            $link = Join-Path $shimProduct $mapping.Name
            if (-not (Test-Path -LiteralPath $link)) {
                New-Item -ItemType Junction -Path $link -Target $mapping.Target | Out-Null
            }
        }
    }
    return [pscustomobject]@{
        Root = $ShimRoot
        VitisRoot = Join-Path $ShimRoot 'Vitis'
        VivadoRoot = Join-Path $ShimRoot 'Vivado'
    }
}

function Resolve-EdzAmdTool {
    [CmdletBinding()]
    param(
        [ValidateSet('Hls', 'Vivado', 'Xsct', 'Vitis', 'Bootgen')]
        [string]$Name,
        [string]$ExplicitPath = '',
        [string]$Version = '2025.2'
    )

    $layout = Get-EdzAmdLayout -Version $Version
    if ($ExplicitPath) {
        $explicit = Get-Command $ExplicitPath -ErrorAction SilentlyContinue
        if (-not $explicit) { throw "AMD tool does not exist: $ExplicitPath" }
        $leaf = [System.IO.Path]::GetFileNameWithoutExtension($explicit.Source).ToLowerInvariant()
        return [pscustomobject]@{
            Name = $Name; Path = $explicit.Source
            Flavor = if ($leaf -eq 'vitis-run') { 'vitis-run' } elseif ($leaf -eq 'vitis_hls') { 'vitis-hls' } else { $leaf }
            Direct = $false
            Layout = $layout; ProductRoot = if ($Name -eq 'Vivado' -or $Name -eq 'Bootgen') { $layout.VivadoRoot } else { $layout.VitisRoot }
        }
    }

    $shimRoot = if ($env:EDZ_AMD_SHIM_ROOT) { $env:EDZ_AMD_SHIM_ROOT } else { 'C:\fpga_build\edgedet_z20\amd_shim' }
    if ($layout.Layout -eq 'modular') {
        $null = Initialize-EdzAmdShim -Layout $layout -ShimRoot $shimRoot
        $shimProduct = if ($Name -eq 'Vivado' -or $Name -eq 'Bootgen') { 'Vivado' } else { 'Vitis' }
        $shimRelative = switch ($Name) {
            'Hls' { 'bin\vitis-run.bat' }
            'Vivado' { 'bin\vivado.bat' }
            'Xsct' { 'bin\xsct.bat' }
            'Vitis' { 'bin\vitis.bat' }
            'Bootgen' { 'bin\bootgen.bat' }
        }
        $shimLauncher = Join-Path (Join-Path $shimRoot $shimProduct) $shimRelative
        if (Test-Path -LiteralPath $shimLauncher -PathType Leaf) {
            return [pscustomobject]@{
                Name = $Name; Path = $shimLauncher
                Flavor = if ($Name -eq 'Hls') { 'vitis-run' } else { $Name.ToLowerInvariant() }
                Direct = $false; Layout = $layout; ProductRoot = Split-Path -Parent (Split-Path -Parent $shimLauncher)
                Shim = $true
            }
        }
    }

    $commandNames = switch ($Name) {
        'Hls' { @('vitis_hls', 'vitis-run') }
        'Vivado' { @('vivado') }
        'Xsct' { @('xsct') }
        'Vitis' { @('vitis') }
        'Bootgen' { @('bootgen') }
    }
    foreach ($commandName in $commandNames) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command) {
            return [pscustomobject]@{
                Name = $Name; Path = $command.Source
                Flavor = if ($commandName -eq 'vitis-run') { 'vitis-run' } elseif ($commandName -eq 'vitis_hls') { 'vitis-hls' } else { $commandName }
                Direct = $false; Layout = $layout
                ProductRoot = if ($Name -eq 'Vivado' -or $Name -eq 'Bootgen') { $layout.VivadoRoot } else { $layout.VitisRoot }
                Shim = $false
            }
        }
    }

    $productRoot = if ($Name -eq 'Vivado' -or $Name -eq 'Bootgen') { $layout.VivadoRoot } else { $layout.VitisRoot }
    $relative = switch ($Name) {
        'Hls' { 'bin\vitis-run.bat' }
        'Vivado' { 'bin\vivado.bat' }
        'Xsct' { 'bin\xsct.bat' }
        'Vitis' { 'bin\vitis.bat' }
        'Bootgen' { 'bin\bootgen.bat' }
    }
    $launcher = Join-Path $productRoot $relative
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
        throw "$Name launcher was not found under $productRoot"
    }

    $directName = switch ($Name) {
        'Hls' { 'vitis-run.exe' }
        'Vivado' { 'vivado.exe' }
        'Xsct' { 'rdi_xsct.exe' }
        'Vitis' { 'rdi_vitis.exe' }
        'Bootgen' { 'bootgen.exe' }
    }
    $directPath = Join-Path $productRoot "bin\unwrapped\win64.o\$directName"
    $missingLocalTps = -not (Test-Path -LiteralPath (Join-Path $productRoot 'tps\tcl\tcl8.6\init.tcl'))
    $sharedTcl = Test-Path -LiteralPath (Join-Path $layout.SharedTps 'tcl\tcl8.6\init.tcl')
    if ($layout.Layout -eq 'modular' -and $missingLocalTps -and $sharedTcl -and
        (Test-Path -LiteralPath $directPath -PathType Leaf)) {
        return [pscustomobject]@{
            Name = $Name; Path = $directPath
            Flavor = if ($Name -eq 'Hls') { 'vitis-run' } else { $Name.ToLowerInvariant() }
            Direct = $true; Layout = $layout; ProductRoot = $productRoot; Shim = $false
        }
    }

    return [pscustomobject]@{
        Name = $Name; Path = $launcher
        Flavor = if ($Name -eq 'Hls') { 'vitis-run' } else { $Name.ToLowerInvariant() }
        Direct = $false; Layout = $layout; ProductRoot = $productRoot; Shim = $false
    }
}

function Push-EdzAmdEnvironment {
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Tool)

    $names = @(
        'RDI_APPROOT', 'RDI_BASEROOT', 'RDI_BINROOT', 'RDI_BINDIR', 'RDI_DATADIR',
        'RDI_LIBDIR', 'HDI_APPROOT', 'RDI_PLATFORM', 'RDI_OPT_EXT', 'TCL_LIBRARY', 'XILINX_HLS',
        'XILINX_VIVADO', 'XILINX_VITIS', 'RDI_JAVAROOT', 'PYTHONHOME', 'PYTHONPATH', 'PATH'
    )
    $saved = @{}
    foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }

    if ($Tool.PSObject.Properties.Name -contains 'Shim' -and $Tool.Shim) {
        $shimRoot = Split-Path -Parent $Tool.ProductRoot
        $env:XILINX_HLS = ((Join-Path $shimRoot 'Vitis') -replace '\\', '/')
        $env:XILINX_VITIS = $env:XILINX_HLS
        $env:XILINX_VIVADO = ((Join-Path $shimRoot 'Vivado') -replace '\\', '/')
        return $saved
    }
    if (-not $Tool.Direct) { return $saved }

    $app = $Tool.ProductRoot
    $layout = $Tool.Layout
    $sharedTps = $layout.SharedTps
    $env:RDI_APPROOT = $app
    $env:RDI_BASEROOT = $layout.BaseRoot
    $env:RDI_BINROOT = Join-Path $app 'bin'
    $env:RDI_BINDIR = Join-Path $app 'bin'
    $env:RDI_DATADIR = if ($layout.Layout -eq 'modular') { Join-Path $layout.BaseRoot 'data' } else { Join-Path $app 'data' }
    $env:RDI_LIBDIR = Join-Path $app 'lib\win64.o'
    $env:HDI_APPROOT = $app
    $env:RDI_PLATFORM = 'win64'
    $env:RDI_OPT_EXT = '.o'
    $env:TCL_LIBRARY = Join-Path $sharedTps 'tcl\tcl8.6'
    $env:XILINX_HLS = $layout.VitisRoot
    $env:XILINX_VIVADO = $layout.VivadoRoot
    $env:XILINX_VITIS = if ($layout.Layout -eq 'modular') { $layout.BaseRoot } else { $layout.VitisRoot }
    $env:RDI_JAVAROOT = Join-Path $sharedTps 'win64\jre21.0.5_11'

    $embeddedPython = Join-Path $sharedTps 'win64\python-3.13.0'
    if (Test-Path -LiteralPath $embeddedPython) {
        $env:PYTHONHOME = $embeddedPython
        $env:PYTHONPATH = "$embeddedPython;$embeddedPython\bin;$embeddedPython\lib;$embeddedPython\lib\site-packages"
    }
    $prefix = @(
        (Join-Path $app 'bin'),
        (Join-Path $app 'lib\win64.o'),
        (Join-Path $layout.BaseRoot 'win64\lib'),
        (Join-Path $sharedTps 'win64'),
        (Join-Path $env:RDI_JAVAROOT 'bin\server'),
        (Join-Path $env:RDI_JAVAROOT 'bin')
    ) -join ';'
    $env:PATH = "$prefix;$($saved.PATH)"
    return $saved
}

function Pop-EdzAmdEnvironment {
    [CmdletBinding()]
    param([Parameter(Mandatory)][hashtable]$Saved)
    foreach ($name in $Saved.Keys) {
        [Environment]::SetEnvironmentVariable($name, $Saved[$name], 'Process')
    }
}

function Get-EdzVolumeHealth {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Path)
    $root = [System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($Path))
    $letter = $root.Substring(0, 1)
    try {
        $volume = Get-Volume -DriveLetter $letter -ErrorAction Stop
        return [pscustomobject]@{
            Root = $root
            HealthStatus = [string]$volume.HealthStatus
            OperationalStatus = ($volume.OperationalStatus -join ', ')
            Healthy = ($volume.HealthStatus -eq 'Healthy' -and ($volume.OperationalStatus -notcontains 'Full Repair Needed'))
        }
    } catch {
        return [pscustomobject]@{ Root = $root; HealthStatus = 'Unknown'; OperationalStatus = $_.Exception.Message; Healthy = $false }
    }
}

function Get-EdzHlsTaskLibrary {
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Layout)
    return @(
        (Join-Path $Layout.VitisRoot 'lib\win64.o\librdi_hlstasks.dll'),
        (Join-Path $Layout.VivadoRoot 'lib\win64.o\librdi_hlstasks.dll'),
        (Join-Path $Layout.BaseRoot 'win64\lib\librdi_hlstasks.dll')
    ) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
