"""CareWare desktop application. Windows 10/11; local-only data handling."""
from __future__ import annotations
import os, sys, json, queue, threading, shutil, csv, sqlite3
from pathlib import Path
from datetime import date, datetime, timedelta
import customtkinter as ctk
from tkinter import messagebox, filedialog
from core import database, scans, cleanup, report, config

APP_TITLE='CareWare'
NAV_GROUPS={
 'START':['Welcome','Customer Details and Consent','Physical Inspection Checklist'],
 'COMPUTER':['System Info','BIOS and Motherboard','Windows Activation and License','Boot Time and Uptime'],
 'HARDWARE':['Processor','Graphics Card','Memory','Storage Health','Temperatures and Fans','Power and Battery','Display and Monitors','Audio Devices','USB and Connected Devices','Bluetooth and Webcam'],
 'DRIVERS':['Driver Check','Devices With Problems'],
 'WINDOWS HEALTH':['System File Check','Windows Image Health','Disk Error Check','Crashes and Blue Screens','Event Log Errors','Windows Updates','Pending Restart Check'],
 'PERFORMANCE':['Quick Speed Test','Running Programs','Background Services','Startup Programs','Scheduled Tasks'],
 'NETWORK':['Internet and Wi-Fi','Network Adapters','Speed and Latency Test','DNS and Connection Check','Open Ports and Sharing'],
 'SECURITY':['Antivirus and Defender','Firewall','Threat History','Secure Boot TPM and Encryption','User Accounts and Admin Rights','Remote Access Settings','Browser Safety'],
 'SOFTWARE':['Installed Programs','Bloatware and Unwanted Apps','Outdated Software','Browser Extensions','Office and Other Licenses'],
 'CLEANUP':['Junk File Scan and Cleanup','Large Files Finder','Duplicate Files Finder','Disk Space Map'],
 'FINISH':['Report','Customer History','Service Reminders','Settings']}
DESCRIPTIONS={
'System Info':'Reads the Windows version and basic computer details. It does not change anything.',
'Storage Health':'Checks available disk space and, when Windows provides it, reported drive health. It does not change or delete files.',
'Processor':'Takes a short, read-only snapshot of processor use and busy programs.',
'Memory':'Reads how much memory is installed, in use, and available.',
'Power and Battery':'Reads the current battery and power status when available.',
'Internet and Wi-Fi':'Lists network connections visible to this computer; it does not change network settings.',
'Running Programs':'Lists currently running programs and their memory use; nothing is closed.',
'Startup Programs':'Lists programs configured to start with Windows; nothing is disabled.',
'Antivirus and Defender':'Reads the built-in Windows antivirus status when available.',
'Firewall':'Reads Windows Firewall profile status.',
'Windows Updates':'Lists recent installed updates; it does not install or remove updates.',
'System File Check':'Runs the read-only Windows system file verification check. Repair is not automatic.'}
BG=('#F3F6F8','#101B26')
SURFACE=('#FFFFFF','#192835')
INK=('#183042','#ECF4F8')
MUTED=('#657988','#A5B8C5')
SOFT=('#EAF1F4','#223744')
ACCENT='#087F8C'

STATUS_COLORS={'good':'#1F9D68','attention':'#B7791F','problem':'#C53030','unknown':'#657988'}

