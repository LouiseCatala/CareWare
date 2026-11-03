import json, tempfile, unittest
from pathlib import Path
from core import database, scans, cleanup

class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/'careware.sqlite3';database.init_db(self.db)
    def tearDown(self):self.tmp.cleanup()
    def test_consent_required_and_visit_recorded(self):
        cid=database.upsert_customer('Sample Customer','555-0100',path=self.db)
        with self.assertRaises(ValueError):database.create_visit(cid,'Laptop','Tech','2026-11-01',{'understood':True,'scan':False},'Sample Customer',path=self.db)
        vid=database.create_visit(cid,'Laptop','Tech','2026-11-01',{'understood':True,'scan':True,'cleanup':False,'reminders':True},'Sample Customer',path=self.db,consent_language='Taglish')
        self.assertGreater(vid,0)
        rows=database.search_visits('Sample',self.db)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['name'],'Sample Customer');self.assertEqual(rows[0]['consent_language'],'Taglish')
    def test_results_health_score_and_settings(self):
        cid=database.upsert_customer('A',path=self.db);vid=database.create_visit(cid,'PC','T','2026-11-01',{'understood':1,'scan':1},'A',path=self.db)
        database.save_results(vid,{'x':{'status':'good'},'y':{'status':'attention'}},self.db)
        self.assertEqual(database.health_score({'x':{'status':'good'},'y':{'status':'attention'}}),83)
        database.set_setting('business_name','Test',self.db);self.assertEqual(database.get_setting('business_name',path=self.db),'Test')
    def test_customer_delete_cascades_visits(self):
        cid=database.upsert_customer('A',path=self.db);database.create_visit(cid,'PC','T','2026-11-01',{'understood':1,'scan':1},'A',path=self.db);database.delete_customer(cid,self.db)
        self.assertEqual(database.search_visits('',self.db),[])
    def test_sqlite_backup_contains_committed_records(self):
        database.upsert_customer('Backup Example','555-2222',path=self.db)
        backup=Path(self.tmp.name)/'backup.sqlite3';database.backup_database(backup,self.db)
        self.assertEqual(len(database.search_visits('Backup',backup)),0)
        cid=database.upsert_customer('Backup Visit','555-2223',path=self.db)
        database.create_visit(cid,'PC','Tech','2026-11-01',{'understood':1,'scan':1},'Backup Visit',path=self.db)
        database.backup_database(backup,self.db)
        self.assertEqual(len(database.search_visits('Backup Visit',backup)),1)

    def test_connection_closes_and_rolls_back(self):
        with self.assertRaises(RuntimeError):
            with database.connect(self.db) as connection:
                connection.execute("INSERT INTO settings VALUES ('rollback', 'value')")
                raise RuntimeError('abort')
        self.assertEqual(database.get_setting('rollback',path=self.db),'')
        import sqlite3
        with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')

    def test_restore_replaces_data_and_preserves_previous_database(self):
        database.set_setting('marker','original',self.db)
        source=Path(self.tmp.name)/'source.sqlite3'
        database.init_db(source);database.set_setting('marker','restored',source)
        backup=database.restore_database(source,self.db)
        self.assertEqual(database.get_setting('marker',path=self.db),'restored')
        self.assertEqual(database.get_setting('marker',path=backup),'original')

    def test_same_file_backup_is_rejected(self):
        with self.assertRaises(ValueError):database.backup_database(self.db,self.db)

    def test_invalid_restore_preserves_current_database(self):
        database.set_setting('marker','original',self.db)
        source=Path(self.tmp.name)/'invalid.sqlite3'
        import sqlite3
        with sqlite3.connect(source) as connection:connection.execute('CREATE TABLE unrelated(id)')
        connection.close()
        with self.assertRaises(ValueError):database.restore_database(source,self.db)
        self.assertEqual(database.get_setting('marker',path=self.db),'original')

class ScanTests(unittest.TestCase):
    def test_scan_returns_friendly_structure(self):
        res=scans.run_scan('Memory')
        self.assertIn(res['status'],('good','attention','problem','unknown'))
        self.assertTrue(res['headline']);self.assertTrue(res['explanation'])
    def test_unimplemented_check_does_not_crash(self):
        res=scans.run_scan('Not an implemented check')
        self.assertEqual(res['status'],'unknown')
    def test_additional_local_checks_are_wired(self):
        for name in ('Browser Extensions','Outdated Software','Office and Other Licenses','Quick Speed Test','Disk Space Map'):
            self.assertIn(name,scans.SCANS)
            self.assertIn(scans.run_scan(name)['status'],('good','attention','problem','unknown'))
    def test_cleanup_dry_run_never_deletes(self):
        res=cleanup.clean([],consent_cleanup=True,dry_run=True)
        self.assertTrue(res['dry_run']);self.assertEqual(res['deleted'],[])

if __name__=='__main__':unittest.main()
