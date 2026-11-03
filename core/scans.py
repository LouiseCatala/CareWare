"""Read-only local diagnostics; subprocesses use timeouts and capture output."""
from __future__ import annotations
import json, platform, subprocess
import psutil
from . import config, translator
TIMEOUT=30

def run_command(args,timeout=TIMEOUT):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=timeout,shell=False,errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return {'ok':p.returncode==0,'returncode':p.returncode,'stdout':p.stdout[-20000:],'stderr':p.stderr[-4000:]}
    except Exception as e:return {'ok':False,'returncode':None,'stdout':'','stderr':f'{type(e).__name__}: {e}'}
def powershell(script,timeout=TIMEOUT):
    if platform.system()!='Windows':return {'ok':False,'stdout':'','stderr':'This check is available on Windows only.','returncode':None}
    return run_command(['powershell.exe','-NoProfile','-NonInteractive','-Command',"$ErrorActionPreference='Stop'; "+script],timeout)
def _result(status,title,explanation,action,details=None):return translator.result_card(status,title,explanation,action,details or '')
def _windows_only():return _result('unknown','Check available on Windows only','This check needs Windows tools and is not available on this computer.','Run CareWare on Windows.')

def scan_system_info():
    info={'os':platform.platform(),'computer':platform.node(),'architecture':platform.machine(),'processor':platform.processor(),'cpu_cores':psutil.cpu_count(logical=False),'cpu_threads':psutil.cpu_count(),'ram_gb':round(psutil.virtual_memory().total/1024**3,1)}
    return _result('good','Basic computer details collected','We read the operating system version and main hardware details.','Review the computer details with the customer.',json.dumps(info,indent=2))
def scan_storage():
    lines=[];issues=[];readable=0;complete=True
    for p in psutil.disk_partitions(all=False):
        try:
            u=psutil.disk_usage(p.mountpoint);free_pct=100*u.free/u.total;readable+=1;lines.append(f'{p.device} {p.fstype}: {u.free/1024**3:.1f} GB free of {u.total/1024**3:.1f} GB ({free_pct:.0f}% free)')
            if free_pct<config.get_threshold('storage_low_space_percent'):issues.append(p.device)
        except (PermissionError,OSError,ZeroDivisionError):complete=False;lines.append(f'{p.device}: usage unavailable')
    physical=''
    if platform.system()=='Windows':
        r=powershell('Get-PhysicalDisk | Select FriendlyName,MediaType,HealthStatus,OperationalStatus,Size | ConvertTo-Json -Compress');physical=r['stdout'] if r['ok'] else r['stderr']
        try:
            disks=json.loads(r['stdout'] or '[]');disks=disks if isinstance(disks,list) else [disks]
            if not r['ok'] or not disks:complete=False
            for d in disks:
                health=str(d.get('HealthStatus','')).lower()
                if health in ('unknown',''):complete=False
                elif health!='healthy':issues.append(str(d.get('FriendlyName','disk')))
        except (ValueError,TypeError,AttributeError):complete=False
    details='\n'.join(lines)+('\nPhysical drive health:\n'+physical if physical else '')
    if not issues and (not readable or not complete):return _result('unknown','Storage check is incomplete','Some drive information could not be read.','Review the available details and retry with appropriate permissions.',details)
    return _result('attention','Storage needs a closer look','A drive has limited free space or reported a health warning.','Review the drive before recommending cleanup or replacement.',details) if issues else _result('good','No storage warning found','We checked available space and, on Windows, requested the drive health status.','No storage action is indicated by these checks.',details or 'No fixed drives were reported.')
