"""Branded PDF report and raw JSON appendix export."""
from __future__ import annotations
import json, os, re, html, uuid
from pathlib import Path
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from . import database

def _safe(s):return re.sub(r'[^A-Za-z0-9_-]+','_',s.strip()).strip('_') or 'Customer'
def _qr(data):
    if not data:return None
    widget=QrCodeWidget(data); b=widget.getBounds(); size=0.8*inch
    d=Drawing(size,size,transform=[size/(b[2]-b[0]),0,0,size/(b[3]-b[1]),0,0]);d.add(widget);return d

def export_visit(visit_id, out_dir=None, db_path=None):
    with database.connect(db_path) as db:
        v=db.execute('SELECT v.*,c.name,c.phone,c.address FROM visits v JOIN customers c ON c.id=v.customer_id WHERE v.id=?',(visit_id,)).fetchone()
        if not v:raise ValueError('Visit not found')
        results=json.loads(v['results_json'] or '{}')
        settings={r['key']:r['value'] for r in db.execute('SELECT key,value FROM settings')}
    folder=Path(out_dir or (Path.home()/'Documents'/'CareWare Reports'));folder.mkdir(parents=True,exist_ok=True)
    d=datetime.fromisoformat(v['service_date']).strftime('%Y-%m-%d') if v['service_date'] else datetime.now().strftime('%Y-%m-%d')
    base=f"{_safe(v['name'])[:80]}_{d}_checkup-{visit_id}_{uuid.uuid4().hex}"
    pdf=folder/(base+'.pdf'); raw=folder/(base+'_raw.json')
    export={'customer':{'name':v['name'],'phone':v['phone'],'address':v['address']},'visit':{k:v[k] for k in ['pc_brand_model','technician','service_date','health_score','consent_understood','consent_scan','consent_cleanup','consent_reminders','consent_language','signature','consent_at','next_due']},'results':results}
    raw.write_text(json.dumps(export,ensure_ascii=False,indent=2),encoding='utf-8')
    styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name='Small',parent=styles['BodyText'],fontSize=8,leading=11,textColor=colors.HexColor('#40536B')))
    accent_value=settings.get('accent_color','#2C7BE5')
    if not re.fullmatch(r'#[0-9A-Fa-f]{6}',accent_value):accent_value='#2C7BE5'
    accent=colors.HexColor(accent_value)
    story=[]
    logo=settings.get('logo_path','');biz=settings.get('business_name','CareWare PC Care')
    if logo and Path(logo).is_file():
        try:
            from reportlab.platypus import Image
            story.append(Image(logo,width=1.05*inch,height=.6*inch,kind='proportional'))
        except Exception:pass
    contact='  •  '.join(x for x in [settings.get('contact_number',''),settings.get('address',''),settings.get('website','')] if x)
    story += [Paragraph(html.escape(biz),styles['Title']),Paragraph(html.escape(settings.get('tagline','PC care, made simple')),styles['Small'])]
    if contact:story.append(Paragraph(html.escape(contact),styles['Small']))
    story += [Paragraph('CUSTOMER SERVICE REPORT',styles['Heading2']),Spacer(1,10)]
    info=[["Customer",v['name'],"Service date",v['service_date']],["Phone",v['phone'] or '—',"Computer",v['pc_brand_model'] or '—'],["Technician",v['technician'] or '—',"Health score",f"{v['health_score'] if v['health_score'] is not None else '—'} / 100"]]
    t=Table(info,colWidths=[.85*inch,2.2*inch,.85*inch,2.2*inch]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),colors.HexColor('#EEF4FB')),('BACKGROUND',(2,0),(2,-1),colors.HexColor('#EEF4FB')),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#D6DFEA')),('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),8),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));story += [t,Spacer(1,12),Paragraph('Consent record',styles['Heading2'])]
    story.append(Paragraph(f"Notice language: {html.escape(v['consent_language'])}. The customer agreed to the scan: {'Yes' if v['consent_scan'] else 'No'}. Cleanup permission: {'Yes' if v['consent_cleanup'] else 'No'}. Future reminders: {'Yes' if v['consent_reminders'] else 'No'}. Signed by: {html.escape(v['signature'])}. Recorded: {html.escape(v['consent_at'])}.",styles['Small']))
    story += [Spacer(1,12),Paragraph('Check results',styles['Heading2'])]
    for name,res in results.items():
        if not isinstance(res,dict) or name=='Physical Inspection Checklist':continue
        st=res.get('status','unknown'); color={'good':'#1F9D68','attention':'#B7791F','problem':'#C53030'}.get(st,'#66758A')
        block=[Paragraph(f"<font color='{color}'><b>{st.upper()}</b></font> &nbsp; <b>{res.get('headline',name)}</b>",styles['BodyText']),Paragraph(res.get('explanation',''),styles['Small']),Paragraph('Suggested next step: '+res.get('action','Review with the customer.'),styles['Small'])]
        if res.get('details'):block.append(Paragraph('Technical detail: '+str(res['details']).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br/>')[:5000],styles['Small']))
        story += [KeepTogether(block),Spacer(1,7)]
    physical=results.get('Physical Inspection Checklist',{});checked=[]
    if physical:
        try:checked=[k for k,val in json.loads(physical.get('details','{}')).items() if val]
        except Exception:checked=[]
    condition='Technician marked: '+', '.join(checked) if checked else ('Checklist recorded; no items marked.' if physical else 'No physical inspection checklist was recorded for this visit.')
    story += [Spacer(1,8),Paragraph('Physical condition',styles['Heading2']),Paragraph(html.escape(condition),styles['Small']),Spacer(1,8),Paragraph(f"Next recommended cleaning: {html.escape(v['next_due'] or 'Not set')}",styles['Small'])]
    target=settings.get('qr_target','')
    q=_qr(target)
    story += [Spacer(1,12),Paragraph(html.escape(settings.get('footer_message','Thank you for choosing us.')),styles['Small'])]
    if q:story += [q,Paragraph('Scan to contact us or book your next cleaning.',styles['Small'])]
    story += [Paragraph('Powered by CareWare',styles['Small']),PageBreak(),Paragraph('Technician appendix — raw results',styles['Heading1']),Paragraph('A copy of the structured raw scan results is also saved as JSON beside this report.',styles['Small'])]
    doc=SimpleDocTemplate(str(pdf),pagesize=letter,rightMargin=.6*inch,leftMargin=.6*inch,topMargin=.55*inch,bottomMargin=.6*inch,title=f'CareWare report — {v["name"]}')
    def footer(canvas,doc):
        canvas.saveState();canvas.setStrokeColor(accent);canvas.line(.6*inch,.45*inch,7.9*inch,.45*inch);canvas.setFont('Helvetica',7);canvas.setFillColor(colors.HexColor('#66758A'));canvas.drawString(.6*inch,.3*inch,settings.get('business_name','CareWare PC Care'));canvas.drawRightString(7.9*inch,.3*inch,f'Page {doc.page}');canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    database.set_visit_fields(visit_id,path=db_path,report_path=str(pdf))
    return str(pdf),str(raw)
