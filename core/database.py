"""Local-only SQLite storage. No network access or sync is performed."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import contextmanager, closing

APP_DIR = Path.home() / "Documents" / "CareWare"
DB_PATH = APP_DIR / "careware.sqlite3"

@contextmanager
def connect(path: str | Path | None = None):
    p = Path(path) if path else DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(p, timeout=15)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        with db:
            yield db
    finally:
        db.close()

def init_db(path=None):
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS customers(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT DEFAULT '', address TEXT DEFAULT '',
          keep_reminders INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS visits(
          id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
          pc_brand_model TEXT DEFAULT '', technician TEXT DEFAULT '', service_date TEXT NOT NULL,
          consent_understood INTEGER NOT NULL, consent_scan INTEGER NOT NULL, consent_cleanup INTEGER NOT NULL,
          consent_reminders INTEGER NOT NULL, signature TEXT NOT NULL, consent_language TEXT NOT NULL DEFAULT 'English', consent_at TEXT NOT NULL,
          results_json TEXT NOT NULL DEFAULT '{}', health_score INTEGER, cleanup_json TEXT NOT NULL DEFAULT '[]',
          benchmark_json TEXT NOT NULL DEFAULT '{}', report_path TEXT DEFAULT '', next_due TEXT DEFAULT '',
          contacted_at TEXT DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_customer_name ON customers(name);
        CREATE INDEX IF NOT EXISTS idx_visit_customer ON visits(customer_id,service_date);
        ''')
        columns={r['name'] for r in db.execute('PRAGMA table_info(visits)')}
        if 'consent_language' not in columns:db.execute("ALTER TABLE visits ADD COLUMN consent_language TEXT NOT NULL DEFAULT 'English'")

def upsert_customer(name, phone='', address='', reminders=False, path=None):
    name=name.strip()
    if not name: raise ValueError('Customer name is required')
    now=datetime.now().isoformat(timespec='seconds')
    with connect(path) as db:
        row=db.execute('SELECT id FROM customers WHERE name=? AND phone=? ORDER BY id LIMIT 1',(name,phone.strip())).fetchone()
        if row:
            db.execute('UPDATE customers SET address=?,keep_reminders=? WHERE id=?',(address.strip(),int(reminders),row['id']))
            return row['id']
        cur=db.execute('INSERT INTO customers(name,phone,address,keep_reminders,created_at) VALUES(?,?,?,?,?)',(name,phone.strip(),address.strip(),int(reminders),now))
        return cur.lastrowid

def create_visit(customer_id, pc_brand_model, technician, service_date, consent, signature, path=None, consent_language='English'):
    if not consent.get('understood') or not consent.get('scan'): raise ValueError('Required consent is missing')
    if not signature.strip(): raise ValueError('Customer signature is required')
    now=datetime.now().astimezone().isoformat(timespec='seconds')
    with connect(path) as db:
        cur=db.execute('''INSERT INTO visits(customer_id,pc_brand_model,technician,service_date,consent_understood,consent_scan,consent_cleanup,consent_reminders,signature,consent_language,consent_at,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(customer_id,pc_brand_model,technician,service_date,int(consent['understood']),int(consent['scan']),int(consent.get('cleanup',False)),int(consent.get('reminders',False)),signature.strip(),consent_language,now,now))
        db.execute('UPDATE customers SET keep_reminders=? WHERE id=?',(int(consent.get('reminders',False)),customer_id))
        return cur.lastrowid

def save_results(visit_id, results, path=None):
    with connect(path) as db:
        db.execute('UPDATE visits SET results_json=?,health_score=? WHERE id=?',(json.dumps(results,ensure_ascii=False),health_score(results),visit_id))

def health_score(results):
    scores={'good':100,'attention':65,'problem':25,'unknown':50}
    values=[scores.get(x.get('status','unknown'),50) for x in results.values() if isinstance(x,dict)]
    return int(sum(values)/len(values)+0.5) if values else None

def set_visit_fields(visit_id, path=None, **fields):
    allowed={'report_path','next_due','cleanup_json','contacted_at','benchmark_json'}
    updates={k:(json.dumps(v,ensure_ascii=False) if k in {'cleanup_json','benchmark_json'} and not isinstance(v,str) else v) for k,v in fields.items() if k in allowed}
    if not updates:return
    with connect(path) as db:
        db.execute('UPDATE visits SET '+','.join(f'{k}=?' for k in updates)+' WHERE id=?',(*updates.values(),visit_id))

def search_visits(query='',path=None):
    with connect(path) as db:
        q=f'%{query.strip()}%'
        return db.execute('''SELECT v.*,c.name,c.phone,c.address,c.keep_reminders FROM visits v JOIN customers c ON c.id=v.customer_id
        WHERE c.name LIKE ? OR c.phone LIKE ? OR v.pc_brand_model LIKE ? ORDER BY v.service_date DESC,v.id DESC''',(q,q,q)).fetchall()

def reminder_visits(path=None):
    cutoff=(datetime.now().date()+timedelta(days=30)).isoformat()
    with connect(path) as db:
        return db.execute('''SELECT v.*,c.name,c.phone,c.keep_reminders FROM visits v JOIN customers c ON c.id=v.customer_id
        WHERE c.keep_reminders=1 AND v.next_due<>'' AND v.next_due<=? AND v.contacted_at='' ORDER BY v.next_due''',(cutoff,)).fetchall()

def get_setting(key, default='', path=None):
    with connect(path) as db:
        r=db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        return r['value'] if r else default

def set_setting(key,value,path=None):
    with connect(path) as db:
        db.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,str(value)))

def delete_customer(customer_id,path=None):
    with connect(path) as db: db.execute('DELETE FROM customers WHERE id=?',(customer_id,))

def export_csv(dest,path=None):
    import csv
    rows=search_visits('',path)
    fields=['id','name','phone','pc_brand_model','technician','service_date','health_score','next_due','report_path']
    with open(dest,'w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for row in rows:w.writerow({k:row[k] for k in fields})


def backup_database(destination, path=None):
    """Create a transactionally consistent SQLite backup (including WAL data)."""
    destination=Path(destination)
    if destination.resolve()==Path(path or DB_PATH).resolve():
        raise ValueError('Choose a backup location different from the active database.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    target=sqlite3.connect(destination)
    try:
        with connect(path) as source:source.backup(target)
    finally:target.close()
    return destination


def restore_database(source, path=None):
    """Restore through SQLite so committed WAL data is included."""
    source=Path(source).resolve();target=Path(path or DB_PATH).resolve()
    backup=target.with_suffix('.before-restore.sqlite3')
    if source in (target, backup):
        raise ValueError('Copy this database to another location before restoring it.')
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as incoming:
        if incoming.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise ValueError('The backup failed its integrity check.')
        required={'customers':{'id','name','phone','address','keep_reminders','created_at'},
                  'visits':{'id','customer_id','pc_brand_model','technician','service_date',
                            'consent_understood','consent_scan','consent_cleanup','consent_reminders',
                            'signature','consent_at','results_json','health_score','cleanup_json',
                            'benchmark_json','report_path','next_due','contacted_at','created_at'},
                  'settings':{'key','value'}}
        for table, columns in required.items():
            actual={r[1] for r in incoming.execute(f'PRAGMA table_info({table})')}
            if not columns.issubset(actual):
                raise ValueError('The selected file is not a valid CareWare database backup.')
        backup_database(backup,target)
        with connect(target) as destination:
            incoming.backup(destination)
    init_db(target)
    return backup
