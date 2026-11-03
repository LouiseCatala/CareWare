"""Manual integration test: python tests/smoke_webview.py (Windows desktop)."""
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import webview
from core import database
from desktop import DesktopAPI

outcome=[]
with tempfile.TemporaryDirectory() as tmp:
    database.DB_PATH=Path(tmp)/'smoke.sqlite3'
    api=DesktopAPI()
    window=webview.create_window('CareWare integration test',str(Path(__file__).resolve().parents[1]/'ui/dist/index.html'),js_api=api,width=1000,height=750)
    api._window=window
    def verify():
        finished=threading.Event()
        def complete(result):
            outcome.append(result);finished.set()
        script="""(async () => {
          const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
          for(let i=0; i<100 && !window.pywebview?.api; i++) await wait(100);
          const api=window.pywebview.api;
          if(!api) throw Error('Bridge did not initialize');
          const state=await api.state();
          if(state.history.length) throw Error('Test database is not isolated');
          for(let i=0;i<100 && !document.querySelector('h1');i++) await wait(100);
          if(!document.querySelector('h1')?.textContent.includes('Give your computer')) throw Error('Hero failed to render');
          if([...document.images].some(img=>!img.complete || !img.naturalWidth)) throw Error('Template image failed to load');
          if(!document.querySelector('[data-testid="checks-dashboard"]')) throw Error('Live dashboard missing');
          if(document.querySelector('img[src*="template-dashboard"]')) throw Error('Static CRM image remains');
          const hero=document.querySelector('h1');
          const dashboard=document.querySelector('[data-testid="checks-dashboard"]');
          const sidebar=document.querySelector('nav[aria-label="Dashboard actions"]');
          document.querySelector('button[data-dashboard-page="checks"]').click();
          await wait(200);
          if(!document.querySelector('input[aria-label="Search dashboard checks"]')) throw Error('Checks dashboard navigation failed');
          for(const page of ['cleanup','inspection','report','checks']) {
            sidebar.querySelector('[data-dashboard-page="'+page+'"]').click();
            await wait(150);
            if(document.querySelector('h1')!==hero || !hero.isConnected) throw Error('Main design replaced on '+page);
            if(document.querySelector('[data-testid="checks-dashboard"]')!==dashboard || !sidebar.isConnected) throw Error('Dashboard shell replaced on '+page);
            if(!sidebar.querySelector('[data-dashboard-page="'+page+'"][aria-current="page"]')) throw Error('Wrong active category: '+page);
            if(page!=='checks' && !dashboard.querySelector('[data-panel-content="'+page+'"]')) throw Error('Category escaped bottom panel: '+page);
          }
          document.querySelector('button[data-dashboard-page="cleanup"]').click();
          await wait(200);
          if(!document.body.textContent.includes('Start a checkup')) throw Error('Cleanup consent gate missing');
          dashboard.querySelector('[data-panel-content="cleanup"] button').click();
          await wait(200);
          const form=dashboard.querySelector('[data-panel-content="visit"] form');
          if(!form || document.querySelector('h1')!==hero) throw Error('New checkup escaped bottom panel');
          form.querySelector('[name="name"]').value='Bridge Test';
          form.querySelector('[name="signature"]').value='Bridge Test';
          form.querySelector('[name="service_date"]').value='2026-11-03';
          form.querySelector('[name="understood"]').checked=true;
          form.querySelector('[name="scan"]').checked=true;
          form.requestSubmit();
          for(let i=0;i<100 && !dashboard.querySelector('input[aria-label="Search dashboard checks"]');i++) await wait(100);
          if(!dashboard.querySelector('input[aria-label="Search dashboard checks"]')) throw Error('Checkup did not return to embedded Checks');
          if(!(await api.state()).active) throw Error('Consent form did not save');
          sidebar.querySelector('[data-dashboard-page="cleanup"]').click();
          await wait(150);
          if(!dashboard.querySelector('[data-panel-content="cleanup"]')?.textContent.includes('Preview temporary files')) throw Error('Cleanup tools missing after consent');
          const result=await api.scan(['System Info']);
          if(!JSON.parse(result.active.results_json)['System Info']) throw Error('Scan did not persist');
          for(const page of ['history','reminders','settings']) {
            if(document.querySelector('[data-dashboard-page="'+page+'"]')) throw Error('Header action duplicated in sidebar: '+page);
            const link=document.querySelector('[data-header-page="'+page+'"]');
            if(!link) throw Error('Missing top-right header action: '+page);
            link.click();
            await wait(150);
            if(!document.querySelector('[data-standalone-page="'+page+'"]')) throw Error('Separate page missing: '+page);
            if(document.querySelector('[data-testid="checks-dashboard"]')) throw Error('Standalone page rendered inside dashboard: '+page);
            if(link.getAttribute('aria-current')!=='page') throw Error('Header selection missing: '+page);
            document.querySelector('[data-back-dashboard]').click();
            await wait(150);
            if(!document.querySelector('[data-testid="checks-dashboard"]') || !document.querySelector('h1')?.textContent.includes('Give your computer')) throw Error('Return to dashboard failed');
          }
          return {ok:true,checks:'Header pages for history/reminders/settings; embedded dashboard actions; consent and scan bridge'};
        })().catch(error=>({ok:false,error:String(error)}))"""
        try:
            window.evaluate_js(script,complete)
            if not finished.wait(30):outcome.append({'ok':False,'error':'Integration test timed out'})
        except Exception as exc:outcome.append({'ok':False,'error':str(exc)})
        finally:window.destroy()
    window.events.loaded += verify
    webview.start(gui='edgechromium',http_server=True)
print(outcome)
if not outcome or not outcome[0].get('ok'):sys.exit(1)
