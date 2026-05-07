$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "C:\Users\ZB933BA\AppData\Local\Programs\Python\Python310\python.exe"
}
if (-not (Test-Path $python)) {
    $python = "py"
}

& $python -m PyInstaller --noconfirm --windowed --name VoteIt main.py
