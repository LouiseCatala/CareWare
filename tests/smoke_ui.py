"""Run manually on a Windows desktop: python tests/smoke_ui.py."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import database, cleanup
import main

with tempfile.TemporaryDirectory() as tmp:
    database.DB_PATH = Path(tmp) / 'smoke.sqlite3'
    app = main.CareWareApp()
    app.withdraw()
    errors = []
    app.report_callback_exception = lambda *args: errors.append(str(args[1]))
    try:
        for page in ('Welcome', 'Checks', 'Customer Details and Consent', 'Customer History', 'Service Reminders', 'Settings'):
            app.navigate(page)
            app.update()
        app.customer_id = database.upsert_customer('UI Test')
        app.visit_id = database.create_visit(app.customer_id, 'PC', 'Test', '2026-11-02', {'understood': True, 'scan': True}, 'UI Test')
        app.consent_given = True
        for page in ('Physical Inspection Checklist', 'Memory', 'Report', 'Junk File Scan and Cleanup', 'Disk Space Map'):
            app.navigate(page)
            app.update()
        app.navigate('Junk File Scan and Cleanup')
        with patch.object(cleanup, 'preview', return_value={'files': [{'path': 'C:/Temp/test.tmp', 'size': 100}], 'count': 1, 'bytes': 100}), patch.object(main.messagebox, 'showerror', side_effect=lambda *a: errors.append(str(a))):
            app.preview_cleanup()
            app.update()
        assert len(app.clean_choices) == 1
        app.scan_running = True
        current = app.current
        with patch.object(main.messagebox, 'showinfo'):
            app.show_consent()
        assert app.current == current
        app.scan_running = False
        app.current = 'Welcome'
        app.result_queue.put(('Memory', {'status': 'good', 'headline': 'Test'}))
        app.poll_queue()
        assert 'Memory' in app.results
        for theme in ('light', 'dark'):
            main.ctk.set_appearance_mode(theme)
            app.geometry('1100x720')
            for page in ('Welcome', 'Checks', 'Customer Details and Consent', 'Settings'):
                app.navigate(page)
                app.update()
        assert not errors, errors
        print('UI pages, cleanup preview, visit guard, and result persistence passed')
    finally:
        app.destroy()
