$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$distDir = Join-Path $repoRoot "dist\VoteIt"
$installerDir = Join-Path $repoRoot "installer"
$outputDir = Join-Path $repoRoot "installer_output"
$payloadDir = Join-Path $outputDir "payload"
$payloadZip = Join-Path $payloadDir "VoteIt_app.zip"
$setupPath = Join-Path $outputDir "VoteIt_One_Click_Setup.exe"
$bootstrapperSource = Join-Path $installerDir "VoteItBootstrapper.cs"
$uninstallResource = Join-Path $installerDir "uninstall_voteit.ps1"

function Assert-UnderPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $resolvedParent = [System.IO.Path]::GetFullPath($Parent)
    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $resolvedPath.StartsWith($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify path outside expected location: $resolvedPath"
    }
}

if (-not (Test-Path $python)) {
    $python = "python"
}

$cscCandidates = @(
    (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe")
)
$csc = $cscCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $csc) {
    throw "Could not find the .NET C# compiler needed to build the one-click installer."
}

Push-Location $repoRoot
try {
    & $python -m PyInstaller --noconfirm --windowed --name VoteIt main.py

    if (-not (Test-Path (Join-Path $distDir "VoteIt.exe"))) {
        throw "PyInstaller build did not create VoteIt.exe."
    }

    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    if (Test-Path $payloadDir) {
        Assert-UnderPath -Path $payloadDir -Parent $outputDir
        Remove-Item -LiteralPath $payloadDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $payloadDir -Force | Out-Null

    Compress-Archive -Path (Join-Path $distDir "*") -DestinationPath $payloadZip -Force

    if (Test-Path $setupPath) {
        Remove-Item -LiteralPath $setupPath -Force
    }

    & $csc `
        /nologo `
        /target:winexe `
        /platform:anycpu `
        /out:$setupPath `
        /reference:System.IO.Compression.dll `
        /reference:System.IO.Compression.FileSystem.dll `
        /reference:System.Windows.Forms.dll `
        /resource:$payloadZip,VoteIt_app.zip `
        /resource:$uninstallResource,uninstall_voteit.ps1 `
        $bootstrapperSource

    if (-not (Test-Path $setupPath)) {
        throw "Installer was not created: $setupPath"
    }

    Write-Host "Created installer: $setupPath"
}
finally {
    Pop-Location
}
