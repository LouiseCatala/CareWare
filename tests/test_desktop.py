import json
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from core import database
from desktop import DesktopAPI


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patch=patch.object(database,'DB_PATH',Path(self.tmp.name)/'test.sqlite3')
        self.patch.start()
        self.api=DesktopAPI()
        self.api._window=Mock()

    def tearDown(self):
        self.patch.stop();self.tmp.cleanup()

    def visit(self, **consent):
        return self.api.create_visit({'name':'Test Customer','service_date':'2026-11-02','signature':'Test Customer','consent':{'understood':True,'scan':True,**consent}})

    def test_scan_requires_persisted_consent(self):
        with self.assertRaises(ValueError):self.api.scan(['System Info'])
        with self.assertRaises(ValueError):self.visit(scan=False)
        self.assertEqual(self.api.state()['history'],[])

    def test_scan_persists_and_new_visit_is_isolated(self):
        first=self.visit()['active']['id']
        state=self.api.scan(['System Info'])
        self.assertIn('System Info',json.loads(state['active']['results_json']))
        next_visit=self.visit()['active']
        self.assertNotEqual(first,next_visit['id'])
        self.assertEqual(json.loads(next_visit['results_json']),{})

    def test_cleanup_permission_enforced_even_for_dry_run(self):
        self.visit()
        with self.assertRaises(PermissionError):self.api.clean([],True)
        self.visit(cleanup=True)
        self.assertTrue(self.api.clean([],True)['dry_run'])

    def test_cancelled_cleanup_never_calls_deletion(self):
        self.visit(cleanup=True)
        self.api._window.create_confirmation_dialog.return_value=False
        with patch('desktop.cleanup.clean') as clean:
            self.api.clean(['unused'],False)
            clean.assert_not_called()

    def test_delete_resets_active_visit(self):
        state=self.visit()
        self.api._window.create_confirmation_dialog.return_value=True
        result=self.api.delete_customer(state['active']['customer_id'])
        self.assertIsNone(result['active']);self.assertEqual(result['history'],[])

    def test_invalid_settings_are_not_partially_saved(self):
        with self.assertRaises(ValueError):self.api.save_settings({'business_name':'Changed'},{'cpu_attention_percent':'nan'})
        self.assertEqual(database.get_setting('business_name'),'')

    def test_inspection_survives_scan(self):
        self.visit()
        self.api.inspection({'CPU fan':True})
        results=json.loads(self.api.scan(['System Info'])['active']['results_json'])
        self.assertIn('Physical Inspection Checklist',results)

    def test_history_csv_export_uses_save_dialog_and_contains_checkups(self):
        self.visit()
        destination=Path(self.tmp.name)/'history.csv'
        self.api._window.create_file_dialog.return_value=(str(destination),)
        result=self.api.database_file('csv')
        self.assertIn('Csv complete',result['message'])
        self.assertTrue(destination.is_file())
        with destination.open(encoding='utf-8-sig',newline='') as handle:
            rows=list(csv.DictReader(handle))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['name'],'Test Customer')
        self.assertEqual(rows[0]['service_date'],'2026-11-02')
        self.assertEqual(list(rows[0]),['id','name','phone','pc_brand_model','technician','service_date','health_score','next_due','report_path'])
