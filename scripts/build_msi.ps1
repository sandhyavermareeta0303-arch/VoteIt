$ErrorActionPreference = "Stop"

# Build a real Windows .msi installer for VoteIt using WiX Toolset 3.x.
# Prerequisites:
#   1. Python venv set up with requirements.txt installed
#   2. WiX Toolset 3.14 installed from https://wixtoolset.org/
# Output:
#   installer_output\VoteIt_Setup.msi
# Install: double-click the MSI (admin elevation required).
# Uninstall: Settings > Apps > VoteIt > Uninstall, or:  msiexec /x "VoteIt_Setup.msi"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$distDir       = Join-Path $repoRoot "dist\VoteIt"
$installerDir  = Join-Path $repoRoot "installer"
$outputDir     = Join-Path $repoRoot "installer_output"
$buildDir      = Join-Path $outputDir "msi-build"
$wxsMain       = Join-Path $installerDir "VoteIt.wxs"
$wxsHarvest    = Join-Path $buildDir     "Files.wxs"
$wixobjMain    = Join-Path $buildDir     "VoteIt.wixobj"
$wixobjHarvest = Join-Path $buildDir     "Files.wixobj"
$msiOut        = Join-Path $outputDir    "VoteIt_Setup.msi"
$licenseRtf    = Join-Path $installerDir "License.rtf"
$appExe        = Join-Path $distDir      "VoteIt.exe"

# Read version from voteit_app/__init__.py to keep MSI in sync with app version.
$versionFile = Join-Path $repoRoot "voteit_app\__init__.py"
$versionMatch = Select-String -Path $versionFile -Pattern '__version__\s*=\s*"([^"]+)"'
if (-not $versionMatch) {
    throw "Could not read __version__ from $versionFile."
}
$productVersion = $versionMatch.Matches[0].Groups[1].Value

# Locate WiX Toolset 3.x. Prefers a local extraction at tools\wix314\ (no
# admin install needed). Falls back to system WiX if installed.
$wixCandidates = @( (Join-Path $repoRoot "tools\wix314") )
if ($env:WIX) { $wixCandidates += (Join-Path $env:WIX "bin") }
if (${env:ProgramFiles(x86)}) {
    $wixCandidates += (Join-Path ${env:ProgramFiles(x86)} "WiX Toolset v3.14\bin")
    $wixCandidates += (Join-Path ${env:ProgramFiles(x86)} "WiX Toolset v3.11\bin")
}
if ($env:ProgramFiles) {
    $wixCandidates += (Join-Path $env:ProgramFiles "WiX Toolset v3.14\bin")
}
$wixBin = $wixCandidates |
    Where-Object { $_ -and (Test-Path (Join-Path $_ "candle.exe")) } |
    Select-Object -First 1
if (-not $wixBin) {
    throw "WiX Toolset 3.x not found. Install WiX 3.14 from https://wixtoolset.org/ then retry."
}

$candle = Join-Path $wixBin "candle.exe"
$light  = Join-Path $wixBin "light.exe"
$heat   = Join-Path $wixBin "heat.exe"

Push-Location $repoRoot
try {
    Write-Host "Building app with PyInstaller..."
    & $python -m PyInstaller --noconfirm --windowed --name VoteIt main.py
    if (-not (Test-Path $appExe)) {
        throw "PyInstaller did not produce $appExe."
    }

    if (Test-Path $buildDir) {
        Remove-Item -LiteralPath $buildDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $buildDir -Force | Out-Null

    Write-Host "Harvesting files from $distDir ..."
    & $heat dir $distDir `
        -cg HarvestedFiles `
        -dr INSTALLFOLDER `
        -ag `
        -srd `
        -sfrag `
        -sreg `
        -scom `
        -ke `
        -var var.HarvestSource `
        -out $wxsHarvest
    if ($LASTEXITCODE -ne 0) { throw "heat.exe failed (exit $LASTEXITCODE)." }

    Write-Host "Compiling WiX sources..."
    & $candle `
        "-dProductVersion=$productVersion" `
        "-dHarvestSource=$distDir" `
        "-dLicenseRtf=$licenseRtf" `
        "-dAppExe=$appExe" `
        -arch x64 `
        -out (Join-Path $buildDir "\") `
        $wxsMain $wxsHarvest
    if ($LASTEXITCODE -ne 0) { throw "candle.exe failed (exit $LASTEXITCODE)." }

    if (Test-Path $msiOut) {
        Remove-Item -LiteralPath $msiOut -Force
    }

    Write-Host "Linking MSI..."
    # Suppress ICE38/43/57: spurious for per-machine installs that use ProgramMenuFolder
    # with HKLM keypaths. ICE doesn't account for ALLUSERS=1 redirecting to CommonProgramMenu.
    & $light `
        -ext WixUIExtension `
        -sice:ICE38 -sice:ICE43 -sice:ICE57 `
        -b $distDir `
        -out $msiOut `
        $wixobjMain $wixobjHarvest
    if ($LASTEXITCODE -ne 0) { throw "light.exe failed (exit $LASTEXITCODE)." }

    if (-not (Test-Path $msiOut)) {
        throw "MSI was not produced: $msiOut"
    }

    Write-Host ""
    Write-Host "Created MSI: $msiOut"
    Write-Host "Version:     $productVersion"
    Write-Host ""
    Write-Host "Install:   double-click the MSI (admin required), or"
    Write-Host "             msiexec /i `"$msiOut`""
    Write-Host "Silent:    msiexec /i `"$msiOut`" /qn"
    Write-Host "Uninstall: Settings > Apps > VoteIt > Uninstall, or"
    Write-Host "             msiexec /x `"$msiOut`" /qn"
}
finally {
    Pop-Location
}
