$ErrorActionPreference = "Stop"

$installDir = Join-Path $env:LOCALAPPDATA "Programs\VoteIt"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\VoteIt"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "VoteIt.lnk"
$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\VoteIt"

function Assert-UnderPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $resolvedParent = [System.IO.Path]::GetFullPath($Parent)
    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $resolvedPath.StartsWith($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside expected location: $resolvedPath"
    }
}

Get-Process VoteIt -ErrorAction SilentlyContinue | Stop-Process -Force

if (Test-Path $desktopShortcut) {
    Remove-Item -LiteralPath $desktopShortcut -Force
}

if (Test-Path $startMenuDir) {
    Assert-UnderPath -Path $startMenuDir -Parent (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs")
    Remove-Item -LiteralPath $startMenuDir -Recurse -Force
}

if (Test-Path $installDir) {
    Assert-UnderPath -Path $installDir -Parent (Join-Path $env:LOCALAPPDATA "Programs")
    Remove-Item -LiteralPath $installDir -Recurse -Force
}

if (Test-Path $uninstallKey) {
    Remove-Item -Path $uninstallKey -Recurse -Force
}

Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show(
    "VoteIt has been uninstalled. Election data in AppData\Local\VoteIt was kept for safety.",
    "VoteIt Uninstall"
) | Out-Null
