# VoteIt Desktop

Offline desktop voting system for schools and local elections.

## Features

- Create elections and multiple polls.
- Add candidates with photo, name, and description.
- Operator-controlled EVM-style voting screen.
- One vote per poll per enabled voter.
- SQLite local database.
- View current and old results.
- Export results to Excel.
- Package as a Windows executable with PyInstaller.

## Operator Password

The default operator password is `1234`.

Use `Voting > Change Password` inside the app before running a real election.
Only the operator password can open the voter-facing voting window.

## Election Status

- `Draft`: setup is open. Add polls and candidates here.
- `Active`: voting is allowed. Setup is locked.
- `Closed`: voting is stopped. Results can still be viewed and exported.

## Run

```powershell
& "C:\Users\ZB933BA\AppData\Local\Programs\Python\Python310\python.exe" -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\scripts\run.ps1
```

Or run the helper:

```powershell
.\scripts\run.ps1
```

## Build EXE

```powershell
.\scripts\build_exe.ps1
```

The executable will be created in `dist\VoteIt\VoteIt.exe`.

## Build Installer

### MSI installer (recommended)

Real Windows Installer `.msi` with proper Add/Remove Programs entry and
`msiexec` install/uninstall. Requires [WiX Toolset 3.14](https://wixtoolset.org/)
to be installed first.

```powershell
.\scripts\build_msi.ps1
```

Output: `installer_output\VoteIt_Setup.msi`

Install / uninstall:

```powershell
# Install (admin required, GUI prompt)
msiexec /i installer_output\VoteIt_Setup.msi

# Silent install
msiexec /i installer_output\VoteIt_Setup.msi /qn

# Uninstall (or use Settings > Apps > VoteIt)
msiexec /x installer_output\VoteIt_Setup.msi /qn
```

The MSI installs to `%ProgramFiles%\VoteIt`, creates Start Menu and Desktop
shortcuts, and registers in Add/Remove Programs. Election data in
`%LOCALAPPDATA%\VoteIt` is preserved across uninstall.

### One-click EXE installer (no admin required)

```powershell
.\scripts\build_one_click_installer.ps1
```

Output: `installer_output\VoteIt_One_Click_Setup.exe`

Self-contained per-user installer. Does not require Python or admin rights on
the target computer.

### Inno Setup installer

After building the EXE, open `installer\VoteIt.iss` in Inno Setup and compile.
Output: `installer_output\VoteIt_Setup.exe`.
