"""Release-review reproductions using temporary data and mocked Windows output.

No real cleanup or restore-point operation is performed.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import database, scans, cleanup, report

findings = {}
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    db = root / 'review.sqlite3'
    database.init_db(db)
    customer = database.upsert_customer('Release Test', path=db)
    first = database.create_visit(customer, 'Computer A', 'Tester', '2026-11-03', {'understood': True, 'scan': True}, 'Release Test', path=db)
    second = database.create_visit(customer, 'Computer B', 'Tester', '2026-11-03', {'understood': True, 'scan': True}, 'Release Test', path=db)
    first_paths = report.export_visit(first, root / 'reports', db)
    second_paths = report.export_visit(second, root / 'reports', db)
    findings['same_day_reports_overwrite'] = {
        'same_paths': first_paths == second_paths,
        'first_report_now_contains': json.loads(Path(first_paths[1]).read_text(encoding='utf-8'))['visit']['pc_brand_model'],
    }
    database.delete_customer(customer, db)
    findings['exports_remain_after_customer_deletion'] = all(Path(p).is_file() for p in second_paths)

with patch.object(scans.platform, 'system', return_value='Windows'):
    with patch.object(scans.psutil, 'disk_partitions', return_value=[]), patch.object(scans, 'powershell', return_value={'ok': False, 'stdout': '', 'stderr': 'Access denied'}):
        findings['storage_with_no_readable_data'] = scans.scan_storage()['status']
    with patch.object(scans, 'powershell', return_value={'ok': True, 'stdout': '[]', 'stderr': ''}):
        findings['firewall_with_no_profiles'] = scans.scan_firewall()['status']
    with patch.object(scans, 'powershell', return_value={'ok': True, 'stdout': 'Name : Windows\nLicenseStatus : 0', 'stderr': ''}):
        findings['unlicensed_windows'] = scans.scan_ps_check('Windows Activation and License')['status']
    with patch.object(scans, 'powershell', return_value={'ok': True, 'stdout': 'False\nTpmPresent : False\nProtectionStatus : Off', 'stderr': ''}):
        findings['disabled_security_features'] = scans.scan_ps_check('Secure Boot TPM and Encryption')['status']

warning = subprocess.CompletedProcess([], 0, stdout='WARNING: A new system restore point cannot be created because one has already been created within the past 24 hours.', stderr='')
with patch.object(cleanup.platform, 'system', return_value='Windows'), patch.object(cleanup.subprocess, 'run', return_value=warning):
    findings['restore_warning_treated_as_success'] = cleanup.create_restore_point()[0]

print(json.dumps(findings, indent=2))