def scan_processor():
    usage=psutil.cpu_percent(interval=1,percpu=True);freq=psutil.cpu_freq();procs=[]
    for p in psutil.process_iter(['name','cpu_percent']):
        try:procs.append((p.info.get('cpu_percent') or 0,p.info.get('name') or 'Unknown'))
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    procs=sorted(procs,reverse=True)[:8];avg=sum(usage)/max(1,len(usage));st='attention' if avg>config.get_threshold('cpu_attention_percent') else 'good'
    return _result(st,'Processor use is high' if st=='attention' else 'Processor check complete',f'Average processor use during this short check was {avg:.0f}%.','Close unnecessary apps and repeat the check.' if st=='attention' else 'No action is needed based on this quick reading.',f'Per-core use: {usage}\nFrequency MHz: {freq.current if freq else "not available"}\nTop processes: {procs}')
def scan_memory():
    m=psutil.virtual_memory();st='attention' if m.percent>=config.get_threshold('memory_attention_percent') else 'good'
    return _result(st,'Memory use is high' if st=='attention' else 'Memory check complete',f'{m.percent:.0f}% of {m.total/1024**3:.1f} GB of memory is currently in use.','Close apps you do not need and check again.' if st=='attention' else 'No action is needed based on this quick reading.',f'Total: {m.total/1024**3:.2f} GB; Available: {m.available/1024**3:.2f} GB; Used: {m.percent:.1f}%')
def scan_battery():
    b=psutil.sensors_battery()
    if not b:return _result('good','No battery detected','This computer does not report a battery.','No action is needed.','Battery data not available.')
    return _result('attention' if b.percent<20 else 'good','Battery charge is low' if b.percent<20 else 'Battery check complete',f'Battery charge is {b.percent:.0f}%.','Connect the charger if appropriate.' if b.percent<20 else 'No action is needed.',f'Plugged in: {b.power_plugged}; seconds left: {b.secsleft}')
def scan_network():
    stats=psutil.net_if_stats();rows=[f'{n}: up={s.isup}, speed={s.speed} Mbps' for n,s in stats.items()]
    return _result('good','Network adapters found','We listed the network connections visible to this computer.','Ask the customer before changing any network settings.','\n'.join(rows))
def scan_running():
    data=[]
    for p in psutil.process_iter(['pid','name','memory_info']):
        try:data.append((p.info['memory_info'].rss if p.info['memory_info'] else 0,p.info['pid'],p.info['name']))
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    data.sort(reverse=True)
    return _result('good','Running programs listed','These are the programs using the most memory right now.','Review unfamiliar programs with the customer before closing anything.','\n'.join(f'{name} (PID {pid}): {mem/1024**2:.0f} MB' for mem,pid,name in data[:20]))
def scan_startup():
    if platform.system()!='Windows':return _windows_only()
    r=powershell('Get-CimInstance Win32_StartupCommand | Select Name,Command,Location,User | Format-List')
    return _result('good' if r['ok'] else 'unknown','Startup items listed' if r['ok'] else 'We could not read startup items','These programs may start when Windows opens.','Do not disable items without the customer’s approval.',r['stdout'] or r['stderr'])
def scan_defender():
    if platform.system()!='Windows':return _windows_only()
    r=powershell('Get-MpComputerStatus | Select AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureLastUpdated | ConvertTo-Json -Compress')
    if not r['ok']:return _result('unknown','We could not read antivirus status','Windows did not provide Defender status.','Check Windows Security manually.',r['stderr'])
    try:d=json.loads(r['stdout']);enabled=bool(d.get('AntivirusEnabled')) and bool(d.get('RealTimeProtectionEnabled'))
    except Exception:d={};enabled=False
    return _result('good' if enabled else 'attention','Antivirus protection is on' if enabled else 'Check antivirus protection','We checked the built-in Windows antivirus status.','Review Windows Security if protection is off.',json.dumps(d,indent=2))
