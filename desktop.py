"""Local React desktop shell; diagnostics and storage remain in Python."""
from pathlib import Path
from datetime import date, datetime
import json
import sys
import threading
from core import database, scans, cleanup, report, config


class DesktopAPI:
    def __init__(self):
        database.init_db()
        self._visit = None
        self._lock = threading.Lock()
        self._window = None

    def _active(self):
        with database.connect() as db:
            row = db.execute('SELECT * FROM visits WHERE id=?', (self._visit,)).fetchone()
        if not row or not row['consent_scan']:
            raise ValueError('Start a checkup and record customer consent first.')
        return row

    def state(self):
        from main import NAV_GROUPS
        with database.connect() as db:
            settings = {r['key']: r['value'] for r in db.execute('SELECT key,value FROM settings')}
        rows = database.search_visits()
        active = next((dict(r) for r in rows if r['id'] == self._visit), None)
        return {'active': active, 'groups': {k: [n for n in v if n in scans.SCANS] for k,v in NAV_GROUPS.items()},
                'history': [dict(r) for r in rows], 'reminders': [dict(r) for r in database.reminder_visits()],
                'settings': settings, 'thresholds': {k: config.get_threshold(k) for k in config.DEFAULTS}}

    def create_visit(self, data):
        with self._lock:
            consent = data.get('consent', {})
            if not consent.get('scan') or not consent.get('understood') or not data.get('signature','').strip():
                raise ValueError('Both required permissions and a signature are required.')
            date.fromisoformat(data['service_date'])
            cid = database.upsert_customer(data['name'], data.get('phone',''), data.get('address',''), consent.get('reminders',False))
            self._visit = database.create_visit(cid, data.get('pc',''), data.get('technician',''), data['service_date'], consent, data['signature'], consent_language=data.get('language','English'))
            return self.state()

    def scan(self, names):
        with self._lock:
            visit = self._active()
            if not names or any(n not in scans.SCANS for n in names):
                raise ValueError('Choose supported checks.')
            results = json.loads(visit['results_json'])
            for name in names:
                results[name] = scans.run_scan(name)
                database.save_results(visit['id'], results)
            return self.state()

    def inspection(self, items):
        with self._lock:
            visit = self._active(); results = json.loads(visit['results_json'])
            results['Physical Inspection Checklist'] = {'status':'good','headline':'Physical inspection recorded','explanation':'The technician recorded the visible inspection checklist.','action':'Review observations with the customer.','details':json.dumps(items)}
            database.save_results(visit['id'],results)
            return self.state()

    def preview_cleanup(self):
        self._active()
        return cleanup.preview()

    def clean(self, paths, dry_run=True):
        with self._lock:
            visit = self._active()
            if not dry_run and not self._window.create_confirmation_dialog('Confirm cleanup','Create a Windows restore point and delete the selected old temporary files?'):
                return {'message':'Cleanup cancelled.'}
            result = cleanup.clean(paths, consent_cleanup=bool(visit['consent_cleanup']), dry_run=bool(dry_run))
            if not dry_run: database.set_visit_fields(visit['id'],cleanup_json=result)
            return result

    def export_report(self, visit_id, due=''):
        with self._lock:
            if due: date.fromisoformat(due)
            if visit_id == self._visit: database.set_visit_fields(visit_id,next_due=due)
            pdf, raw = report.export_visit(visit_id)
            return {'message':f'Report saved: {pdf}\nJSON saved: {raw}'}

    def delete_customer(self, customer_id):
        with self._lock:
            if self._window.create_confirmation_dialog('Delete customer','Permanently delete this customer and their checkups from this app? Exported reports and database backups remain on disk; remove those separately if needed.'):
                database.delete_customer(customer_id)
                if not any(r['id']==self._visit for r in database.search_visits()): self._visit=None
            return self.state()

    def mark_contacted(self, visit_id):
        database.set_visit_fields(visit_id,contacted_at=datetime.now().isoformat(timespec='minutes'))
        return self.state()

    def save_settings(self, values, thresholds):
        import math
        allowed={'business_name','tagline','contact_number','website','address','accent_color','footer_message','technician_name','qr_target','logo_path'}
        for k,v in thresholds.items():
            if k not in config.DEFAULTS or not math.isfinite(float(v)) or not 0 <= float(v) <= 10000:
                raise ValueError('Enter valid numeric thresholds between 0 and 10000.')
        for k,v in values.items():
            if k in allowed: database.set_setting(k,v)
        for k,v in thresholds.items(): config.set_threshold(k,v)
        return self.state()

    def database_file(self, action):
        import webview
        with self._lock:
            if action not in ('backup','restore','csv'): raise ValueError('Unknown action')
            mode=webview.FileDialog.OPEN if action=='restore' else webview.FileDialog.SAVE
            selected=self._window.create_file_dialog(mode,save_filename='careware.csv' if action=='csv' else 'careware-backup.sqlite3')
            if not selected: return {'message':'Cancelled.'}
            path=selected[0] if isinstance(selected,(list,tuple)) else selected
            if action=='backup': database.backup_database(path)
            elif action=='csv': database.export_csv(path)
            elif self._window.create_confirmation_dialog('Restore database','Replace current records with this backup? Current records will be backed up first.'):
                database.restore_database(path);self._visit=None
            else: return {'message':'Cancelled.'}
            return {'message':f'{action.title()} complete: {path}'}


def run(preview=False, smoke_output=None):
    from core.runtime import require_webview2
    if not require_webview2():return
    import webview
    import tempfile
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    entry=root/'ui'/'dist'/'index.html'
    if not entry.is_file(): raise RuntimeError('Build the interface first: cd ui && npm install && npm run build')
    temporary=tempfile.TemporaryDirectory() if preview or smoke_output else None
    if temporary: database.DB_PATH=Path(temporary.name)/'preview.sqlite3'
    api=DesktopAPI()
    window=webview.create_window('CareWare - Design Preview' if preview else 'CareWare',str(entry),js_api=api,width=1280,height=900,min_size=(800,600),background_color='#000000')
    api._window=window
    if smoke_output:
        from core.release_check import attach
        attach(window,api,smoke_output)
    try: webview.start(gui='edgechromium',http_server=True)
    finally:
        if temporary: temporary.cleanup()


if __name__=='__main__': run('--preview' in sys.argv)
