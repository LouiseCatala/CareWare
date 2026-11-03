# CareWare

CareWare is a Windows desktop app that makes basic PC health checks easier to understand. It was built for everyday computer users who want to check their desktop or laptop without needing to understand technical tools, command-line output, or complicated system menus.

CareWare presents local diagnostic results in plain language, keeps checkup history on the computer, and provides guarded cleanup tools that require review and permission before anything is removed.

## Preview

![CareWare desktop app preview](ui_preview.png)

## Download

[**Download CareWare for Windows**](https://github.com/LouiseCatala/CareWare/raw/main/release/CareWare-Setup.exe)

Current installer SHA-256:

```text
C939C180F81BC3BE5BA4CB293BEBC73ECD22689B4DF363D97508AD15B5DB9A3C
```

CareWare currently supports 64-bit Windows 10 and Windows 11. It requires the Microsoft Edge WebView2 Runtime, which is already included with most supported Windows installations. The installer will explain what to do if WebView2 is missing.

The installer is not yet code-signed, so Windows may display **Unknown publisher**. Verify the SHA-256 value above before installing the downloaded file.

## How to install

1. Select **Download CareWare for Windows** above.
2. Save `CareWare-Setup.exe` somewhere easy to find, such as Downloads.
3. Verify the installer SHA-256 if you want to confirm the file matches this release.
4. Double-click `CareWare-Setup.exe`.
5. Follow the installation window and optionally create a Desktop shortcut.
6. Open **CareWare** from the Desktop shortcut or Start menu.
7. Create a new checkup, review the consent notice, and choose the checks you want to run.

CareWare installs for the current Windows user and does not require a separate Python or Node.js installation.

## Overview

CareWare provides:

- A simple dashboard for PC checks, cleanup, physical inspection, and reports.
- Read-only checks for system information, storage, memory, processor use, Windows health, security settings, devices, startup programs, and other local system information.
- Plain-language results marked as passed, needing attention, a problem, or unavailable.
- Quick, full, and individually selected check modes.
- A guarded temporary-file cleanup workflow with separate consent, file review, confirmation, and restore-point verification.
- Local checkup history and comparison between recorded visits.
- PDF and JSON report export for individual checkups.
- CSV export from **Checkup history** for all saved checkups.
- Local reminders, business details, report branding, and database backup and restore.

## Why CareWare was built

Windows includes many useful diagnostic tools, but their results are often spread across technical screens and written for experienced users. CareWare brings common checks into one focused desktop app and translates the outcome into clear, practical language.

The goal is to help nontechnical users understand the condition of their computer, see what may need attention, and keep a local record without pretending that every warning needs an immediate repair. CareWare does not upload checkup results; customer, consent, and scan data remain in the local CareWare database on the computer.

## Safety and privacy

- Checks are read-only unless the user explicitly enters the cleanup flow.
- Cleanup only targets eligible older files in Windows temporary folders.
- Personal documents, photos, downloads, passwords, and browsing history are not cleanup targets.
- Cleanup starts in dry-run mode and requires recorded permission, a second confirmation, and a verified Windows restore point.
- Missing or unreadable diagnostic information is shown as unavailable instead of being reported as healthy.
- Data is stored locally in `Documents\CareWare`.

CareWare is a diagnostic aid. It does not replace a qualified technician for hardware failure, data recovery, malware response, or other high-risk repairs.

## Using Checkup history

Open **Checkup history** from the top-right header to:

- Search previous checkups by customer, phone number, or computer.
- Compare two recorded checkups.
- Export an individual PDF and JSON report.
- Select **Export CSV** to save the complete history as a spreadsheet-compatible file.

## Development

The desktop shell uses Python 3.11 and pywebview. The interface uses React, TypeScript, Tailwind CSS, and Vite. Local records use SQLite, and PDF reports use ReportLab.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ui
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe main.py
```

Run the automated checks with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The current release passes 24 unit and regression tests, the desktop navigation smoke test, a packaged executable test, dependency audits, and an isolated installer install/uninstall test. See [RELEASE_REVIEW.md](RELEASE_REVIEW.md) for the release review and remaining distribution note.

## Building the Windows installer

Run `build.bat` on a Windows development machine to build the React interface, execute the tests, and create `dist\CareWare\CareWare.exe`. Compile `installer.iss` with Inno Setup to produce `installer_output\CareWare-Setup.exe`.