def scan_firewall():
    if platform.system()!='Windows':return _windows_only()
    r=powershell('Get-NetFirewallProfile | Select Name,Enabled | ConvertTo-Json -Compress')
    if not r['ok']:return _result('unknown','We could not read firewall status','Windows did not provide firewall status.','Check Windows Security manually.',r['stderr'])
    try:
        d=json.loads(r['stdout']);d=d if isinstance(d,list) else [d]
        if not d or any(not isinstance(x,dict) or type(x.get('Enabled')) is not bool for x in d):raise ValueError('Missing profile state')
        enabled=all(x['Enabled'] for x in d)
    except (ValueError,TypeError):return _result('unknown','Firewall status is unavailable','Windows did not return usable firewall profiles.','Check Windows Security manually.',r['stdout'])
    return _result('good' if enabled else 'attention','Firewall is on' if enabled else 'Review firewall settings','We checked the firewall status for available profiles.','Review Windows Security if any profile is off.',json.dumps(d,indent=2))
def scan_updates():
    if platform.system()!='Windows':return _windows_only()
    r=powershell('Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10 HotFixID,Description,InstalledOn | Format-Table -AutoSize')
    return _result('good' if r['ok'] else 'unknown','Recent updates listed','We read the most recently installed Windows updates.','Use Windows Update to check for pending updates.',r['stdout'] if r['ok'] else r['stderr'])
def scan_sfc_verify():
    if platform.system()!='Windows':return _windows_only()
    r=run_command(['sfc.exe','/verifyonly'],timeout=180)
    text=r['stdout']+'\n'+r['stderr']
    status='good' if r['ok'] and 'did not find any integrity violations' in text.lower() else 'unknown'
    if 'found integrity violations' in text.lower() or 'found corrupt files' in text.lower():status='attention'
    return _result(status,'Windows file check finished','Review the read-only System File Checker result; unrecognized or localized output requires manual review.','Review technical output; repair is not run automatically.',text)

def scan_temperature():
    if platform.system()!='Windows':return _windows_only()
    r=powershell('Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | Select InstanceName,CurrentTemperature | ConvertTo-Json -Compress')
    if not r['ok'] or not r['stdout'].strip():return _result('unknown','Temperature sensor not available','Windows did not provide a temperature reading on this computer.','No temperature conclusion can be made from this check.',r['stderr'] or 'No thermal-zone sensor was returned.')
    try:
        vals=json.loads(r['stdout']);vals=vals if isinstance(vals,list) else [vals];celsius=[round((float(x['CurrentTemperature'])/10)-273.15,1) for x in vals if x.get('CurrentTemperature')]
    except Exception:celsius=[]
    if not celsius:return _result('unknown','Temperature sensor not available','Windows did not provide a usable temperature reading.','Use a supported sensor tool if a temperature check is needed.',r['stdout'])
    high=max(celsius)
    if high>=config.get_threshold('temperature_problem_c'):status='problem';headline='A temperature reading is very high';action='Stop heavy work and arrange a careful cooling-system inspection.'
    elif high>=config.get_threshold('temperature_attention_c'):status='attention';headline='A temperature reading is warm';action='Check vents, fans, and airflow; repeat the reading after the computer cools.'
    else:status='good';headline='Temperature readings are within the set range';action='No temperature action is indicated by this reading.'
    return _result(status,headline,f'The highest Windows thermal-zone reading was {high:.1f} °C. This may not represent CPU or GPU temperature.',action,'Readings °C: '+str(celsius))
def scan_junk_preview():
    from . import cleanup
    if platform.system()!='Windows':return _windows_only()
    rows=cleanup.preview()
    if not rows['count']:return _result('good','No older temporary files found','The safe preview found no eligible old temporary files.','No cleanup is needed.','Items: 0; estimated size: 0 MB. Dry run; nothing deleted.')
    return _result('attention','Temporary files are available to review',f"The preview found {rows['count']} files in approved temporary folders, about {rows['bytes']/1024**2:.1f} MB in total.",'Review each item; cleanup requires separate customer permission and an explicit confirmation.',f"Candidate count: {rows['count']}\nBytes: {rows['bytes']}\nDry run: yes; nothing deleted.")

