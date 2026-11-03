"""Additional local-only, read-only diagnostics for CareWare navigation pages.

These checks deliberately avoid browsing history, personal-file traversal, repairs,
cleanup, and network access. They are standalone so importing this module cannot
create a circular dependency with core.scans.
"""
from __future__ import annotations

import json
import platform
import subprocess


def _result(status: str, headline: str, explanation: str, action: str, details: str = "") -> dict:
    if status not in {"good", "attention", "problem", "unknown"}:
        status = "unknown"
    return {
        "status": status,
        "headline": str(headline),
        "explanation": str(explanation),
        "action": str(action),
        "details": str(details or ""),
    }


def _powershell(script: str, timeout: int = 25) -> dict:
    """Run a fixed local PowerShell query, capture output, and bound execution time."""
    if platform.system() != "Windows":
        return {"ok": False, "stdout": "", "stderr": "This diagnostic is available on Windows only."}
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return {"ok": completed.returncode == 0, "stdout": completed.stdout or "", "stderr": completed.stderr or ""}
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        err = exc.stderr or ""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        if isinstance(err, bytes):
            err = err.decode(errors="replace")
        return {"ok": False, "stdout": out, "stderr": f"Timed out after {timeout} seconds. {err}".strip()}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "stdout": "", "stderr": f"Could not start local PowerShell query: {type(exc).__name__}."}


def _unknown_unavailable(label: str, reason: str) -> dict:
    return _result("unknown", f"{label} could not be assessed", reason,
                   "Review the relevant application settings with the customer.")


def scan_office_other_licenses() -> dict:
    """Read Office licensing state without selecting or returning any key fields."""
    script = r"""
$ErrorActionPreference = 'Stop'
$rows = @(Get-CimInstance SoftwareLicensingProduct -ErrorAction Stop |
  Where-Object { $_.Name -match 'Office|Microsoft 365' -and $_.PartialProductKey } |
  Select-Object Name, Description, LicenseStatus)
$rows | ConvertTo-Json -Compress
"""
    r = _powershell(script)
    if not r["ok"]:
        return _unknown_unavailable("Office licensing", r["stderr"] or "Windows did not return Office license status.")
    try:
        rows = json.loads(r["stdout"]) if r["stdout"].strip() else []
        rows = rows if isinstance(rows, list) else [rows]
    except (ValueError, TypeError):
        return _unknown_unavailable("Office licensing", "Windows returned data that could not be interpreted safely.")
    if not rows:
        return _result("unknown", "No Office license status was returned",
                       "No matching Office licensing record was exposed to this read-only check.",
                       "Open an Office application and review Account and activation status.",
                       "No product keys or partial product keys were requested or displayed.")
    names = [str(row.get("Name", "Office product")) for row in rows if isinstance(row, dict)]
    statuses = [row.get("LicenseStatus") for row in rows if isinstance(row, dict)]
    # Software licensing status 1 means licensed; avoid interpreting missing/other values as failure.
    if statuses and all(value == 1 for value in statuses):
        status, headline = "good", "Office reports a licensed product"
        action = "No license action is indicated by this read-only check."
    elif any(value in (0, 2, 3, 4, 5, 6) for value in statuses):
        status, headline = "attention", "An Office license status may need review"
        action = "Review activation from the Office Account page with the customer."
    else:
        status, headline = "unknown", "Office license status is inconclusive"
        action = "Review activation from the Office Account page with the customer."
    details = "\n".join(f"{name}: LicenseStatus={code}" for name, code in zip(names, statuses))
    return _result(status, headline, "We read Office licensing status from Windows; no key material was requested.", action, details)


def scan_browser_extensions() -> dict:
    """List extension identifiers from browser extension registry metadata only."""
    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$roots = @(
 'HKCU:\Software\Google\Chrome\PreferenceMACs\Default\extensions',
 'HKCU:\Software\Microsoft\Edge\PreferenceMACs\Default\extensions',
 'HKCU:\Software\Google\Chrome\Extensions',
 'HKCU:\Software\Microsoft\Edge\Extensions'
)
$items = @()
foreach ($root in $roots) {
  if (Test-Path -LiteralPath $root) {
    foreach ($key in (Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue)) {
      $items += [pscustomobject]@{ Browser = if ($root -match 'Edge') {'Edge'} else {'Chrome'}; ExtensionId = $key.PSChildName }
    }
  }
}
$items | Sort-Object Browser,ExtensionId -Unique | ConvertTo-Json -Compress
"""
    r = _powershell(script)
    if not r["ok"]:
        return _unknown_unavailable("Browser extensions", r["stderr"] or "Browser extension registry metadata could not be read.")
    try:
        rows = json.loads(r["stdout"]) if r["stdout"].strip() else []
        rows = rows if isinstance(rows, list) else [rows]
    except (ValueError, TypeError):
        return _unknown_unavailable("Browser extensions", "Windows returned data that could not be interpreted safely.")
    ids = [f"{row.get('Browser', 'Browser')}: {row.get('ExtensionId', '')}" for row in rows if isinstance(row, dict)]
    if ids:
        return _result("attention", "Browser extension metadata is available",
                       f"Windows registry metadata listed {len(ids)} extension identifier(s). This is not a safety verdict.",
                       "Review extensions in the browser's own extensions page with the customer.",
                       "\n".join(ids) + "\nBrowsing history and page contents were not read.")
    return _result("unknown", "No browser extension metadata was found",
                   "The limited registry locations checked did not list extensions; this does not prove that no extensions are installed.",
                   "Review extensions in the browser's own extensions page if needed.",
                   "Only Chrome/Edge extension registry metadata was checked; browsing history was not read.")


def scan_bloatware() -> dict:
    """Return conservative installed-app metadata; do not label software unwanted."""
    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$rows = @(Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' |
  Where-Object { $_.DisplayName } | Select-Object -First 150 DisplayName,DisplayVersion,Publisher)
$rows | ConvertTo-Json -Compress
"""
    r = _powershell(script, timeout=35)
    if not r["ok"]:
        return _unknown_unavailable("Unwanted software", r["stderr"] or "Installed application metadata could not be read.")
    try:
        rows = json.loads(r["stdout"]) if r["stdout"].strip() else []
        rows = rows if isinstance(rows, list) else [rows]
    except (ValueError, TypeError):
        return _unknown_unavailable("Unwanted software", "Windows returned data that could not be interpreted safely.")
    return _result("unknown", "Installed software needs customer review",
                   f"Windows returned metadata for {len(rows)} installed application(s); CareWare cannot determine which are unwanted.",
                   "Review the installed-app list with the customer; do not uninstall anything as part of this check.",
                   "Inventory metadata only; no files were traversed or changed. " +
                   "\n".join(str(row.get("DisplayName", "")) for row in rows[:80] if isinstance(row, dict)))


def scan_outdated_software() -> dict:
    """State that update status cannot be determined without contacting vendors."""
    return _result("unknown", "Software update status was not checked",
                   "Determining whether third-party software is current would require trusted version comparison data. This local-only check does not contact vendors or the internet.",
                   "Use each application's built-in update feature or its trusted vendor source.",
                   "No outbound requests were made; installed files and personal content were not inspected.")


ADDITIONAL_SCANS = {
    "Browser Extensions": scan_browser_extensions,
    "Bloatware and Unwanted Apps": scan_bloatware,
    "Outdated Software": scan_outdated_software,
    "Office and Other Licenses": scan_office_other_licenses,
}
