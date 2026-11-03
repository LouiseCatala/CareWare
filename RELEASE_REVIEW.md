# CareWare release review — 2026-11-03

**Update after fixes: source blockers addressed; final clean-machine acceptance remains required.** The original findings below are retained as the review record. See the remediation section for their current status. No customer files were cleaned up and nothing was published.

## Remediation

- Report filenames now include the checkup ID and a unique export identifier. Repeated exports preserve previous PDFs and JSON files; logo rendering was tested with Pillow 13.
- Missing storage/firewall results return unknown. Unactivated Windows returns attention. Generic inventory/security output requires manual review instead of implying health. System File Checker requires recognized output to pass; PowerShell errors stop execution.
- Cleanup requires a matching, uniquely named restore point and sequence number. Warnings, malformed responses, and missing points fail closed. Regression tests prove failed verification prevents deletion of a temporary test file.
- Pillow is now 13.0.0; build tools were also updated. The full installed Python environment audit reports no known vulnerabilities. This audit does not cover every bundled native-library vulnerability.
- Setup and application startup detect missing WebView2 and provide the official installation address. The installer uses a per-user directory and restricts installation to compatible Windows systems.
- Customer deletion text now explicitly explains that exported reports and backups remain on disk.
- All 24 unit/regression tests pass, including PDF export with a logo and History CSV export through the desktop save dialog. The existing desktop UI integration test passes. The React/CSS design files were not changed.
- The executable and installer have been built. The packaged executable passed an isolated end-to-end check covering UI/images, bottom categories, header pages, consent, scan persistence, and PDF/JSON report export. A separate installer test completed install, packaged-app smoke testing, and uninstall successfully.
- The packaged check also verifies that the standalone Checkup History page exposes its **Export CSV** action.
- Final installer: `installer_output/CareWare-Setup.exe` (27,068,232 bytes), SHA-256 `C939C180F81BC3BE5BA4CB293BEBC73ECD22689B4DF363D97508AD15B5DB9A3C`.
- The release binaries are not Authenticode-signed. Windows can identify them as an unknown publisher until a trusted code-signing certificate is supplied and integrated into the build.

Final release acceptance still needs a clean supported Windows machine, including the missing-WebView2 path. This workstation cannot substitute for that environment. Real privileged restore-point creation and deletion were not exercised; safe failure paths were tested with mocks.

## Release blockers

1. **Report exports overwrite previous checkups.** `core/report.py:30` builds filenames from customer name and date only. Two checkups for the same customer on the same date produce identical PDF and JSON paths. A temporary-data reproduction confirmed that exporting Computer B replaces Computer A's raw report. Include a unique checkup identifier in filenames and test repeated exports.

2. **Diagnostics can incorrectly report healthy results.** In `core/scans.py`, storage without readable data and firewall with an empty profile list return `good`. Generic PowerShell checks also return `good` for unlicensed Windows and disabled security features when command execution succeeds. These results were reproduced with mocked Windows responses. Parse each diagnostic's actual result; missing data must be unknown/error, and successful command execution must not imply a healthy device.

3. **Cleanup does not verify restore-point creation.** `core/cleanup.py:38` trusts a zero PowerShell exit code. A mocked response containing a skipped-creation warning was accepted as success. Verify the requested restore point exists before treating the safeguard as successful. No real deletion or restore operation was performed. Microsoft documents the creation frequency restriction: https://learn.microsoft.com/en-us/powershell/module/Microsoft.PowerShell.Management/checkpoint-computer?view=powershell-5.1

4. **Installed Python image dependency has a known vulnerability.** Both `requirements.txt:3` and the installed environment use Pillow 10.4.0. CVE-2026-25990 affects Pillow >=10.3.0 and <12.1.1 and concerns an out-of-bounds write when loading crafted PSD images. Report logos accept local image paths. Update to a supported patched release, audit all Python dependencies, and verify report/logo compatibility. Advisory: https://github.com/python-pillow/Pillow/security/advisories/GHSA-cfh3-3jmp-rvhc

5. **The distributable has not been validated.** Neither `dist/CareWare/CareWare.exe` nor `installer_output/CareWare-Setup.exe` exists in this workspace. The desktop runtime explicitly uses EdgeChromium, while setup does not provision or check WebView2. Build the installer, handle the runtime prerequisite, and test install, launch, persistence, report export, and uninstall on a clean supported Windows machine before release.

## Additional finding

Deleting a customer removes database records but leaves exported PDF/JSON files. The temporary-data reproduction confirmed this. Clarify the deletion dialog's scope and document how users remove exported records.

## Verification completed

- Python unit tests: 19 passed.
- TypeScript type check: passed.
- Vite production build: passed.
- Windows webview smoke test: passed, including header pages, embedded dashboard actions, consent, and scan bridge.
- npm audit: zero reported vulnerabilities at review time.
- pip check: no broken dependency requirements. This is not a vulnerability audit; a full Python vulnerability audit remains outstanding.
- `tests/release_probe.py`: reproduces export collision and diagnostic/restore-point findings using temporary files and mocked operating-system output.

These checks validate the development environment, not a clean-machine installer or all real Windows diagnostic outcomes. Production code was not changed as part of this review.