SCANS={'System Info':scan_system_info,'Storage Health':scan_storage,'Processor':scan_processor,'Memory':scan_memory,'Power and Battery':scan_battery,'Internet and Wi-Fi':scan_network,'Running Programs':scan_running,'Startup Programs':scan_startup,'Antivirus and Defender':scan_defender,'Firewall':scan_firewall,'Windows Updates':scan_updates,'System File Check':scan_sfc_verify,'Temperatures and Fans':scan_temperature,'Junk File Scan and Cleanup':scan_junk_preview}
PS_CHECKS={
 'BIOS and Motherboard':("Get-CimInstance Win32_BIOS | Select Manufacturer,SMBIOSBIOSVersion,ReleaseDate; Get-CimInstance Win32_BaseBoard | Select Manufacturer,Product,SerialNumber | Format-List",'BIOS and motherboard details collected','We read the BIOS and motherboard information Windows makes available.'),
 'Windows Activation and License':("Get-CimInstance SoftwareLicensingProduct | Where-Object {$_.PartialProductKey -and $_.Name -like '*Windows*'} | Select Name,Description,LicenseStatus,PartialProductKey | Format-List",'Windows license information collected','We read Windows activation status and only the partial key Windows exposes.'),
 'Boot Time and Uptime':("Get-CimInstance Win32_OperatingSystem | Select LastBootUpTime,LocalDateTime | Format-List",'Recent startup time collected','We read when Windows last started.'),
 'Graphics Card':("Get-CimInstance Win32_VideoController | Select Name,DriverVersion,DriverDate,AdapterRAM,Status | Format-List",'Graphics details collected','We read the graphics device and driver details available through Windows.'),
 'Display and Monitors':("Get-CimInstance Win32_DesktopMonitor | Select Name,ScreenWidth,ScreenHeight,Status | Format-List",'Display details collected','We read the display details Windows reports.'),
 'Audio Devices':("Get-CimInstance Win32_SoundDevice | Select Name,Manufacturer,Status | Format-List",'Audio devices listed','We read audio devices visible to Windows.'),
 'USB and Connected Devices':("Get-PnpDevice -PresentOnly | Where-Object {$_.Class -in @('USB','HIDClass')} | Select Class,FriendlyName,Status | Format-Table -AutoSize",'Connected devices listed','We read names and status of currently present USB and input devices.'),
 'Bluetooth and Webcam':("Get-PnpDevice -PresentOnly | Where-Object {$_.Class -match 'Bluetooth|Camera|Image'} | Select Class,FriendlyName,Status | Format-Table -AutoSize",'Camera and Bluetooth devices listed','We read available camera and Bluetooth device names and status.'),
 'Driver Check':("Get-CimInstance Win32_PnPSignedDriver | Select-Object -First 300 DeviceName,DriverVersion,DriverDate,IsSigned | Format-Table -AutoSize",'Driver details collected','We read driver names, versions, dates, and signing status.'),
 'Devices With Problems':("Get-CimInstance Win32_PnPEntity | Where-Object {$_.ConfigManagerErrorCode -ne 0} | Select Name,ConfigManagerErrorCode,Status | Format-Table -AutoSize",'Device status check complete','We checked whether Windows reports a problem with a device.'),
 'Windows Image Health':("DISM.exe /Online /Cleanup-Image /CheckHealth",'Windows image check finished','We ran the read-only Windows image health check. No repair was started.'),
 'Disk Error Check':("Get-Volume | Select DriveLetter,FileSystem,HealthStatus,OperationalStatus,SizeRemaining,Size | Format-Table -AutoSize",'Drive status collected','We read the drive status Windows reports; no disk repair was scheduled.'),
 'Crashes and Blue Screens':("Get-WinEvent -FilterHashtable @{LogName='System';Id=41,1001;StartTime=(Get-Date).AddDays(-30)} -MaxEvents 50 -ErrorAction SilentlyContinue | Select TimeCreated,Id,ProviderName,Message | Format-List",'Recent crash records collected','We looked for common Windows crash and restart records from the last 30 days.'),
 'Event Log Errors':("Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;StartTime=(Get-Date).AddDays(-7)} -MaxEvents 60 -ErrorAction SilentlyContinue | Select TimeCreated,ProviderName,Id,LevelDisplayName,Message | Format-List",'Recent Windows errors collected','We reviewed recent critical and error records from the System log.'),
 'Pending Restart Check':("$p=@('HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending','HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired'); foreach($x in $p){if(Test-Path $x){$x}}",'Restart status checked','We checked common Windows markers that indicate a restart may be pending.'),
 'Background Services':("Get-Service | Where-Object {$_.Status -ne 'Running' -and $_.StartType -eq 'Automatic'} | Select-Object -First 100 Name,DisplayName,Status,StartType | Format-Table -AutoSize",'Automatic services reviewed','We listed automatic services that are not running; Windows may stop some services normally.'),
 'Scheduled Tasks':("Get-ScheduledTask | Where-Object {$_.State -eq 'Disabled' -or $_.TaskPath -notlike '\\Microsoft\\*'} | Select-Object -First 100 TaskName,TaskPath,State,Author | Format-Table -AutoSize",'Scheduled tasks listed','We listed selected tasks for technician review; nothing was changed.'),
 'Network Adapters':("Get-NetIPConfiguration | Select InterfaceAlias,InterfaceDescription,IPv4Address,IPv4DefaultGateway,DNSServer | Format-List",'Network adapter details collected','We read network configuration already present on this computer.'),
 'DNS and Connection Check':("Get-NetIPConfiguration | Select InterfaceAlias,IPv4Address,IPv4DefaultGateway,DNSServer | Format-List; Get-DnsClientServerAddress -AddressFamily IPv4 | Select InterfaceAlias,ServerAddresses | Format-List",'Local network settings collected','We read network and DNS settings already stored on this computer. CareWare did not contact an internet service.'),
 'Open Ports and Sharing':("Get-NetTCPConnection -State Listen | Select-Object -First 100 LocalAddress,LocalPort,OwningProcess | Format-Table -AutoSize; Get-SmbServerConfiguration | Select EnableSMB1Protocol",'Listening ports reviewed','We listed listening network ports and checked SMBv1; no network settings were changed.'),
 'Threat History':("Get-MpThreatDetection | Select-Object -First 50 InitialDetectionTime,ThreatName,ActionSuccess,Resources | Format-List",'Windows threat history collected','We read threat detections that Windows Defender makes available.'),
 'Secure Boot TPM and Encryption':("Confirm-SecureBootUEFI -ErrorAction SilentlyContinue; Get-Tpm | Select TpmPresent,TpmReady,ManufacturerVersion; Get-BitLockerVolume -ErrorAction SilentlyContinue | Select MountPoint,VolumeStatus,ProtectionStatus",'Security hardware status collected','We read Secure Boot, TPM, and BitLocker status where supported.'),
 'User Accounts and Admin Rights':("Get-LocalUser | Select Name,Enabled,PasswordRequired,LastLogon | Format-Table -AutoSize; whoami /groups",'Local account settings collected','We listed local account status and current technician group memberships.'),
 'Remote Access Settings':("Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server' -Name fDenyTSConnections | Select fDenyTSConnections; Get-NetFirewallRule -DisplayGroup 'Remote Desktop' -ErrorAction SilentlyContinue | Select DisplayName,Enabled,Profile",'Remote access setting checked','We read whether Remote Desktop appears enabled and its firewall rule status.'),
 'Installed Programs':("Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*,HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* -ErrorAction SilentlyContinue | Where-Object DisplayName | Select-Object -First 300 DisplayName,DisplayVersion,Publisher,InstallDate | Format-Table -AutoSize",'Installed programs listed','We read installed program names, versions, publishers, and dates Windows reports.'),
}
def scan_ps_check(name):
    script,headline,explanation=PS_CHECKS[name];r=powershell(script,timeout=75)
    if not r['ok']:return _result('unknown','We could not read this information on this computer','Windows did not return a usable result for this check.','Retry or review the relevant Windows settings manually.',r['stderr'] or r['stdout'])
    text=(r['stdout'] or '').strip()
    if name=='Pending Restart Check' and text:return _result('attention','Windows may need a restart','Windows reported a pending restart marker.','Save work and ask the customer before restarting.',text)
    if name=='Devices With Problems' and text:return _result('attention','A device needs a closer look','Windows reported one or more device status issues.','Review the named device in Device Manager.',text)
    if name in ('Pending Restart Check','Devices With Problems') and not text:
        return _result('good',headline,explanation,'No matching warning was reported.',text)
    if name=='Windows Activation and License':
        import re
        states=re.findall(r'LicenseStatus\s*:\s*(\d+)',text)
        if states:return _result('good' if all(s=='1' for s in states) else 'attention',headline,explanation,'Review activation in Windows Settings if any license is not activated.',text)
    if name=='Windows Image Health':
        if 'no component store corruption detected' in text.lower():return _result('good',headline,explanation,'No corruption was reported.',text)
        if 'repairable' in text.lower():return _result('attention',headline,explanation,'Review the result before considering repair.',text)
    # Collected inventory and unparsed security output are not proof of health.
    return _result('unknown',headline,explanation,'Manual review required; collecting these details does not establish a passing health result.',text or 'Windows returned no matching items.')
