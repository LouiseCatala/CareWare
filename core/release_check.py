"""Opt-in packaged smoke test. Runs only with an isolated preview database."""
import json
import threading
from pathlib import Path
from . import database, report


def attach(window, api, output):
    output=Path(output).resolve()
    def verify():
        finished=threading.Event();result={}
        def complete(value):
            result.update(value);finished.set()
        try:
            window.evaluate_js("""(async()=>{
                const wait=ms=>new Promise(r=>setTimeout(r,ms));
                for(let i=0;i<100&&!window.pywebview?.api;i++)await wait(100);
                const api=window.pywebview.api;
                if((await api.state()).history.length)throw Error('Database is not isolated');
                for(let i=0;i<100&&!document.querySelector('h1');i++)await wait(100);
                const hero=document.querySelector('h1');
                if(!hero?.textContent.includes('Give your computer'))throw Error('Hero missing');
                if([...document.images].some(i=>!i.complete||!i.naturalWidth))throw Error('Image missing');
                for(const page of ['cleanup','inspection','report','checks']){
                    document.querySelector('[data-dashboard-page="'+page+'"]').click();await wait(150);
                    if(document.querySelector('h1')!==hero)throw Error('Design replaced');
                }
                for(const page of ['history','reminders','settings']){
                    document.querySelector('[data-header-page="'+page+'"]').click();await wait(150);
                    if(!document.querySelector('[data-standalone-page="'+page+'"]'))throw Error('Header page missing');
                    if(page==='history'&&![...document.querySelectorAll('button')].some(button=>button.textContent?.trim()==='Export CSV'))throw Error('History CSV export missing');
                    document.querySelector('[data-back-dashboard]').click();await wait(150);
                }
                await api.create_visit({name:'Packaged smoke test',signature:'Test',service_date:'2026-11-03',consent:{understood:true,scan:true}});
                const state=await api.scan(['System Info']);
                if(!JSON.parse(state.active.results_json)['System Info'])throw Error('Scan persistence failed');
                return {ok:true,checks:'UI, images, bottom categories, header pages, consent, scan persistence'};
            })().catch(e=>({ok:false,error:String(e)}))""",complete)
            if not finished.wait(40):raise RuntimeError('Packaged UI test timed out')
            if result.get('ok'):
                paths=report.export_visit(api._visit,database.DB_PATH.parent/'reports')
                if not all(Path(p).is_file() for p in paths):raise RuntimeError('Report export failed')
                result['report_export']=True
        except Exception as exc:result={'ok':False,'error':str(exc)}
        finally:
            output.write_text(json.dumps(result,indent=2),encoding='utf-8')
            window.destroy()
    window.events.loaded+=verify
