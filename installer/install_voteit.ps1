$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$archive = Join-Path $scriptDir "VoteIt_app.zip"
$installDir = Join-Path $env:LOCALAPPDATA "Programs\VoteIt"
$dataDir = Join-Path $env:LOCALAPPDATA "VoteIt"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\VoteIt"
$desktopDir = [Environment]::GetFolderPath("Desktop")
$exePath = Join-Path $installDir "VoteIt.exe"
$uninstallSource = Join-Path $scriptDir "uninstall_voteit.ps1"
$uninstallTarget = Join-Path $installDir "uninstall_voteit.ps1"

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

function New-Shortcut {
    param(
        [Parameter(Mandatory = $true)][string]$ShortcutPath,
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [string]$Arguments = "",
        [string]$WorkingDirectory = ""
    )

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $TargetPath
    $shortcut.Arguments = $Arguments
    if ($WorkingDirectory) {
        $shortcut.WorkingDirectory = $WorkingDirectory
    }
    $shortcut.IconLocation = $TargetPath
    $shortcut.Save()
}

if (-not (Test-Path $archive)) {
    throw "Installer archive not found: $archive"
}

Assert-UnderPath -Path $installDir -Parent (Join-Path $env:LOCALAPPDATA "Programs")

New-Item -ItemType Directory -Path $installDir -Force | Out-Null
if (Test-Path $installDir) {
    Get-ChildItem -LiteralPath $installDir -Force | Remove-Item -Recurse -Force
}

Expand-Archive -LiteralPath $archive -DestinationPath $installDir -Force
Copy-Item -LiteralPath $uninstallSource -Destination $uninstallTarget -Force

New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
New-Item -ItemType Directory -Path $startMenuDir -Force | Out-Null

New-Shortcut `
    -ShortcutPath (Join-Path $desktopDir "VoteIt.lnk") `
    -TargetPath $exePath `
    -WorkingDirectory $installDir

New-Shortcut `
    -ShortcutPath (Join-Path $startMenuDir "VoteIt.lnk") `
    -TargetPath $exePath `
    -WorkingDirectory $installDir

New-Shortcut `
    -ShortcutPath (Join-Path $startMenuDir "Uninstall VoteIt.lnk") `
    -TargetPath "powershell.exe" `
    -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$uninstallTarget`"" `
    -WorkingDirectory $installDir

$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\VoteIt"
New-Item -Path $uninstallKey -Force | Out-Null
Set-ItemProperty -Path $uninstallKey -Name "DisplayName" -Value "VoteIt"
Set-ItemProperty -Path $uninstallKey -Name "DisplayVersion" -Value "0.1.0"
Set-ItemProperty -Path $uninstallKey -Name "Publisher" -Value "VoteIt"
Set-ItemProperty -Path $uninstallKey -Name "InstallLocation" -Value $installDir
Set-ItemProperty -Path $uninstallKey -Name "DisplayIcon" -Value $exePath
Set-ItemProperty -Path $uninstallKey -Name "UninstallString" -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$uninstallTarget`""
Set-ItemProperty -Path $uninstallKey -Name "NoModify" -Value 1 -Type DWord
Set-ItemProperty -Path $uninstallKey -Name "NoRepair" -Value 1 -Type DWord

Start-Process -FilePath $exePath -WorkingDirectory $installDir
