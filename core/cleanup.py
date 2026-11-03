"""Conservative temp-file cleanup. Dry-run is default; restoration point is mandatory."""
from __future__ import annotations
import os, platform, subprocess, time, json, uuid
from pathlib import Path
from datetime import datetime, timedelta

def candidates(older_than_days=7):
    if platform.system()!='Windows':return []
    roots=[]
    for v in (os.environ.get('TEMP'),os.environ.get('TMP'),os.path.join(os.environ.get('WINDIR','C:\\Windows'),'Temp')):
        if v and Path(v).is_dir():
            try:roots.append(Path(v).resolve())
            except OSError:pass
    roots=list(dict.fromkeys(roots));cutoff=time.time()-older_than_days*86400;out=[]
    for root in roots:
        try:
            for base,dirs,files in os.walk(root,followlinks=False):
                dirs[:]=[d for d in dirs if not (Path(base)/d).is_symlink()]
                for f in files:
                    p=Path(base)/f
                    try:
                        st=p.lstat()
                        if p.is_symlink() or not p.is_file() or st.st_mtime>cutoff:continue
                        out.append({'path':str(p),'size':st.st_size,'modified':datetime.fromtimestamp(st.st_mtime).isoformat(timespec='minutes')})
                    except OSError:continue
        except (OSError,PermissionError):continue
    return out

def preview():
    rows=candidates()
    return {'files':rows,'bytes':sum(x['size'] for x in rows),'count':len(rows),'dry_run':True}

def create_restore_point():
    if platform.system()!='Windows':return False,'Restore points are available only on Windows.'
    description='CareWare cleanup '+uuid.uuid4().hex
    ps=("$ErrorActionPreference='Stop'; $WarningPreference='Stop'; "
        f"Checkpoint-Computer -Description '{description}' -RestorePointType 'MODIFY_SETTINGS'; "
        f"$point=Get-ComputerRestorePoint | Where-Object {{$_.Description -eq '{description}'}} | Select-Object -Last 1; "
        "if ($null -eq $point) { throw 'Restore point creation could not be verified.' }; "
        "$point | Select-Object Description,SequenceNumber | ConvertTo-Json -Compress")
    try:
        p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',ps],capture_output=True,text=True,timeout=90,shell=False,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        detail=(p.stderr or p.stdout or f'PowerShell exited {p.returncode}')[-2000:]
        if p.returncode!=0 or p.stderr.strip():return False,detail
        try:
            point=json.loads(p.stdout)
            verified=(isinstance(point,dict) and point.get('Description')==description
                      and isinstance(point.get('SequenceNumber'),int) and point['SequenceNumber']>0)
        except (ValueError,TypeError):verified=False
        return verified,detail
    except Exception as e:return False,f'{type(e).__name__}: {e}'

def clean(selected_paths, consent_cleanup=False, dry_run=True):
    if not consent_cleanup:raise PermissionError('Cleanup was not separately authorized in customer consent.')
    if dry_run:return {'deleted':[],'skipped':[],'dry_run':True,'message':'Dry run: no files deleted.'}
    if platform.system()!='Windows':raise OSError('Cleanup is supported only on Windows.')
    roots=[Path(os.environ.get('TEMP','')).resolve(),Path(os.environ.get('TMP','')).resolve(),Path(os.path.join(os.environ.get('WINDIR','C:\\Windows'),'Temp')).resolve()]
    allowed=set()
    for x in candidates():allowed.add(Path(x['path']).resolve())
    requested=[]
    for item in selected_paths:
        p=Path(item)
        try: rp=p.resolve(strict=True)
        except OSError:continue
        if rp in allowed and any(rp.is_relative_to(root) for root in roots):requested.append(rp)
    if not requested:return {'deleted':[],'skipped':[],'dry_run':False,'message':'No eligible selected files.'}
    ok,detail=create_restore_point()
    if not ok:raise RuntimeError('Could not create a Windows restore point; cleanup was cancelled. '+detail)
    deleted=[];skipped=[];bytes_recovered=0
    for p in requested:
        try:
            if p.is_symlink() or not p.is_file():skipped.append(str(p));continue
            size=p.stat().st_size
            p.unlink();deleted.append(str(p));bytes_recovered+=size
        except OSError:skipped.append(str(p))
    return {'deleted':deleted,'skipped':skipped,'dry_run':False,'bytes_recovered':bytes_recovered,'restore_point':True,'message':'Cleanup finished. Review the detailed log.'}