class CareWareApp(ctk.CTk):
 def __init__(self):
  super().__init__();database.init_db();self.title('CareWare — PC Care Assistant');self.geometry('1280x820');self.minsize(1100,720)
  self.configure(fg_color=BG);self.consent_given=False;self.visit_id=None;self.customer_id=None;self.results={};self.current='Welcome';self.result_queue=queue.Queue();self.scan_running=False;self.theme=database.get_setting('theme','light');ctk.set_appearance_mode(self.theme)
  self.nav=ctk.CTkFrame(self,width=220,fg_color='#142C3A',corner_radius=0);self.nav.pack(side='left',fill='y');self.nav.pack_propagate(False)
  self.main=ctk.CTkFrame(self,fg_color=BG,corner_radius=0);self.main.pack(side='right',fill='both',expand=True)
  self.build_nav();self.show_welcome();self.after(150,self.poll_queue)
 def build_nav(self):
  ctk.CTkLabel(self.nav,text='+  CareWare',font=ctk.CTkFont(family='Segoe UI',size=25,weight='bold'),text_color='white').pack(anchor='w',padx=23,pady=(32,0))
  ctk.CTkLabel(self.nav,text='A little care. A better PC.',font=ctk.CTkFont(size=11),text_color='#9CB7C6').pack(anchor='w',padx=25,pady=(2,34))
  self.nav_buttons={}
  for label,target in [('Overview','Welcome'),('New visit','Customer Details and Consent'),('Computer checks','Checks'),('Cleanup','Junk File Scan and Cleanup'),('Report','Report'),('Visit history','Customer History'),('Reminders','Service Reminders')]:
   button=ctk.CTkButton(self.nav,text=label,anchor='w',height=43,corner_radius=9,fg_color='transparent',hover_color='#254858',text_color='#D6E5EC',font=ctk.CTkFont(size=13),command=lambda x=target:self.navigate(x))
   button.pack(fill='x',padx=14,pady=3);self.nav_buttons[target]=button
  ctk.CTkLabel(self.nav,text='LOCAL STORAGE\nYour data stays on this PC.',justify='left',font=ctk.CTkFont(size=11),text_color='#9CB7C6').pack(side='bottom',anchor='w',padx=25,pady=24)
  button=ctk.CTkButton(self.nav,text='Settings',anchor='w',height=43,fg_color='transparent',hover_color='#254858',text_color='#D6E5EC',command=lambda:self.navigate('Settings'))
  button.pack(side='bottom',fill='x',padx=14,pady=3);self.nav_buttons['Settings']=button
 def highlight_nav(self):
  selected=self.current
  if selected not in self.nav_buttons:selected='Checks'
  for name,button in self.nav_buttons.items():button.configure(fg_color=ACCENT if name==selected else 'transparent',text_color='white' if name==selected else '#D6E5EC')
 def clear(self):
  for w in self.main.winfo_children():w.destroy()
 def header(self,title,subtitle='',description=''):
  self.highlight_nav()
  top=ctk.CTkFrame(self.main,fg_color='transparent');top.pack(fill='x',padx=32,pady=(26,4))
  ctk.CTkLabel(top,text='YOUR PC CARE WORKSPACE',font=ctk.CTkFont(size=10,weight='bold'),text_color=ACCENT).pack(side='left')
  ctk.CTkLabel(top,text=f'Visit #{self.visit_id}  /  Active' if self.visit_id else 'Ready for a new visit',font=ctk.CTkFont(size=11),text_color=MUTED).pack(side='right')
  ctk.CTkLabel(self.main,text=title,font=ctk.CTkFont(family='Segoe UI',size=29,weight='bold'),text_color=INK).pack(anchor='w',padx=32)
  caption=' '.join(x for x in (subtitle,description) if x)
  if caption:ctk.CTkLabel(self.main,text=caption,font=ctk.CTkFont(size=13),text_color=MUTED,wraplength=800,justify='left').pack(anchor='w',padx=32,pady=(3,22))
 def card(self):
  f=ctk.CTkScrollableFrame(self.main,fg_color=SURFACE,corner_radius=14);f.pack(fill='both',expand=True,padx=32,pady=(0,26));return f
 def navigate(self,name):
  if self.scan_running:messagebox.showinfo('Scan in progress','Wait for the current scan to finish before changing pages.');return
  self.current=name
  if name in ('Welcome','Customer Details and Consent'):self.show_welcome() if name=='Welcome' else self.show_consent();return
  if name=='Checks':self.show_checks();return
  if not self.consent_given and name not in ('Settings','Customer History','Service Reminders'):
   messagebox.showinfo('Consent required','Please complete the customer consent first.');self.show_consent();return
  if name in ('Customer History','Report','Service Reminders','Settings','Physical Inspection Checklist','Junk File Scan and Cleanup','Large Files Finder','Duplicate Files Finder','Disk Space Map'):
   {'Customer History':self.show_history,'Report':self.show_report,'Service Reminders':self.show_reminders,'Settings':self.show_settings,'Physical Inspection Checklist':self.show_inspection,'Junk File Scan and Cleanup':self.show_cleanup,'Large Files Finder':self.show_large_files,'Duplicate Files Finder':self.show_duplicate,'Disk Space Map':self.show_disk_map}[name]();return
  self.show_scan_page(name)
 def show_welcome(self):
  self.current='Welcome';self.clear();self.header('Good care starts here.','One place to check a PC, explain the results, and wrap up a visit.')
  f=self.card()
  hero=ctk.CTkFrame(f,fg_color=('#E4F4F2','#163E43'),corner_radius=16);hero.pack(fill='x',padx=16,pady=(16,20))
  ctk.CTkLabel(hero,text='A FRESH START FOR EVERY PC',font=ctk.CTkFont(size=11,weight='bold'),text_color=ACCENT).pack(anchor='w',padx=26,pady=(24,8))
  ctk.CTkLabel(hero,text='A healthier PC. A happier customer.',font=ctk.CTkFont(size=25,weight='bold'),text_color=INK).pack(anchor='w',padx=26)
  ctk.CTkLabel(hero,text='Start with consent, then let CareWare guide the checkup.',font=ctk.CTkFont(size=13),text_color=MUTED).pack(anchor='w',padx=26,pady=(7,18))
  ctk.CTkButton(hero,text='Run quick scan  \u2192' if self.consent_given else 'Start a new visit  \u2192',height=43,width=200,fg_color=ACCENT,hover_color='#066975',command=self.start_quick_scan if self.consent_given else self.show_consent).pack(anchor='w',padx=26,pady=(0,26))
  row=ctk.CTkFrame(f,fg_color='transparent');row.pack(fill='x',padx=16,pady=(0,20));row.grid_columnconfigure((0,1,2),weight=1,uniform='steps')
  for i,(number,title,body,target) in enumerate([('01','Meet & consent','Customer details and permission.','Customer Details and Consent'),('02','Check the computer','Clear checks. Practical next steps.','Checks'),('03','Share the results','A report your customer can follow.','Report')]):
   tile=ctk.CTkFrame(row,fg_color=BG,corner_radius=12);tile.grid(row=0,column=i,sticky='nsew',padx=(0 if i==0 else 6,0 if i==2 else 6))
   ctk.CTkLabel(tile,text=number,font=ctk.CTkFont(size=21,weight='bold'),text_color=ACCENT).pack(anchor='w',padx=18,pady=(16,8))
   ctk.CTkButton(tile,text=title+'  \u2192',anchor='w',fg_color='transparent',hover_color=SOFT,text_color=INK,font=ctk.CTkFont(size=14,weight='bold'),command=lambda x=target:self.navigate(x)).pack(fill='x',padx=10)
   ctk.CTkLabel(tile,text=body,font=ctk.CTkFont(size=12),text_color=MUTED,wraplength=220,justify='left').pack(anchor='w',padx=18,pady=(4,18))
  ctk.CTkLabel(f,text='Your current visit' if self.visit_id else 'Simple by design',font=ctk.CTkFont(size=17,weight='bold'),text_color=INK).pack(anchor='w',padx=22,pady=(3,6))
  summary=f'{len(self.results)} checks recorded. Continue checking or create your report.' if self.visit_id else 'Read-only checks. Local records. Cleanup only with separate permission.'
  ctk.CTkLabel(f,text=summary,text_color=MUTED,font=ctk.CTkFont(size=13),wraplength=760,justify='left').pack(anchor='w',padx=22,pady=(0,15))
  if self.consent_given:
   actions=ctk.CTkFrame(f,fg_color='transparent');actions.pack(anchor='w',padx=22,pady=(0,20))
   for label,command in [('Full scan',self.start_full_scan),('Choose checks',self.show_custom_scan),('View report',lambda:self.navigate('Report'))]:
    ctk.CTkButton(actions,text=label,height=37,fg_color=SOFT,hover_color=('#D8E8EC','#304B59'),text_color=INK,command=command).pack(side='left',padx=(0,10))
 def show_checks(self):
  self.current='Checks';self.clear();self.header('Computer checks','Find a check below. Customer consent is required before running it.')
  f=self.card();search=ctk.CTkEntry(f,placeholder_text='Search checks: memory, security, storage...',height=42);search.pack(fill='x',padx=18,pady=18)
  results=ctk.CTkFrame(f,fg_color='transparent');results.pack(fill='both',expand=True,padx=12)
  def render(*args):
   for widget in results.winfo_children():widget.destroy()
   query=search.get().strip().lower();count=0
   for group,items in NAV_GROUPS.items():
    names=[n for n in items if (n in scans.SCANS or n=='Physical Inspection Checklist') and (query in n.lower() or query in group.lower())]
    if not names:continue
    count+=len(names)
    ctk.CTkLabel(results,text=group,font=ctk.CTkFont(size=11,weight='bold'),text_color=ACCENT).pack(anchor='w',padx=8,pady=(14,6))
    for name in names:ctk.CTkButton(results,text=name+'   \u2192',anchor='w',height=38,fg_color=BG,hover_color=SOFT,text_color=INK,command=lambda x=name:self.navigate(x)).pack(fill='x',padx=6,pady=3)
   if not count:ctk.CTkLabel(results,text='No matching checks. Try another search.',text_color=MUTED).pack(pady=30)
  search.bind('<KeyRelease>',render);render()
 def show_consent(self):
  if self.scan_running:messagebox.showinfo('Scan in progress','Wait for the current scan before starting another visit.');return
  self.current='Customer Details and Consent';self.clear();self.header('Customer details and consent','Please review this notice together before any computer check begins.')
  f=self.card();f.grid_columnconfigure((0,1),weight=1);self.entries={}
  for i,(label,default) in enumerate([('Customer name',''),('Contact number',''),('Address (optional)',''),('PC brand and model',''),('Technician name',database.get_setting('technician_name','')),('Service date',date.today().isoformat())]):
   c=i%2;r=i//2*2;ctk.CTkLabel(f,text=label,font=ctk.CTkFont(size=12,weight='bold'),text_color=MUTED).grid(row=r,column=c,sticky='w',padx=22,pady=(12,3));e=ctk.CTkEntry(f,height=37,placeholder_text=label);e.insert(0,default);e.grid(row=r+1,column=c,sticky='ew',padx=22);self.entries[label]=e
  ctk.CTkLabel(f,text='Your privacy matters',font=ctk.CTkFont(size=17,weight='bold'),text_color=INK).grid(row=6,column=0,sticky='w',padx=22,pady=(19,6))
  self.consent_notice_en='CareWare checks computer hardware health, Windows health, security settings, installed programs and junk files. It does not read personal files, photos, documents, passwords or browsing history, and does not send data over the internet. Scanning is read-only. Cleanup or repair happens only after separate review and confirmation. Results are saved on this computer for the service report.'
  self.consent_notice_tl='Tinitingnan ng CareWare ang kalusugan ng hardware at Windows, mga security setting, naka-install na programs, at junk files. Hindi nito binabasa ang personal mong files, photos, documents, passwords, o browsing history, at walang data na ipinapadala sa internet. Read-only ang scan. May hiwalay na review at kumpirmasyon bago maglinis o mag-ayos. Lokal lang sa computer na ito ise-save ang resulta para sa service report.'
  self.taglish=ctk.BooleanVar(value=False);ctk.CTkCheckBox(f,text='Basahin sa Taglish',variable=self.taglish,command=self.toggle_consent_language).grid(row=6,column=1,sticky='e',padx=22,pady=(19,6))
  self.notice_label=ctk.CTkLabel(f,text=self.consent_notice_en,wraplength=690,justify='left',font=ctk.CTkFont(size=12),text_color=MUTED);self.notice_label.grid(row=7,column=0,columnspan=2,sticky='w',padx=22,pady=5)
  self.under=ctk.BooleanVar();self.agree=ctk.BooleanVar();self.cleanok=ctk.BooleanVar();self.remind=ctk.BooleanVar()
  for r,(txt,var) in enumerate([('I understand what will be checked',self.under),('I agree to the scan',self.agree),('Optional: I agree to cleanup of junk files after I review the list',self.cleanok),('Optional: I agree to keep my details for future service reminders',self.remind)],start=8):ctk.CTkCheckBox(f,text=txt,variable=var,fg_color=ACCENT).grid(row=r,column=0,columnspan=2,sticky='w',padx=22,pady=5)
  ctk.CTkLabel(f,text='Customer signature — type full name',font=ctk.CTkFont(size=12,weight='bold'),text_color=MUTED).grid(row=12,column=0,sticky='w',padx=22,pady=(16,3));self.sig=ctk.CTkEntry(f,height=38,placeholder_text='Full name');self.sig.grid(row=13,column=0,sticky='ew',padx=22,pady=(0,12));ctk.CTkButton(f,text='Save consent and continue →',height=40,fg_color=ACCENT,command=self.save_consent).grid(row=13,column=1,sticky='e',padx=22)
 def toggle_consent_language(self):self.notice_label.configure(text=self.consent_notice_tl if self.taglish.get() else self.consent_notice_en)
 def save_consent(self):
  if not self.under.get() or not self.agree.get():messagebox.showwarning('Consent needed','Both required consent boxes must be checked.');return
  if not self.sig.get().strip():messagebox.showwarning('Signature needed','Enter the customer’s full name as their signature.');return
  try:
   e=self.entries;name=e['Customer name'].get().strip();phone=e['Contact number'].get().strip()
   if not name:raise ValueError('Customer name is required')
   self.customer_id=database.upsert_customer(name,phone,e['Address (optional)'].get(),self.remind.get())
   self.visit_id=database.create_visit(self.customer_id,e['PC brand and model'].get(),e['Technician name'].get(),e['Service date'].get(),{'understood':self.under.get(),'scan':self.agree.get(),'cleanup':self.cleanok.get(),'reminders':self.remind.get()},self.sig.get(),consent_language='Taglish' if self.taglish.get() else 'English')
   self.consent_given=True;self.results={};self.show_welcome()
  except Exception as ex:messagebox.showerror('Could not save consent',str(ex))
 def show_scan_page(self,name):
  self.clear();self.header(name,DESCRIPTIONS.get(name,'This page is reserved for this check. Checks are read-only unless a separate action is clearly confirmed.'))
  f=self.card();self.run_btn=ctk.CTkButton(f,text='Run check',height=52,width=250,fg_color=ACCENT,font=ctk.CTkFont(size=16,weight='bold'),command=lambda:self.start_scan(name));self.run_btn.pack(pady=(24,12));self.progress=ctk.CTkProgressBar(f,width=460);self.progress.set(0);self.progress.pack_forget();self.resbox=ctk.CTkFrame(f,fg_color='transparent');self.resbox.pack(fill='x',padx=20,pady=12);self.render_result(name)
  ctk.CTkLabel(f,text='Technician: commands and diagnostic details appear below; customer-facing results use plain language.',font=ctk.CTkFont(size=11),text_color=MUTED).pack(anchor='w',padx=22,pady=(15,4))
 def render_result(self,name):
  for w in self.resbox.winfo_children():w.destroy()
  res=self.results.get(name)
  if not res:return
  status=res.get('status','unknown');ctk.CTkLabel(self.resbox,text=f"{status.upper()}  •  {res.get('headline',name)}",font=ctk.CTkFont(size=18,weight='bold'),text_color=STATUS_COLORS.get(status,MUTED)).pack(anchor='w',pady=(5,8));ctk.CTkLabel(self.resbox,text=res.get('explanation',''),wraplength=850,justify='left',font=ctk.CTkFont(size=14),text_color=MUTED).pack(anchor='w',pady=4);ctk.CTkLabel(self.resbox,text='Recommended next step: '+res.get('action','Review with the customer.'),wraplength=850,justify='left',font=ctk.CTkFont(size=12,weight='bold'),text_color=INK).pack(anchor='w',pady=5);details=ctk.CTkTextbox(self.resbox,height=110);details.insert('1.0',res.get('details','No technical details returned.'));details.configure(state='disabled');self.details_btn=ctk.CTkButton(self.resbox,text='Technical details ▸',fg_color='transparent',text_color=ACCENT,command=lambda:self.toggle_details(details));self.details_btn.pack(anchor='w');self.details=details
 def toggle_details(self,widget):
  if widget.winfo_ismapped():widget.pack_forget();self.details_btn.configure(text='Technical details ▸')
  else:widget.pack(fill='x',pady=6);self.details_btn.configure(text='Technical details ▾')
 def start_scan(self,name):
  if not self.consent_given or not self.visit_id:messagebox.showinfo('Consent required','Please complete customer consent first.');return
  if self.scan_running:return
  self.scan_running=True;self.progress.pack(pady=7);self.progress.set(.15);self.run_btn.configure(state='disabled',text='Checking…')
  threading.Thread(target=lambda:self.result_queue.put((name,scans.run_scan(name))),daemon=True).start()
 def start_quick_scan(self):
  if not self.consent_given or not self.visit_id:messagebox.showinfo('Consent required','Please complete customer consent first.');return
  if self.scan_running:return
  self.current='Quick Scan';self.clear();self.header('Quick Scan','A short local-only review. This scan does not change settings or delete files.')
  self.quick_frame=self.card();self.quick_status=ctk.CTkLabel(self.quick_frame,text='Preparing checks…',text_color=MUTED);self.quick_status.pack(anchor='w',padx=22,pady=12);self.quick_progress=ctk.CTkProgressBar(self.quick_frame,width=520);self.quick_progress.set(0);self.quick_progress.pack(anchor='w',padx=22,pady=8);self.quick_results=ctk.CTkFrame(self.quick_frame,fg_color='transparent');self.quick_results.pack(fill='x',padx=12,pady=10)
  self.scan_running=True
  def work():
   names=['System Info','Storage Health','Temperatures and Fans','Antivirus and Defender','Startup Programs','Junk File Scan and Cleanup'];out={}
   for i,name in enumerate(names,1):
    self.result_queue.put(('__QUICK_SCAN_PROGRESS__',(i,len(names),name)));out[name]=scans.run_scan(name)
   self.result_queue.put(('__QUICK_SCAN_RESULT__',out))
  threading.Thread(target=work,daemon=True).start()
 def start_full_scan(self):
  names=list(scans.SCANS.keys());self.start_scan_batch('Full Scan',names)
 def show_custom_scan(self):
  if not self.consent_given or not self.visit_id:messagebox.showinfo('Consent required','Please complete customer consent first.');return
  self.current='Custom Scan';self.clear();self.header('Custom Scan','Choose from checks implemented in this build. Every selected check is read-only.')
  f=self.card();self.custom_vars={}
  for group,items in NAV_GROUPS.items():
   available=[name for name in items if name in scans.SCANS]
   if not available:continue
   ctk.CTkLabel(f,text=group,font=ctk.CTkFont(size=13,weight='bold'),text_color=INK).pack(anchor='w',padx=18,pady=(14,5))
   for name in available:
    var=ctk.BooleanVar(value=True);self.custom_vars[name]=var;ctk.CTkCheckBox(f,text=name,variable=var).pack(anchor='w',padx=24,pady=3)
  ctk.CTkButton(f,text='Run selected checks',height=42,fg_color=ACCENT,command=self.run_custom_scan).pack(anchor='w',padx=20,pady=18)
 def run_custom_scan(self):
  names=[name for name,var in self.custom_vars.items() if var.get()]
  if not names:messagebox.showinfo('No checks selected','Select at least one check.');return
  self.start_scan_batch('Custom Scan',names)
 def start_scan_batch(self,title,names):
  if not self.consent_given or not self.visit_id:messagebox.showinfo('Consent required','Please complete customer consent first.');return
  if self.scan_running:messagebox.showinfo('Scan in progress','Wait for the current scan to finish.');return
  self.current=title;self.clear();self.header(title,'Read-only checks run locally. Some planned checks are not implemented and may be reported as unavailable.')
  self.batch_frame=self.card();self.batch_status=ctk.CTkLabel(self.batch_frame,text='Preparing checks…',text_color=MUTED);self.batch_status.pack(anchor='w',padx=22,pady=12);self.batch_progress=ctk.CTkProgressBar(self.batch_frame,width=520);self.batch_progress.set(0);self.batch_progress.pack(anchor='w',padx=22,pady=8);self.batch_results=ctk.CTkTextbox(self.batch_frame,height=520);self.batch_results.pack(fill='both',expand=True,padx=12,pady=10);self.batch_results.configure(state='disabled')
  self.scan_running=True
  def work():
   out={}
   for i,name in enumerate(names,1):
    self.result_queue.put(('__BATCH_PROGRESS__',(i,len(names),name)));out[name]=scans.run_scan(name)
   self.result_queue.put(('__BATCH_RESULT__',out))
  threading.Thread(target=work,daemon=True).start()
 def render_quick_results(self,results):
  for w in self.quick_results.winfo_children():w.destroy()
  order={'problem':0,'attention':1,'unknown':2,'good':3}
  for name,res in sorted(results.items(),key=lambda kv:order.get(kv[1].get('status','unknown'),2)):
   box=ctk.CTkFrame(self.quick_results,fg_color=BG,corner_radius=10);box.pack(fill='x',pady=4)
   ctk.CTkLabel(box,text=f"{res.get('status','unknown').upper()}  •  {res.get('headline',name)}",font=ctk.CTkFont(size=13,weight='bold'),text_color=STATUS_COLORS.get(res.get('status'),MUTED)).pack(anchor='w',padx=12,pady=(9,3))
   ctk.CTkLabel(box,text=res.get('explanation',''),wraplength=850,justify='left',text_color=MUTED).pack(anchor='w',padx=12,pady=(0,8))
  self.quick_status.configure(text=f"Quick Scan complete — {len(results)} checks recorded. Review each result before recommending an action.")
  self.quick_progress.set(1)
 def poll_queue(self):
  try:
   name,res=self.result_queue.get_nowait()
   if name=='__QUICK_SCAN_PROGRESS__':
    if self.current=='Quick Scan':self.quick_progress.set(res[0]/res[1]);self.quick_status.configure(text=f'Checking {res[2]}…  ({res[0]} of {res[1]})')
   elif name=='__QUICK_SCAN_RESULT__':
    self.results.update(res);database.save_results(self.visit_id,self.results);self.scan_running=False
    if self.current=='Quick Scan':self.render_quick_results(res)
   elif name=='__BATCH_PROGRESS__':
    if self.current in ('Full Scan','Custom Scan'):self.batch_progress.set(res[0]/res[1]);self.batch_status.configure(text=f'Checking {res[2]}…  ({res[0]} of {res[1]})')
   elif name=='__BATCH_RESULT__':
    self.results.update(res);database.save_results(self.visit_id,self.results);self.scan_running=False
    if self.current in ('Full Scan','Custom Scan'):
     order={'problem':0,'attention':1,'unknown':2,'good':3}
     summary=[]
     for title,result in sorted(res.items(),key=lambda kv:order.get(kv[1].get('status','unknown'),2)):
      summary.append(f"{result.get('status','unknown').upper()} | {result.get('headline',title)}\n{result.get('explanation','')}\nNext: {result.get('action','Review with the customer.')}\n")
     self.batch_results.configure(state='normal');self.batch_results.delete('1.0','end');self.batch_results.insert('1.0','\n'.join(summary));self.batch_results.configure(state='disabled')
     self.batch_progress.set(1);self.batch_status.configure(text=f"Scan finished: {len(res)} checks recorded. Items marked UNKNOWN need Windows support or are not implemented.")
   else:
    self.results[name]=res;database.save_results(self.visit_id,self.results);self.scan_running=False
    if self.current==name:self.progress.pack_forget();self.run_btn.configure(state='normal',text='Run Again');self.render_result(name)
  except queue.Empty:pass
  except Exception as ex:
   self.scan_running=False
   messagebox.showerror('Could not finish scan',str(ex))
  finally:self.after(150,self.poll_queue)
 def show_history(self):
  self.current='Customer History';self.clear();self.header('Customer history','Search local visit records. Data stays on this computer.')
  f=self.card();bar=ctk.CTkFrame(f,fg_color='transparent');bar.pack(fill='x',padx=18,pady=12);self.search=ctk.CTkEntry(bar,placeholder_text='Customer, phone, or PC model',width=360);self.search.pack(side='left');ctk.CTkButton(bar,text='Search',command=self.render_history).pack(side='left',padx=8);ctk.CTkButton(bar,text='Export CSV',command=self.csv_export).pack(side='right')
  rows=database.search_visits('');self.compare_choices={f"#{r['id']} | {r['name']} | {r['service_date']} | {r['pc_brand_model'] or 'PC'}":r['id'] for r in rows};choices=list(self.compare_choices) or ['No saved visits']
  compare=ctk.CTkFrame(f,fg_color=BG,corner_radius=9);compare.pack(fill='x',padx=14,pady=5);ctk.CTkLabel(compare,text='Compare two visits',font=ctk.CTkFont(size=13,weight='bold')).pack(anchor='w',padx=10,pady=(8,3));self.compare_a=ctk.CTkOptionMenu(compare,values=choices,width=250);self.compare_a.pack(side='left',padx=8,pady=8);self.compare_b=ctk.CTkOptionMenu(compare,values=choices,width=250);self.compare_b.pack(side='left',padx=8,pady=8);ctk.CTkButton(compare,text='Compare',command=self.compare_visits).pack(side='left',padx=8)
  self.compare_output=ctk.CTkTextbox(f,height=130);self.compare_output.pack(fill='x',padx=14,pady=5);self.compare_output.insert('1.0','Choose two visits to compare the recorded score and scan headlines.');self.compare_output.configure(state='disabled')
  self.hist=ctk.CTkScrollableFrame(f,fg_color=SURFACE);self.hist.pack(fill='both',expand=True,padx=12,pady=8);self.render_history()
 def compare_visits(self):
  if not self.compare_choices:return
  a=self.compare_choices.get(self.compare_a.get());b=self.compare_choices.get(self.compare_b.get())
  if not a or not b or a==b:messagebox.showinfo('Choose two visits','Select two different visit records.');return
  with database.connect() as db:ra=db.execute('SELECT * FROM visits WHERE id=?',(a,)).fetchone();rb=db.execute('SELECT * FROM visits WHERE id=?',(b,)).fetchone()
  if not ra or not rb:return
  old,new=(ra,rb) if ra['service_date']<=rb['service_date'] else (rb,ra);x=json.loads(old['results_json'] or '{}');y=json.loads(new['results_json'] or '{}')
  lines=[f"Earlier visit: {old['service_date']} — score {old['health_score'] if old['health_score'] is not None else '—'} / 100",f"Later visit: {new['service_date']} — score {new['health_score'] if new['health_score'] is not None else '—'} / 100"]
  if old['health_score'] is not None and new['health_score'] is not None:lines.append(f"Health score change: {new['health_score']-old['health_score']:+d} points")
  for name in sorted(set(x)|set(y)):
   before=x.get(name,{});after=y.get(name,{})
   lines.append(f"{name}: {before.get('headline','not checked')} → {after.get('headline','not checked')}")
  self.compare_output.configure(state='normal');self.compare_output.delete('1.0','end');self.compare_output.insert('1.0','\n'.join(lines));self.compare_output.configure(state='disabled')
 def render_history(self):
  for w in self.hist.winfo_children():w.destroy()
  for r in database.search_visits(self.search.get() if hasattr(self,'search') else ''):
   line=f"{r['service_date']}  |  {r['name']}  |  {r['pc_brand_model'] or 'PC not entered'}  |  Score: {r['health_score'] if r['health_score'] is not None else '—'}  |  Visit #{r['id']}"
   row=ctk.CTkFrame(self.hist,fg_color=BG);row.pack(fill='x',pady=3);ctk.CTkLabel(row,text=line,anchor='w').pack(side='left',padx=12,pady=10,fill='x',expand=True);ctk.CTkButton(row,text='Open report',width=110,command=lambda vid=r['id']:self.export_report(vid)).pack(side='right',padx=7);ctk.CTkButton(row,text='Delete customer data',width=145,fg_color='#9B2C2C',command=lambda cid=r['customer_id']:self.delete_data(cid)).pack(side='right',padx=4)
 def delete_data(self,cid):
  if self.scan_running:messagebox.showinfo('Scan in progress','Wait for the scan before deleting customer records.');return
  if messagebox.askyesno('Delete customer data','This permanently deletes this customer and all linked visits from the local CareWare database. Continue?'):
   database.delete_customer(cid)
   if cid==self.customer_id:self.reset_visit()
   self.show_history()
 def csv_export(self):
  p=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')]);
  if p:
   database.export_csv(p);messagebox.showinfo('Exported',f'History saved to {p}')
 def show_report(self):
  self.current='Report';self.clear();self.header('Customer report','Export the active visit as a branded PDF and JSON copy.')
  f=self.card();ctk.CTkLabel(f,text='Visit summary',font=ctk.CTkFont(size=18,weight='bold')).pack(anchor='w',padx=20,pady=(22,8));ctk.CTkLabel(f,text=f'Active visit: {self.visit_id or "none"}   •   Results collected: {len(self.results)}',text_color=MUTED).pack(anchor='w',padx=20,pady=4);ctk.CTkLabel(f,text='Next cleaning due (optional, YYYY-MM-DD)',text_color=MUTED).pack(anchor='w',padx=20,pady=(18,4));self.due=ctk.CTkEntry(f,width=250);self.due.insert(0,(date.today()+timedelta(days=180)).isoformat());self.due.pack(anchor='w',padx=20);ctk.CTkButton(f,text='Export Customer Report (PDF + JSON)',height=42,fg_color=ACCENT,command=lambda:self.export_report(self.visit_id)).pack(anchor='w',padx=20,pady=18)
 def export_report(self,vid):
  if not vid:messagebox.showinfo('No visit','Start a consented visit before exporting a report.');return
  if hasattr(self,'due') and self.current=='Report':database.set_visit_fields(vid,next_due=self.due.get().strip())
  try:
   pdf,raw=report.export_visit(vid);messagebox.showinfo('Report exported',f'PDF: {pdf}\nRaw JSON: {raw}')
  except Exception as e:messagebox.showerror('Report failed',str(e))
 def show_reminders(self):
  self.current='Service Reminders';self.clear();self.header('Service reminders','Only customers who agreed to future reminders are listed here.')
  f=self.card();rows=database.reminder_visits()
  if not rows:ctk.CTkLabel(f,text='No due reminders. Set a next-cleaning date in the visit report and record reminder permission in consent.',wraplength=800,text_color=MUTED).pack(anchor='w',padx=22,pady=25)
  for r in rows:
   box=ctk.CTkFrame(f,fg_color=BG);box.pack(fill='x',padx=12,pady=5);ctk.CTkLabel(box,text=f"{r['name']}  •  {r['phone']}  •  {r['pc_brand_model']}  •  Due {r['next_due']}",anchor='w').pack(fill='x',padx=12,pady=8);ctk.CTkButton(box,text='Copy reminder',command=lambda row=r:self.copy_reminder(row)).pack(side='left',padx=10,pady=(0,10));ctk.CTkButton(box,text='Mark contacted',command=lambda vid=r['id']:self.mark_contacted(vid)).pack(side='left',padx=5,pady=(0,10))
 def copy_reminder(self,r):
  msg=f"Hi {r['name']}, this is {database.get_setting('business_name','your PC care technician')}. Your next recommended computer cleaning is due. Reply if you’d like to book a visit."
  self.clipboard_clear();self.clipboard_append(msg);messagebox.showinfo('Copied','Reminder message copied to clipboard. Review it before sending.')
 def mark_contacted(self,vid):database.set_visit_fields(vid,contacted_at=datetime.now().isoformat(timespec='minutes'));self.show_reminders()
 def show_settings(self):
  self.current='Settings';self.clear();self.header('Settings','Business branding, report defaults, theme, and local database tools.')
  f=self.card();self.settings_entries={};vals={'business_name':'Business name','tagline':'Tagline','contact_number':'Contact number','website':'Facebook page or website','address':'Address or service area','accent_color':'Accent colour (hex, e.g. #2C7BE5)','footer_message':'Custom report footer','technician_name':'Default technician','qr_target':'QR code target'}
  for key,label in vals.items():
   ctk.CTkLabel(f,text=label,text_color=MUTED).pack(anchor='w',padx=20,pady=(12,2));e=ctk.CTkEntry(f,width=520);e.insert(0,database.get_setting(key,''));e.pack(anchor='w',padx=20);self.settings_entries[key]=e
  ctk.CTkLabel(f,text='Report logo image',text_color=MUTED).pack(anchor='w',padx=20,pady=(12,2));lf=ctk.CTkFrame(f,fg_color='transparent');lf.pack(anchor='w',padx=20);self.logo_entry=ctk.CTkEntry(lf,width=430);self.logo_entry.insert(0,database.get_setting('logo_path',''));self.logo_entry.pack(side='left');ctk.CTkButton(lf,text='Browse',command=self.choose_logo).pack(side='left',padx=5)
  self.threshold_entries={}
  for key,label in [('cpu_attention_percent','CPU attention threshold (%)'),('memory_attention_percent','Memory attention threshold (%)'),('storage_low_space_percent','Low disk space threshold (%)'),('temperature_attention_c','Temperature warning threshold (°C)'),('temperature_problem_c','High temperature threshold (°C)')]:
   ctk.CTkLabel(f,text=label,text_color=MUTED).pack(anchor='w',padx=20,pady=(10,2));e=ctk.CTkEntry(f,width=180);e.insert(0,str(config.get_threshold(key)));e.pack(anchor='w',padx=20);self.threshold_entries[key]=e
  ctk.CTkButton(f,text='Save settings',fg_color=ACCENT,command=self.save_settings).pack(anchor='w',padx=20,pady=18);self.dark=ctk.BooleanVar(value=self.theme=='dark');ctk.CTkCheckBox(f,text='Dark mode',variable=self.dark,command=self.toggle_theme).pack(anchor='w',padx=20,pady=5);ctk.CTkButton(f,text='Back up local database',command=self.backup_db).pack(anchor='w',padx=20,pady=8);ctk.CTkButton(f,text='Restore local database from backup…',fg_color='#9B2C2C',command=self.restore_db).pack(anchor='w',padx=20,pady=8)
 def choose_logo(self):
  p=filedialog.askopenfilename(filetypes=[('Image files','*.png *.jpg *.jpeg')]);
  if p:self.logo_entry.delete(0,'end');self.logo_entry.insert(0,p)
 def save_settings(self):
  for k,e in self.settings_entries.items():database.set_setting(k,e.get())
  try:
   for k,e in self.threshold_entries.items():config.set_threshold(k,e.get())
   database.set_setting('logo_path',self.logo_entry.get());messagebox.showinfo('Saved','Settings saved locally.')
  except Exception as ex:messagebox.showerror('Invalid setting',str(ex))
 def toggle_theme(self):self.theme='dark' if self.dark.get() else 'light';ctk.set_appearance_mode(self.theme);database.set_setting('theme',self.theme)
 def backup_db(self):
  dest=filedialog.asksaveasfilename(defaultextension='.sqlite3',filetypes=[('SQLite database','*.sqlite3')]);
  if dest:
   src=database.DB_PATH
   try:database.backup_database(dest);messagebox.showinfo('Backup complete',f'Database backup saved to {dest}')
   except Exception as e:messagebox.showerror('Backup failed',str(e))
 def reset_visit(self):
  self.consent_given=False;self.visit_id=None;self.customer_id=None;self.results={}
 def restore_db(self):
  if self.scan_running:messagebox.showinfo('Scan in progress','Wait for the scan before restoring the database.');return
  src=filedialog.askopenfilename(filetypes=[('CareWare SQLite backup','*.sqlite3 *.db')])
  if not src:return
  if not messagebox.askyesno('Replace local database','Replace the current database with this backup? A backup of the current database will be saved first.'):return
  try:
   backup=database.restore_database(src)
   self.reset_visit();self.show_welcome()
   messagebox.showinfo('Database restored',f'Database restored. Previous data backup: {backup}')
  except Exception as e:messagebox.showerror('Restore failed',str(e))
 def show_inspection(self):
  self.current='Physical Inspection Checklist';self.clear();self.header(self.current,'Record visible condition only; optional photo attachments are not enabled in this build.')
  f=self.card();self.physical={}
  items=['Dust level','CPU fan','GPU fan','Power supply fan','Thermal paste age','Cables','Loose parts','Swollen capacitors','Airflow','Laptop vents','Keyboard condition','Screen condition']
  for item in items:
   v=ctk.BooleanVar();self.physical[item]=v;ctk.CTkCheckBox(f,text=item,variable=v).pack(anchor='w',padx=22,pady=8)
  ctk.CTkButton(f,text='Save inspection notes',fg_color=ACCENT,command=self.save_inspection).pack(anchor='w',padx=22,pady=14)
 def save_inspection(self):
  self.results['Physical Inspection Checklist']={'status':'good','headline':'Physical inspection recorded','explanation':'The technician recorded the visible inspection checklist.','action':'Include observations in the service notes.','details':json.dumps({k:v.get() for k,v in self.physical.items()})};database.save_results(self.visit_id,self.results);messagebox.showinfo('Saved','Inspection checklist saved to this visit.')
 def show_cleanup(self):
  self.current='Junk File Scan and Cleanup';self.clear();self.header(self.current,'Preview old temporary files first. No files are removed during the scan.')
  f=self.card();ctk.CTkLabel(f,text='CareWare only lists old files from Windows and user temporary folders. Personal documents, photos, downloads, browser history, and registry data are never targeted.',wraplength=850,justify='left',text_color=MUTED).pack(anchor='w',padx=20,pady=15);ctk.CTkButton(f,text='Scan for eligible temporary files',fg_color=ACCENT,command=self.preview_cleanup).pack(anchor='w',padx=20,pady=5);self.clean_summary=ctk.CTkLabel(f,text='No preview yet.',anchor='w',text_color=MUTED);self.clean_summary.pack(fill='x',padx=20,pady=(8,2));self.clean_candidates=ctk.CTkScrollableFrame(f,height=240,fg_color=BG);self.clean_candidates.pack(fill='x',padx=20,pady=6);self.dry=ctk.BooleanVar(value=True);ctk.CTkCheckBox(f,text='Dry run (recommended; never delete files)',variable=self.dry).pack(anchor='w',padx=20,pady=5);ctk.CTkButton(f,text='Clean selected files',fg_color='#B7791F',command=self.run_cleanup).pack(anchor='w',padx=20,pady=12);self.clean_paths=[];self.clean_choices={}
 def preview_cleanup(self):
  try:
   data=cleanup.preview();self.clean_paths=[x['path'] for x in data['files']];self.clean_choices={}
   for w in self.clean_candidates.winfo_children():w.destroy()
   self.clean_summary.configure(text=f"Found {data['count']} eligible files ({data['bytes']/1024**2:.1f} MB). All start unchecked; no files have been deleted.")
   for item in data['files'][:1000]:
    var=ctk.BooleanVar(value=False);self.clean_choices[item['path']]=var
    ctk.CTkCheckBox(self.clean_candidates,text=f"{item['path']}   •   {item['size']/1024:.1f} KB",variable=var).pack(anchor='w',fill='x',padx=8,pady=3)
  except Exception as e:messagebox.showerror('Preview failed',str(e))
 def run_cleanup(self):
  selected=[p for p,v in self.clean_choices.items() if v.get()]
  if not self.visit_id or not self.clean_paths:messagebox.showinfo('Nothing selected','Run the preview first.');return
  if not selected:messagebox.showinfo('Nothing selected','Tick the individual temporary files you want to include.');return
  with database.connect() as db:r=db.execute('SELECT consent_cleanup FROM visits WHERE id=?',(self.visit_id,)).fetchone()
  if not r or not r[0]:messagebox.showwarning('Separate permission required','This visit did not include optional cleanup permission. Start a new visit and obtain separate customer consent before cleanup.');return
  dry=self.dry.get()
  if dry:
   cleanup.clean(selected,consent_cleanup=True,dry_run=True);messagebox.showinfo('Dry run',f'Dry run complete for {len(selected)} selected files. No files were deleted. Untick Dry run to request deletion.');return
  if not messagebox.askyesno('Confirm cleanup','This will try to create a Windows restore point and then delete only the old temporary files listed in the preview. Continue?'):return
  try:
   out=cleanup.clean(selected,consent_cleanup=True,dry_run=False);database.set_visit_fields(self.visit_id,cleanup_json=out);messagebox.showinfo('Cleanup complete',f"Deleted {len(out['deleted'])} files. Skipped {len(out['skipped'])}. {out.get('bytes_recovered',0)/1024**2:.1f} MB recovered. A restore point was created.")
  except Exception as e:messagebox.showerror('Cleanup cancelled',str(e))
 def show_large_files(self):self.show_scan_page('Large Files Finder')
 def show_duplicate(self):self.show_scan_page('Duplicate Files Finder')
 def show_disk_map(self):self.show_scan_page('Disk Space Map')

if __name__=='__main__':
 try:
  if '--legacy' in sys.argv:CareWareApp().mainloop()
  else:
   from desktop import run
   smoke_output=sys.argv[sys.argv.index('--smoke-test')+1] if '--smoke-test' in sys.argv else None
   run('--preview' in sys.argv,smoke_output=smoke_output)
 except Exception as exc:
  if '--smoke-test' in sys.argv:
   Path(sys.argv[sys.argv.index('--smoke-test')+1]).write_text(json.dumps({'ok':False,'error':str(exc)}),encoding='utf-8')
   sys.exit(1)
  try:messagebox.showerror('CareWare could not start',str(exc))
  except Exception:raise