for _name in PS_CHECKS:SCANS[_name]=lambda n=_name:scan_ps_check(n)
def run_scan(name):
    fn=SCANS.get(name)
    if not fn:return _result('unknown','This check is not implemented yet',f'{name} is listed in the app but has not been enabled in this build.','No system changes were made.')
    try:return fn()
    except Exception as e:return _result('unknown','We could not read this information on this computer','The check stopped safely instead of showing a technical error in the result card.','Retry or inspect technical details.',f'{type(e).__name__}: {e}')
def quick_scan():
    return {n:run_scan(n) for n in ['System Info','Storage Health','Temperatures and Fans','Antivirus and Defender','Startup Programs','Junk File Scan and Cleanup']}

from .additional_scans import ADDITIONAL_SCANS
SCANS.update(ADDITIONAL_SCANS)


def scan_quick_speed():
    import time, hashlib
    start=time.perf_counter();acc=0
    for i in range(600000):acc=(acc+i*31)%1000003
    cpu_s=max(time.perf_counter()-start,1e-6)
    block=bytearray(8*1024*1024);start=time.perf_counter();digest=hashlib.sha256(block).hexdigest();mem_s=max(time.perf_counter()-start,1e-6)
    return _result('good','Quick processor and memory check complete',f'The in-memory check processed a short CPU workload in {cpu_s:.2f} seconds and 8 MB of memory in {mem_s:.2f} seconds. This is a simple comparison, not a full benchmark.','Repeat under similar conditions for a before-and-after comparison. This check does not write benchmark files or test disk speed.',f'CPU loop result: {acc}; memory SHA-256: {digest}; CPU seconds: {cpu_s:.4f}; memory seconds: {mem_s:.4f}')

def scan_disk_map():
    rows=[]
    for p in psutil.disk_partitions(all=False):
        try:
            u=psutil.disk_usage(p.mountpoint);usedpct=100*u.used/u.total
            rows.append(f'{p.device or p.mountpoint}: {usedpct:.0f}% used ({u.used/1024**3:.1f} GB used; {u.free/1024**3:.1f} GB free of {u.total/1024**3:.1f} GB)')
        except (OSError,PermissionError):continue
    return _result('good','Drive space summary ready','We summarized used and free space for each readable drive without scanning folders or personal files.','Use Storage Health to review a drive that is nearly full.','\n'.join(rows) or 'No readable drives were returned.')

SCANS['Quick Speed Test']=scan_quick_speed
SCANS['Disk Space Map']=scan_disk_map
SCANS['Browser Safety']=ADDITIONAL_SCANS['Browser Extensions']
