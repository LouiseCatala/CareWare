"""Regression coverage for release blockers; never performs real maintenance."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import cleanup, database, report, scans


class ReleaseTests(unittest.TestCase):
    def test_exports_preserve_each_checkup_and_previous_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'test.sqlite3';database.init_db(db)
            from PIL import Image
            logo=Path(tmp)/'logo.png';Image.new('RGB',(100,60),'blue').save(logo)
            database.set_setting('logo_path',str(logo),db)
            cid=database.upsert_customer('Same Customer',path=db)
            paths=[]
            for pc in ('Computer A','Computer B'):
                vid=database.create_visit(cid,pc,'Tech','2026-11-03',{'understood':True,'scan':True},'Signed',path=db)
                paths.append(report.export_visit(vid,tmp,db))
            paths.append(report.export_visit(vid,tmp,db))
            self.assertEqual(len({p for pair in paths for p in pair}),6)
            self.assertEqual(json.loads(Path(paths[0][1]).read_text())['visit']['pc_brand_model'],'Computer A')
            self.assertTrue(all(Path(pdf).read_bytes().startswith(b'%PDF') for pdf,_ in paths))

    @patch.object(scans.platform,'system',return_value='Windows')
    def test_unavailable_and_unhealthy_diagnostics_do_not_pass(self,_):
        with patch.object(scans.psutil,'disk_partitions',return_value=[]), patch.object(scans,'powershell',return_value={'ok':False,'stdout':'','stderr':'Denied'}):
            self.assertEqual(scans.scan_storage()['status'],'unknown')
        for output,expected in [('[]','unknown'),('null','unknown'),('[{"Enabled":true}]','good'),('[{"Enabled":false}]','attention')]:
            with patch.object(scans,'powershell',return_value={'ok':True,'stdout':output,'stderr':''}):
                self.assertEqual(scans.scan_firewall()['status'],expected)
        for output,expected in [('LicenseStatus : 0','attention'),('LicenseStatus : 1','good'),('','unknown')]:
            with patch.object(scans,'powershell',return_value={'ok':True,'stdout':output,'stderr':''}):
                self.assertEqual(scans.scan_ps_check('Windows Activation and License')['status'],expected)
        with patch.object(scans,'powershell',return_value={'ok':True,'stdout':'False\nTpmPresent : False\nProtectionStatus : Off','stderr':''}):
            self.assertEqual(scans.scan_ps_check('Secure Boot TPM and Encryption')['status'],'unknown')

    @patch.object(cleanup.platform,'system',return_value='Windows')
    def test_restore_requires_verified_unique_point(self,_):
        for output in ('WARNING: creation skipped','{}','{"Description":"other","SequenceNumber":1}'):
            with patch.object(cleanup.subprocess,'run',return_value=subprocess.CompletedProcess([],0,output,'')):
                self.assertFalse(cleanup.create_restore_point()[0])
        def verified(args,**kwargs):
            import re
            description=re.search(r"-Description '([^']+)'",args[-1]).group(1)
            return subprocess.CompletedProcess([],0,json.dumps({'Description':description,'SequenceNumber':123}),'')
        with patch.object(cleanup.subprocess,'run',side_effect=verified):
            self.assertTrue(cleanup.create_restore_point()[0])

    @patch.object(cleanup.platform,'system',return_value='Windows')
    def test_failed_restore_prevents_deletion(self,_):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'keep.txt';target.write_text('keep')
            with patch.dict(cleanup.os.environ,{'TEMP':tmp,'TMP':tmp}), patch.object(cleanup,'candidates',return_value=[{'path':str(target)}]), patch.object(cleanup,'create_restore_point',return_value=(False,'Skipped')):
                with self.assertRaises(RuntimeError):cleanup.clean([str(target)],consent_cleanup=True,dry_run=False)
            self.assertEqual(target.read_text(),'keep')
