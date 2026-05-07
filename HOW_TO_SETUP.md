# VoteIt Setup Guide

## 1. Install Python

Install Python 3.10 or newer on Windows.

Recommended path on this machine:

```powershell
C:\Users\ZB933BA\AppData\Local\Programs\Python\Python310\python.exe
```

## 2. Open Project Folder

Open PowerShell in:

```powershell
C:\wamp64\www\VoteIt
```

## 3. Create Virtual Environment

```powershell
& "C:\Users\ZB933BA\AppData\Local\Programs\Python\Python310\python.exe" -m venv .venv
```

## 4. Activate Virtual Environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate again.

## 5. Install Dependencies

```powershell
pip install -r requirements.txt
```

## 6. Run App In Development

```powershell
.\scripts\run.ps1
```

Or:

```powershell
.\.venv\Scripts\python.exe main.py
```

## 7. First-Time App Setup

1. Open the app.
2. Go to `Setup`.
3. Create an election.
4. Add polls.
5. Add candidates with name, description, and photo.
6. Click `Start Election`.
7. Go to `Voting`.
8. Click `Open Voter Window`.
9. Enter operator password.

Default operator password:

```text
1234
```

Change it from:

```text
Voting > Change Password
```

## 8. Voting Process

1. Operator opens the voter window.
2. Voter selects one candidate in each poll.
3. Voter clicks `Submit Vote`.
4. Voter window closes automatically.
5. Operator opens the voter window again for the next voter.

Only `Active` elections can accept votes.

## 9. View And Export Results

1. Go to `Results`.
2. Select election.
3. Click `Refresh`.
4. Click `Export Excel`.

Excel files are saved in:

```powershell
C:\Users\ZB933BA\AppData\Local\VoteIt\exports
```

For development runs, exports are saved in:

```powershell
C:\wamp64\www\VoteIt\exports
```

## 10. Build Windows EXE

```powershell
.\scripts\build_exe.ps1
```

The EXE will be created at:

```powershell
C:\wamp64\www\VoteIt\dist\VoteIt\VoteIt.exe
```

## 11. Build One-Click Installer

This creates a single installer EXE that does not require Python on the target computer.
It uses a small embedded Windows bootstrapper and installs VoteIt for the current user.

```powershell
.\scripts\build_one_click_installer.ps1
```

The installer will be created at:

```powershell
C:\wamp64\www\VoteIt\installer_output\VoteIt_One_Click_Setup.exe
```

The one-click installer installs VoteIt for the current Windows user at:

```powershell
C:\Users\ZB933BA\AppData\Local\Programs\VoteIt
```

It also creates:

- Desktop shortcut
- Start Menu shortcut
- Uninstall shortcut
- Windows Apps uninstall entry

## 12. Build Inno Setup Installer

Install Inno Setup first.

Then open:

```powershell
C:\wamp64\www\VoteIt\installer\VoteIt.iss
```

Compile it in Inno Setup.

The installer will be created at:

```powershell
C:\wamp64\www\VoteIt\installer_output\VoteIt_Setup.exe
```

## 13. Runtime Data Location

Packaged app data is stored here:

```powershell
C:\Users\ZB933BA\AppData\Local\VoteIt
```

Important files/folders:

```powershell
data\voteit.sqlite3
data\candidate_photos
exports
```

## 14. Election Status Meaning

`Draft`

Setup is open. Add polls and candidates here.

`Active`

Voting is allowed. Setup is locked.

`Closed`

Voting is stopped. Results can still be viewed and exported.
