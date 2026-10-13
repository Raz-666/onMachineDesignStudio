#!/usr/bin/env python3
"""MANUAL.pdf — the illustrated user handbook (R2-2026-10-13.102).
Mirrors MANUAL.md: daily workflow first, generators next, calibration ladder,
reference tables. 21 vector diagrams (font specimens + range variants drawn
from the REAL generator glyph data), full parameter tables."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Table, TableStyle, PageBreak, HRFlowable, CondPageBreak, KeepTogether)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle, Polygon, PolyLine

FD = '/usr/share/fonts/truetype/dejavu/'
pdfmetrics.registerFont(TTFont('DVS', FD + 'DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DVSB', FD + 'DejaVuSans-Bold.ttf'))

BLUE = colors.HexColor('#1c4e8c'); LBLUE = colors.HexColor('#e8f0fa')
ORANGE = colors.HexColor('#e07b00'); GRAY = colors.HexColor('#58595b')
LGRAY = colors.HexColor('#f2f2f2'); GREEN = colors.HexColor('#1e7d32')
RED = colors.HexColor('#b3261e'); PURPLE = colors.HexColor('#6a3fb5')
TEAL = colors.HexColor('#00706b'); BLACK = colors.HexColor('#111111')

S = {
 'title': ParagraphStyle('t', fontName='DVSB', fontSize=26, leading=30, textColor=BLUE, alignment=TA_CENTER),
 'sub':   ParagraphStyle('s', fontName='DVS', fontSize=14.5, leading=20.5, textColor=GRAY, alignment=TA_CENTER),
 'h1':    ParagraphStyle('h1', fontName='DVSB', fontSize=21, leading=27, textColor=BLUE, spaceBefore=12, spaceAfter=2, keepWithNext=1),
 'h2':    ParagraphStyle('h2', fontName='DVSB', fontSize=15.5, leading=22, spaceBefore=17, spaceAfter=8, keepWithNext=1),
 'p':     ParagraphStyle('p', fontName='DVS', fontSize=12.2, leading=18.6, spaceAfter=7, allowWidows=0, allowOrphans=0),
 'b':     ParagraphStyle('b', fontName='DVS', fontSize=12.2, leading=18, leftIndent=12, spaceAfter=5.5, allowWidows=0, allowOrphans=0),
 'code':  ParagraphStyle('c', fontName='DVS', fontSize=10.8, leading=15.8, backColor=LGRAY, borderPadding=5, leftIndent=6, spaceAfter=8, allowWidows=0, allowOrphans=0),
 'cap':   ParagraphStyle('cap', fontName='DVS', fontSize=10.5, leading=15, textColor=GRAY, alignment=TA_CENTER, spaceBefore=3, spaceAfter=8, allowWidows=0, allowOrphans=0),
 'ts':    ParagraphStyle('ts', fontName='DVSB', fontSize=10.5, leading=14.2, textColor=colors.white),
 'tc':    ParagraphStyle('tc', fontName='DVS', fontSize=10.5, leading=14.2),
 'end':   ParagraphStyle('end', fontName='DVSB', fontSize=13, leading=18, textColor=BLUE, alignment=TA_CENTER),
}
H1 = lambda t: Paragraph(t, S['h1'])
def H2(t): return [CondPageBreak(46*mm), Paragraph(t, S['h2'])]
def CENT(d):
    d.hAlign='CENTER'; return d
P = lambda t: Paragraph(t, S['p']); CAP = lambda t: Paragraph(t, S['cap'])
B = lambda *i: [Paragraph('•  ' + x, S['b']) for x in i]
CODE = lambda t: Paragraph(t.replace('\n', '<br/>').replace(' ', '&nbsp;'), S['code'])

def TBL(headers, rows, widths, pad=4):
    data = [[Paragraph(h, S['ts']) for h in headers]] + [[Paragraph(c, S['tc']) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), BLUE),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LGRAY]),
        ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#c9d4e4')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 4), ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), pad), ('BOTTOMPADDING', (0,0), (-1,-1), pad)]))
    return t

# ============================ DIAGRAMS ============================
def d_state_machine():
    d = Drawing(480, 210); 
    def box(x,y,w,h,txt,fill,fs=9):
        d.add(Rect(x,y,w,h,rx=6,fill=1,stroke=0,fillColor=fill))
        d.add(String(x+w/2,y+h/2-3,txt,fontName='DVSB',fontSize=fs,textAnchor='middle',fillColor=colors.white))
    def arrow(x1,y1,x2,y2,lbl='',lx=0,ly=0,col=GRAY):
        d.add(Line(x1,y1,x2,y2,strokeColor=col,strokeWidth=1.1)); import math
        a=math.atan2(y2-y1,x2-x1)
        for s in (2.6,-2.6): d.add(Line(x2,y2,x2-5*math.cos(a-s),y2-5*math.sin(a-s),strokeColor=col,strokeWidth=1.1))
        if lbl: d.add(String((x1+x2)/2+lx,(y1+y2)/2+ly,lbl,fontName='DVS',fontSize=7.3,fillColor=col))
    box(15,155,90,26,'idle',BLUE); box(190,155,100,26,'waiting',ORANGE)
    box(355,155,100,26,'starting',GRAY); box(355,85,100,26,'printing',GREEN)
    box(190,85,100,26,'paused',colors.HexColor('#c79100')); box(190,12,100,26,'filament',TEAL)
    box(15,12,90,26,'finished',PURPLE)
    arrow(105,168,190,168,'PRINT_START',0,8); arrow(290,168,355,168,'decision',0,8)
    arrow(405,155,405,111,'file released',8,7); arrow(355,98,290,98,'PAUSE / M600',0,8)
    arrow(290,85,355,85,'RESUME',0,-11); arrow(240,85,240,38,'runout / M600',8,0)
    arrow(240,38,240,85,'RESUME (purge)',0,-13)
    arrow(355,90,105,30,'PRINT_END / legacy end',26,26)
    d.add(Line(60,38,60,155,strokeColor=colors.HexColor('#9bb2cc'),strokeWidth=1,strokeDashArray=[3,3]))
    d.add(String(52,90,'watcher re-syncs',fontName='DVS',fontSize=7.5,fillColor=GRAY,angle=90))
    return d

def d_start_stages():
    stages=[('Homing','cyan scanner','r2_stage_home'),('Bed heats','red chase','r2_stage_heat'),
            ('Bed mesh','magenta scanner','r2_stage_mesh'),('Hotend heats','red chase','r2_stage_heat'),
            ('Temp ok','-','r2_hot'),('Purge/Prime','leveling','r2_prime'),('PRINT','blue wave','r2_printing')]
    d=Drawing(480,120); x=8
    for i,(n,led,snd) in enumerate(stages):
        w=57
        d.add(Rect(x,55,w,30,rx=5,fill=1,stroke=0,fillColor=BLUE if i<len(stages)-1 else GREEN))
        d.add(String(x+w/2,75,n,fontName='DVSB',fontSize=7.6,textAnchor='middle',fillColor=colors.white))
        d.add(String(x+w/2,64,'LED: '+led,fontName='DVS',fontSize=6.3,textAnchor='middle',fillColor=colors.HexColor('#d7e3f4')))
        d.add(String(x+w/2,43,snd,fontName='DVS',fontSize=6.6,textAnchor='middle',fillColor=GRAY))
        if i<len(stages)-1:
            d.add(Line(x+w+1,70,x+w+8,70,strokeColor=GRAY,strokeWidth=1.2))
            d.add(Polygon(points=[x+w+8,70,x+w+3,72.4,x+w+3,67.6],fillColor=GRAY,stroke=0))
        x+=w+8
    d.add(String(240,26,'parked HIGH while heating · nozzle never waits on the bed · overrides applied before the file runs',
                 fontName='DVS',fontSize=7.5,textAnchor='middle',fillColor=GRAY))
    d.add(String(240,97,'Print start choreography (identical for every start mode)',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    return d

def d_l1l2():
    d=Drawing(480,170)
    d.add(String(240,158,'L1/L2 temperatures & speed — every object starts from scratch',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    ox,oy,w,h=40,22,400,112
    d.add(Line(ox,oy,ox+w,oy,strokeColor=colors.black,strokeWidth=1)); d.add(Line(ox,oy,ox,oy+h,strokeColor=colors.black,strokeWidth=1))
    for i in range(5):
        d.add(Line(ox+i*100,oy,ox+i*100,oy+3,strokeColor=colors.black))
        d.add(String(ox+i*100,oy-10,f'obj {i+1}' if i else 'obj 1',fontName='DVS',fontSize=7,textAnchor='middle'))
    d.add(String(ox+w/2,2,'print progress — sequential "print by object"',fontName='DVS',fontSize=7,textAnchor='middle',fillColor=GRAY))
    yL1,yL2,ys1,ys2=oy+30,oy+88,oy+12,oy+54
    poly=[]; x=ox
    for i in range(4):
        poly+=[(x,yL1),(x+22,yL1),(x+22,yL2),(x+100,yL2)]; x+=100
    for i in range(len(poly)-1): d.add(Line(poly[i][0],poly[i][1],poly[i+1][0],poly[i+1][1],strokeColor=RED,strokeWidth=1.6))
    poly=[]; x=ox
    for i in range(4):
        poly+=[(x,ys1),(x+22,ys1),(x+22,ys2),(x+100,ys2)]; x+=100
    for i in range(len(poly)-1): d.add(Line(poly[i][0],poly[i][1],poly[i+1][0],poly[i+1][1],strokeColor=BLUE,strokeWidth=1.6,strokeDashArray=[3,2]))
    d.add(String(ox+6,yL1+5,'L1 temp (adhesion)',fontName='DVS',fontSize=7,fillColor=RED))
    d.add(String(ox+130,yL2+5,'L2 temp from layer 2',fontName='DVS',fontSize=7,fillColor=RED))
    d.add(String(ox+26,ys1-10,'L1 speed 75% (feature factors capped)',fontName='DVS',fontSize=7,fillColor=BLUE))
    d.add(String(ox+215,ys2+5,'L2 speed 100% (feature factor)',fontName='DVS',fontSize=7,fillColor=BLUE))
    d.add(String(ox+398,yL1-16,'object change: pause + wait for L1',fontName='DVSB',fontSize=6.8,fillColor=GREEN,textAnchor='end'))
    return d

def d_seq():
    d=Drawing(480,178)
    d.add(String(240,166,'Sequential object detection — why z-hop cannot fool it',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    ox,oy,w=40,25,400
    d.add(Line(ox,oy,ox+w,oy,strokeColor=colors.black,strokeWidth=1))
    yts,ytl=oy+96,oy+30
    d.add(Line(ox,yts,ox+w,yts,strokeColor=GREEN,strokeWidth=0.8,strokeDashArray=[4,3]))
    d.add(String(ox+w-2,yts+3,'high-water ≥1.6',fontName='DVS',fontSize=6.6,textAnchor='end',fillColor=GREEN))
    d.add(Line(ox,ytl,ox+w,ytl,strokeColor=ORANGE,strokeWidth=0.8,strokeDashArray=[4,3]))
    d.add(String(ox+w+2,ytl-2,'Z < 1.5',fontName='DVS',fontSize=6.6,fillColor=ORANGE))
    d.add(Line(ox+10,ytl+6,ox+10,oy+106,strokeColor=BLUE,strokeWidth=1.8))
    d.add(Line(ox+10,oy+106,ox+80,oy+106,strokeColor=BLUE,strokeWidth=1.8))
    d.add(Line(ox+80,oy+106,ox+90,ytl+4,strokeColor=BLUE,strokeWidth=1.8))
    d.add(Line(ox+90,ytl+4,ox+150,ytl+4,strokeColor=BLUE,strokeWidth=1.8))
    d.add(String(ox+16,oy+108,'object 1 (vase only rises)',fontName='DVS',fontSize=7,fillColor=BLUE))
    d.add(String(ox+14,ytl+9,'fall >1 mm + stays low ≥0.8 s',fontName='DVSB',fontSize=7,fillColor=GREEN))
    d.add(String(ox+92,ytl+10,'→ OBJECT CHANGE: L1 restart',fontName='DVSB',fontSize=7.2,fillColor=GREEN))
    d.add(Line(ox+230,ytl+2,ox+230,oy+70,strokeColor=RED,strokeWidth=1.8))
    d.add(Line(ox+230,oy+70,ox+330,oy+70,strokeColor=RED,strokeWidth=1.8))
    for hx in (ox+250,ox+280,ox+310):
        d.add(Line(hx,oy+52,hx,oy+70,strokeColor=RED,strokeWidth=1.4)); d.add(Line(hx,oy+70,hx+8,oy+52,strokeColor=RED,strokeWidth=1.4))
    d.add(String(ox+236,oy+74,'object 2 (low layers, z-hop travels)',fontName='DVS',fontSize=7,fillColor=RED))
    d.add(String(ox+244,oy+40,'hop bounces: fall ≤1 mm and/or brief',fontName='DVSB',fontSize=7,fillColor=RED))
    d.add(String(ox+244,oy+31,'→ ignored (no false alarm)',fontName='DVSB',fontSize=7,fillColor=RED))
    return d

def d_calibration():
    steps=['1 Shaper','2 Probe Z','3 Screws','4 Extruder','5 PID','6 Mesh','7 PA','8 Flow']
    d=Drawing(480,62); x=6
    for i,s in enumerate(steps):
        w=54
        d.add(Rect(x,22,w,24,rx=5,fill=1,stroke=0,fillColor=BLUE if i%2==0 else colors.HexColor('#2f6db3')))
        d.add(String(x+w/2,31,s,fontName='DVSB',fontSize=7,textAnchor='middle',fillColor=colors.white))
        if i<len(steps)-1:
            d.add(Line(x+w+1,34,x+w+4.5,34,strokeColor=GRAY,strokeWidth=1.2))
            d.add(Polygon(points=[x+w+4.5,34,x+w+2.5,35.4,x+w+2.5,32.6],fillColor=GRAY,stroke=0))
        x+=w+5
    d.add(String(240,10,'once per printer (left -> right) - then per material: Temp Tower + Ironing card',
                 fontName='DVS', fontSize=6.8, textAnchor='middle', fillColor=GRAY))
    return d

def d_menu():
    d=Drawing(480,195)
    d.add(String(240,183,'LCD menu overview (12864 — every line fits 16 characters)',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    def box(x,y,w,h,t,f,fs=7):
        d.add(Rect(x,y,w,h,rx=4,fill=1,stroke=0,fillColor=f))
        d.add(String(x+w/2,y+h/2-2.5,t,fontName='DVSB',fontSize=fs,textAnchor='middle',fillColor=colors.white))
    def ln(x1,y1,x2,y2): d.add(Line(x1,y1,x2,y2,strokeColor=colors.HexColor('#9bb2cc'),strokeWidth=0.9))
    box(195,155,90,18,'R2-D2',BLUE,fs=9)
    # R89/R90: seven groups - Tools (the seven part generators) joined the row
    items=[('Start Print?',ORANGE),('Live Tuning',GREEN),('Pre-Print',GRAY),('Macros',TEAL),
           ('Tools',colors.HexColor('#5a3d8a')),('Maintenance',PURPLE),('System',RED)]
    xs=[2,70,138,206,274,342,410]
    for (n,c),x in zip(items,xs):
        ln(240,155,x+32,127); box(x,109,64,18,n,c,fs=6.4)
    subs=[('AS SLICED / AS','LEGACY / cancel',),
          ('speed+accel global,','vel, extrusion,','pause'),
          ('Z-babysteps,','cockpit, material,','temps+fan L2, mesh'),
          ('load/unload, sync,','sounds, LEDs,','nozzle LED'),
          ('cable ties, angles,','lithophane, gaskets,','frames, labels,','plotter'),
          ('vib, level, mesh,','extr, PID, PA, flow,','tower, iron, fil,','KAMP, tests'),
          ('restarts 2x,','shutdown 2x,','save config')]
    col=[0,0, 1,1,1, 2,2,2, 3,3,3, 4,4,4,4, 5,5,5,5, 6,6,6]
    ys=[96,88, 96,88,80, 96,88,80, 96,88,80, 96,88,80,72, 96,88,80,72, 96,88,80]
    for line,y,c in zip([l for grp in subs for l in grp],ys,col):
        d.add(String(xs[c]+32,y,line,fontName='DVS',fontSize=5.9,textAnchor='middle',fillColor=GRAY))
    d.add(String(240,12,'Live Tuning appears during a print — for EVERY start mode, legacy included',fontName='DVS',fontSize=7.5,textAnchor='middle',fillColor=GRAY))
    return d

def d_led():
    d=Drawing(470,168)
    d.add(String(235,158,'LED states + sound volume — the audio-visual vocabulary',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    states=[('idle','#0a1f4d','breathe'),('waiting','#1c4e8c','blink'),('heating','#b34700','chase'),
            ('homing','#00666d','scanner'),('leveling','#4d0033','scanner'),('pid','#1c4e8c','blink'),
            ('printing','#00337a','wave'),('paused','#4d3300','breathe'),('filament','#00333d','chase'),
            ('alarm','#b30000','strobe'),('finished','#1e7d32','twinkle'),('boot','#1c4e8c','scanner')]
    for k,(n,hx,pat) in enumerate(states):
        row, col = divmod(k, 6)
        x = 10 + col * 77
        cy = 128 - row * 38
        c=colors.HexColor(hx)
        for i in range(4): d.add(Circle(x+i*11,cy,4.2,fillColor=c,stroke=0))
        d.add(String(x+16,cy-15,n,fontName='DVSB',fontSize=6.8,textAnchor='middle',fillColor=colors.black))
        d.add(String(x+16,cy-24,pat,fontName='DVS',fontSize=6.2,textAnchor='middle',fillColor=GRAY))
    d.add(String(6,38,'Sound volume dynamics (M300 V):',fontName='DVSB',fontSize=7.5,fillColor=colors.black))
    x=6
    for n,v in [('ticks 0.15',15),('mid 0.35',35),('confirm 0.44',44),('alarm 0.5',50)]:
        d.add(Rect(x,14,90,12,rx=3,fill=1,stroke=0,fillColor=LGRAY))
        d.add(Rect(x,14,90*v/50,12,rx=3,fill=1,stroke=0,fillColor=BLUE))
        d.add(String(x+4,17.5,n,fontName='DVS',fontSize=6.4,fillColor=colors.white)); x+=112
    d.add(String(6,2,'12 frame states · TOGGLE_LEDS off/on · nozzle LED 5: OWN switch — AUTO/ON/OFF + live dimming & color',
                 fontName='DVS',fontSize=7,fillColor=GRAY))
    return d

def d_park():
    d=Drawing(480,190)
    d.add(String(240,178,'Safe parking — every pause, the same anatomy',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    # bed top view
    d.add(Rect(40,30,290,130,fillColor=colors.white,strokeColor=GRAY,strokeWidth=1.2))
    d.add(String(185,15,'bed, top view (objects from the file polygons)',fontName='DVS',fontSize=7,fillColor=GRAY,textAnchor='middle'))
    d.add(Rect(80,70,110,60,rx=3,fillColor=LBLUE,strokeColor=BLUE,strokeWidth=1))
    d.add(String(135,95,'objects',fontName='DVSB',fontSize=8,textAnchor='middle',fillColor=BLUE))
    d.add(Circle(310,145,9,fillColor=GREEN,stroke=0))
    d.add(String(310,128,'PARK',fontName='DVSB',fontSize=6.5,textAnchor='middle',fillColor=GREEN))
    d.add(String(310,120,'farthest',fontName='DVS',fontSize=5.8,textAnchor='middle',fillColor=GREEN))
    d.add(String(310,112,'corner',fontName='DVS',fontSize=5.8,textAnchor='middle',fillColor=GREEN))
    d.add(Line(135,100,295,138,strokeColor=GREEN,strokeWidth=1.2,strokeDashArray=[4,3]))
    d.add(String(60,45,'front left = fallback',fontName='DVS',fontSize=6.5,fillColor=GRAY))
    # side annotations
    notes=[('lift +5 mm (capped below Z max)','never rams the frame'),
           ('retract −3 mm anti-ooze','only if hotend ≥ 170 °C'),
           ('sensor OFF · timeout ∞','no false runout while parked'),
           ('resume: XY first, then Z F300','slow — cannot rip the print off')]
    y=160
    for a,b in notes:
        d.add(String(344,y,a,fontName='DVSB',fontSize=7,fillColor=colors.black))
        d.add(String(344,y-9,b,fontName='DVS',fontSize=6.6,fillColor=GRAY)); y-=30
    return d

def d_runout():
    d=Drawing(480,110)
    d.add(String(240,98,'Filament runout — the friendly way',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    steps=[('filament\nempty','alarm\n6 s repeat'),('pause at NEXT\nlayer boundary','clean layer\nfinish'),('filament\nmode','load new\nfilament'),('insert event','squeak\n+ LED'),('RESUME','purge 15 mm\n+ continue')]
    x=10
    for i,(a,b) in enumerate(steps):
        w=80
        d.add(Rect(x,38,w,34,rx=5,fill=1,stroke=0,fillColor=TEAL if i in (0,2) else BLUE))
        for j,l in enumerate(a.split('\n')): d.add(String(x+w/2,62-j*9,l,fontName='DVSB',fontSize=7,textAnchor='middle',fillColor=colors.white))
        for j,l in enumerate(b.split('\n')): d.add(String(x+w/2,26-j*8,l,fontName='DVS',fontSize=6.2,textAnchor='middle',fillColor=GRAY))
        if i<len(steps)-1:
            d.add(Line(x+w+1,55,x+w+8,55,strokeColor=GRAY,strokeWidth=1.2))
            d.add(Polygon(points=[x+w+8,55,x+w+4,57,x+w+4,53],fillColor=GRAY,stroke=0))
        x+=w+10
    d.add(String(240,8,'no print is ever canceled by runout — direct drive keeps enough filament to finish the layer',
                 fontName='DVS',fontSize=7.3,textAnchor='middle',fillColor=GRAY))
    return d

def d_mesh():
    d=Drawing(480,120)
    d.add(String(240,108,'Bed mesh dispatch — who decides the mesh area?',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    d.add(Rect(10,60,120,30,rx=6,fill=1,stroke=0,fillColor=BLUE))
    d.add(String(70,74,'_CALIBRATE_MESH',fontName='DVSB',fontSize=7.4,textAnchor='middle',fillColor=colors.white))
    d.add(String(70,65,'PROFILE=r2',fontName='DVS',fontSize=6.6,textAnchor='middle',fillColor=colors.white))
    qs=[('KAMP installed + objects + ON?','KAMP adaptive (KAMP cfg)',GREEN,160),
        ('native ADAPTIVE + objects?','Klipper adaptive, margin 5',ORANGE,270),
        ('else','full bed',RED,380)]
    for q,a,c,xx in qs:
        d.add(Line(130,70,xx-4,70,strokeColor=GRAY,strokeWidth=1))
        d.add(Polygon(points=[xx,70,xx-5,72,xx-5,68],fillColor=GRAY,stroke=0))
        d.add(String(xx+2,78,q,fontName='DVSB',fontSize=6.8,fillColor=c))
        d.add(String(xx+2,58,a,fontName='DVS',fontSize=6.6,fillColor=GRAY))
    d.add(String(240,15,'always at BED temperature · saved as profile r2 (session) · persistence is your choice',
                 fontName='DVS',fontSize=7.3,textAnchor='middle',fillColor=GRAY))
    return d

def d_stack():
    d=Drawing(480,150)
    d.add(String(240,138,'Override priority — who wins?',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    rows=[('1  LCD override (ON + value > 0)','your explicit choice',GREEN,300),
          ('2  file value (PRINT_START params / M104…)','what the slicer asks',ORANGE,240),
          ('3  material preset (PLA/PETG/…)','your saved defaults',BLUE,180)]
    y=95
    for a,b,c,w in rows:
        x=(480-w)/2
        d.add(Rect(x,y,w,24,rx=4,fill=1,stroke=0,fillColor=c))
        d.add(String(240,y+12,a,fontName='DVSB',fontSize=8,textAnchor='middle',fillColor=colors.white))
        d.add(String(240,y+3.5,b,fontName='DVS',fontSize=6.4,textAnchor='middle',fillColor=colors.white))
        y-=32
    d.add(String(240,14,'gate: switch OFF or value 0 → the next lower layer rules · AS SLICED bypasses layer 1 entirely (file = king)',
                 fontName='DVS',fontSize=7.3,textAnchor='middle',fillColor=GRAY))
    return d

def d_robot():
    d=Drawing(220,235); line=GRAY
    d.add(Circle(110,170,42,fillColor=colors.HexColor('#eef2f8'),strokeColor=line,strokeWidth=1.2))
    d.add(Circle(110,170,10,fillColor=BLUE,stroke=0)); d.add(Circle(110,170,4.5,fillColor=colors.white,stroke=0))
    d.add(Rect(96,195,28,7,rx=3,fillColor=colors.HexColor('#9bb2cc'),stroke=0))
    d.add(Rect(70,75,80,60,rx=6,fillColor=colors.HexColor('#dfe7f2'),strokeColor=line,strokeWidth=1.2))
    d.add(Rect(84,115,52,8,rx=2,fillColor=BLUE,stroke=0))
    for i in range(4): d.add(Circle(84+i*17,95,5.5,fillColor=colors.HexColor('#0a1f4d'),stroke=0))
    ledc=[colors.HexColor('#0a1f4d'),BLUE,colors.HexColor('#2f6db3'),colors.HexColor('#5b8fd6')]
    for i in range(4): d.add(Circle(60+i*18,42,6,fillColor=ledc[i],stroke=0))
    d.add(String(87,29,'frame LEDs 1-4',fontName='DVS',fontSize=7,fillColor=GRAY))
    d.add(Circle(160,42,6,fillColor=ORANGE,stroke=0)); d.add(String(160,29,'nozzle',fontName='DVS',fontSize=7,fillColor=GRAY,textAnchor='middle'))
    d.add(Line(80,75,70,52,strokeColor=line,strokeWidth=3)); d.add(Line(140,75,150,52,strokeColor=line,strokeWidth=3))
    d.add(Line(60,52,84,52,strokeColor=line,strokeWidth=3)); d.add(Line(136,52,160,52,strokeColor=line,strokeWidth=3))
    return d


# ---- R37 power/electrics diagrams ----
def d_power_tree():
    d=Drawing(480,225)
    d.add(String(240,213,'Voltage map — who feeds whom (and who must not)',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    def box(x,y,w,h,txt,fill,fs=7.5,tc=colors.white):
        d.add(Rect(x,y,w,h,rx=5,fill=1,stroke=0,fillColor=fill))
        for j,l in enumerate(txt.split('\n')): d.add(String(x+w/2,y+h-11-j*9.5,l,fontName='DVSB' if j==0 else 'DVS',fontSize=fs,textAnchor='middle',fillColor=tc))
    box(170,178,140,20,'230 V mains + fuse',GRAY)
    d.add(Line(240,178,240,160,strokeColor=GRAY,strokeWidth=1.3))
    box(170,136,140,24,'[ 24 V PSU ]',BLUE)
    d.add(Line(240,136,240,124,strokeColor=GRAY,strokeWidth=1.3))
    d.add(Line(15,124,465,124,strokeColor=RED,strokeWidth=2))
    d.add(String(15,128,'+24 V rail',fontName='DVS',fontSize=7,fillColor=RED))
    d.add(Line(15,118,465,118,strokeColor=colors.black,strokeWidth=1.4))
    d.add(String(15,108,'0 V (GND)',fontName='DVS',fontSize=7,fillColor=GRAY))
    for x,w,n in [(18,88,'bed heater\n(HB, 20 A fuse)'),(116,88,'hotend\n(E0)'),(214,100,'steppers\nX Y Z E'),(324,60,'fans\n24 V'),(394,68,'probe /\nVIN pin')]:
        box(x,88 if x>300 else 84,w,32,n,colors.HexColor('#4a4a4a'),fs=6.6)
        d.add(Line(x+w/2,124,x+w/2,120 if x>300 else 116,strokeColor=RED,strokeWidth=1))
    box(15,40,205,52,'SKR mini E3 v3.0\nonboard 5 V buck ~1 A max\n(made for the logic — not for a Pi)',BLUE,fs=7.5)
    d.add(Line(60,118,60,92,strokeColor=RED,strokeWidth=1.2))
    box(245,40,220,52,'POWER FROM THE BOARD BUCK = NO\nPi + Neopixels on ~1 A rail:\nbrown-outs, unstable Pi, SD risk',RED,fs=7)
    d.add(Line(100,92,100,118,strokeColor=colors.HexColor('#9bb2cc'),strokeWidth=0))
    box(245,4,220,28,'DCDC 24V->5V >=3 A feeds Pi + LEDs\nBTT DCDC Mode V1.0 (Neo-PWR1) or buck',GREEN,fs=6.8)
    d.add(Line(355,118,355,32,strokeColor=RED,strokeWidth=1.2))
    return d

def d_supply_target():
    d=Drawing(480,232)
    d.add(String(240,220,'Target wiring — one 24 V source, dedicated 5 V rails, ONE ground star',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    def box(x,y,w,h,txt,fill,fs=7.2,tc=colors.white):
        d.add(Rect(x,y,w,h,rx=5,fill=1,stroke=0,fillColor=fill))
        for j,l in enumerate(txt.split('\n')): d.add(String(x+w/2,y+h-11-j*9.5,l,fontName='DVSB' if j==0 else 'DVS',fontSize=fs,textAnchor='middle',fillColor=tc))
    box(12,120,86,64,'24 V PSU\nV+  V-',GRAY)
    d.add(Line(98,168,290,168,strokeColor=RED,strokeWidth=2)); d.add(String(120,172,'+24 V (red)',fontName='DVS',fontSize=7,fillColor=RED))
    box(290,128,96,56,'DCDC 24V->5V\n>=3 A\n(5.0-5.2 V!)',GREEN)
    d.add(Line(386,168,455,168,strokeColor=RED,strokeWidth=2)); d.add(String(390,199,'+5 V (Pi)',fontName='DVS',fontSize=7,fillColor=RED))
    box(120,128,130,56,'SKR mini E3 v3.0\nVIN+ / VIN-\nUART to Pi (3 wires)',BLUE)
    box(372,150,98,44,'Pi Zero 2 W\nUSB-PWR or GPIO\n5V (2/4) + GND (6)',ORANGE,fs=6.8)
    box(372,86,98,44,'5x Neopixel\nexternal 5 V\ndata: PA8 + resistor',PURPLE,fs=6.8)
    d.add(Line(386,150,386,140,strokeColor=RED,strokeWidth=1.6))
    d.add(Line(421,128,421,130,strokeColor=RED,strokeWidth=1.6))
    d.add(Line(386,140,421,140,strokeColor=RED,strokeWidth=1.6)); d.add(String(300,143,'+5 V (LEDs, own rail)',fontName='DVS',fontSize=7,fillColor=RED))
    d.add(Line(300,140,386,140,strokeColor=RED,strokeWidth=1.6))
    d.add(Line(60,120,60,34,strokeColor=colors.black,strokeWidth=1.6))
    d.add(Line(185,128,185,34,strokeColor=colors.black,strokeWidth=1.6))
    d.add(Line(338,128,338,34,strokeColor=colors.black,strokeWidth=1.6))
    d.add(Line(421,86,421,34,strokeColor=colors.black,strokeWidth=1.6))
    d.add(Line(40,34,455,34,strokeColor=colors.black,strokeWidth=3.4))
    d.add(String(250,20,'COMMON GROUND STAR — every V- tied HERE. Only GND is shared: NEVER tie +5 V of two sources!',
                 fontName='DVSB',fontSize=7.6,textAnchor='middle',fillColor=GREEN))
    d.add(String(250,8,'SW_USB jumper on the SKR: REMOVE (no USB-5V backfeed) · measure 5.0-5.2 V BEFORE connecting Pi/LEDs',
                 fontName='DVS',fontSize=7,textAnchor='middle',fillColor=GRAY))
    return d

def d_uart():
    d=Drawing(480,168)
    d.add(String(240,156,'UART serial link — 3 wires instead of USB',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    def pin(x,y,txt,anchor='start'):
        d.add(Circle(x,y,2.6,fillColor=colors.white,strokeColor=GRAY,strokeWidth=1))
        d.add(String(x+6 if anchor=='start' else x-6,y-2.5,txt,fontName='DVS',fontSize=7,fillColor=colors.black,textAnchor='start' if anchor=='start' else 'end'))
    d.add(Rect(14,36,168,100,rx=6,strokeColor=BLUE,strokeWidth=1.2,fillColor=colors.HexColor('#eef2f8')))
    d.add(String(98,122,'Raspberry Pi Zero 2 W',fontName='DVSB',fontSize=8.4,textAnchor='middle',fillColor=BLUE))
    d.add(String(98,111,'GPIO header',fontName='DVS',fontSize=7,textAnchor='middle',fillColor=GRAY))
    d.add(Rect(298,36,168,100,rx=6,strokeColor=GREEN,strokeWidth=1.2,fillColor=colors.HexColor('#eef8f2')))
    d.add(String(382,122,'SKR mini E3 v3.0',fontName='DVSB',fontSize=8.4,textAnchor='middle',fillColor=GREEN))
    d.add(String(382,111,'TFT port',fontName='DVS',fontSize=7,textAnchor='middle',fillColor=GRAY))
    pin(176,92,'pin 8  TXD','end'); pin(176,68,'pin 10 RXD','end'); pin(176,48,'pin 6  GND','end')
    pin(304,92,'RX   (TFT pin 2)'); pin(304,68,'TX   (TFT pin 3)'); pin(304,48,'GND (TFT pin 4)')
    d.add(Line(182,92,298,92,strokeColor=ORANGE,strokeWidth=1.8)); d.add(String(240,97,'TX -> RX',fontName='DVSB',fontSize=7.2,textAnchor='middle',fillColor=ORANGE))
    d.add(Line(182,68,298,68,strokeColor=TEAL,strokeWidth=1.8)); d.add(String(240,73,'RX <- TX',fontName='DVSB',fontSize=7.2,textAnchor='middle',fillColor=TEAL))
    d.add(Line(182,48,298,48,strokeColor=colors.black,strokeWidth=1.8)); d.add(String(240,53,'GND <-> GND  (mandatory!)',fontName='DVSB',fontSize=7.2,textAnchor='middle',fillColor=colors.black))
    d.add(String(240,24,'crossover! Pi-TX goes to board-RX · both boards keep their OWN 5 V supply',
                 fontName='DVS',fontSize=7.4,textAnchor='middle',fillColor=GRAY))
    d.add(String(240,12,'[mcu] serial: /dev/ttyAMA0 · baud 250000 · restart_method: command  (pin numbers: verify against the BTT pinout PDF)',
                 fontName='DVS',fontSize=7,textAnchor='middle',fillColor=GRAY))
    return d

def d_neopixel():
    d=Drawing(480,192)
    d.add(String(240,180,'Neopixels on their own 5 V — capacitor, resistor, star ground',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    d.add(Rect(14,86,104,54,rx=5,stroke=0,fillColor=GREEN))
    d.add(String(66,124,'DCDC 5 V >=3 A',fontName='DVSB',fontSize=7.6,textAnchor='middle',fillColor=colors.white))
    d.add(String(66,113,'5.0-5.2 V measured',fontName='DVS',fontSize=6.6,textAnchor='middle',fillColor=colors.white))
    d.add(String(66,102,'for the LEDs',fontName='DVS',fontSize=6.6,textAnchor='middle',fillColor=colors.white))
    d.add(Line(118,132,450,132,strokeColor=RED,strokeWidth=2)); d.add(String(448,136,'+5 V',fontName='DVS',fontSize=7,fillColor=RED,textAnchor='end'))
    d.add(Line(118,100,450,100,strokeColor=colors.black,strokeWidth=1.6)); d.add(String(448,90,'GND',fontName='DVS',fontSize=7,fillColor=GRAY,textAnchor='end'))
    d.add(Line(160,132,160,116,strokeColor=BLUE,strokeWidth=1.6)); d.add(Line(172,132,172,116,strokeColor=BLUE,strokeWidth=1.6))
    d.add(Line(160,100,160,116,strokeColor=BLUE,strokeWidth=1.6)); d.add(Line(172,100,172,116,strokeColor=BLUE,strokeWidth=1.6))
    d.add(String(166,143,'1000 uF',fontName='DVSB',fontSize=7,textAnchor='middle',fillColor=BLUE))
    for i in range(5):
        x=214+i*46
        d.add(Circle(x,116,10,fillColor=colors.HexColor('#0a1f4d') if i==0 else BLUE,stroke=0))
        d.add(String(x,113,str(i+1),fontName='DVS',fontSize=7,textAnchor='middle',fillColor=colors.white))
        if i<4: d.add(Line(x+12,116,x+32,116,strokeColor=GRAY,strokeWidth=1.2,strokeDashArray=[2,2]))
    d.add(String(306,136,'pixels 1-5 (frame) — nozzle LED 5th',fontName='DVS',fontSize=6.8,textAnchor='middle',fillColor=GRAY))
    d.add(Rect(150,20,120,26,rx=4,stroke=0,fillColor=PURPLE))
    d.add(String(210,32,'SKR data pin PA8',fontName='DVSB',fontSize=7.4,textAnchor='middle',fillColor=colors.white))
    d.add(String(210,26,'3.3 V logic',fontName='DVS',fontSize=6.6,textAnchor='middle',fillColor=colors.white))
    d.add(Rect(292,25,88,16,rx=3,stroke=0,fillColor=LGRAY))
    d.add(String(336,29.5,'330-470 Ohm',fontName='DVSB',fontSize=7,textAnchor='middle',fillColor=colors.black))
    d.add(Line(270,33,292,33,strokeColor=PURPLE,strokeWidth=1.8))
    d.add(Line(380,33,421,33,strokeColor=PURPLE,strokeWidth=1.8)); d.add(Line(421,33,421,104,strokeColor=PURPLE,strokeWidth=1.8))
    d.add(String(340,16,'series resistor right before DIN — protects pixel 1',fontName='DVS',fontSize=6.8,textAnchor='middle',fillColor=GRAY))
    d.add(String(70,66,'worst case 5 px x 60 mA = 0.3 A (full white) — firmware LED budget keeps it ~0.1 A',
                 fontName='DVS',fontSize=7.2,fillColor=GRAY))
    d.add(String(70,54,'SKR-GND and LED-GND MUST be tied together (star) or data has no reference',
                 fontName='DVSB',fontSize=7.2,fillColor=GREEN))
    return d


def d_prime():
    d=Drawing(480,132)
    d.add(String(240,120,'Prime line — probe-safe: only X, start right, drawn toward x=0',fontName='DVSB',fontSize=9.5,textAnchor='middle',fillColor=BLUE))
    d.add(Rect(60,18,300,84,strokeColor=GRAY,strokeWidth=1.2,fillColor=colors.HexColor('#eef2f8')))
    d.add(Rect(60,18,16,84,fillColor=colors.HexColor('#f6dede'),strokeColor=GRAY,strokeWidth=0.5))
    d.add(Rect(344,18,16,84,fillColor=colors.HexColor('#f6dede'),strokeColor=GRAY,strokeWidth=0.5))
    d.add(String(68,104,'margin 5 mm',fontName='DVS',fontSize=6,fillColor=GRAY))
    d.add(String(352,104,'margin 5 mm',fontName='DVS',fontSize=6,fillColor=GRAY))
    d.add(Rect(180,42,120,44,rx=4,fillColor=LBLUE,strokeColor=BLUE,strokeWidth=1))
    d.add(String(240,60,'objects',fontName='DVSB',fontSize=8,textAnchor='middle',fillColor=BLUE))
    d.add(String(240,50,'(file polygons)',fontName='DVS',fontSize=6.6,textAnchor='middle',fillColor=BLUE))
    d.add(Circle(284,34,3.4,fillColor=GREEN,strokeColor=GREEN))
    d.add(Line(284,34,96,34,strokeColor=GREEN,strokeWidth=3.5))
    d.add(Polygon(points=[84,34,96,39,96,29],fillColor=GREEN,stroke=0))
    d.add(String(284,42,'start (right)',fontName='DVSB',fontSize=7,textAnchor='middle',fillColor=GREEN))
    d.add(String(184,42,'up to 110 mm · width 1.2 mm · toward x=0',fontName='DVSB',fontSize=7,textAnchor='middle',fillColor=GREEN))
    d.add(String(184,24,'[probe] x/y offset respected — nozzle AND probe stay on the bed',fontName='DVS',fontSize=6.8,textAnchor='middle',fillColor=GRAY))
    d.add(String(52,10,'x=0',fontName='DVS',fontSize=6.6,fillColor=GRAY))
    d.add(String(352,10,'x=max',fontName='DVS',fontSize=6.6,fillColor=GRAY))
    d.add(String(400,70,'_PROBE_STOW',fontName='DVSB',fontSize=8,fillColor=PURPLE))
    d.add(String(400,60,'runs first',fontName='DVS',fontSize=7,fillColor=PURPLE))
    d.add(String(400,49,'KAMP LINE purge',fontName='DVS',fontSize=7,fillColor=GRAY))
    d.add(String(400,39,'skipped if probe',fontName='DVS',fontSize=7,fillColor=GRAY))
    d.add(String(400,29,'offset &gt; 10 mm',fontName='DVS',fontSize=7,fillColor=GRAY))
    d.add(Line(396,66,320,52,strokeColor=PURPLE,strokeWidth=1,strokeDashArray=[3,2]))
    return d

# ============================ DOC ============================
class Mark(Flowable):
    ch=''
    def __init__(self, ch=''):
        super().__init__(); self.ch=ch; self.width=0; self.height=0
    def draw(self): pass

class Doc(BaseDocTemplate):
    def __init__(self, fn):
        super().__init__(fn, pagesize=A4, leftMargin=17*mm, rightMargin=17*mm, topMargin=16*mm,
                         bottomMargin=16*mm, title='R2-D2 Macro System — Manual (illustrated edition)',
                         author='klipper-e3-r2d2')
        f=Frame(self.leftMargin,self.bottomMargin,self.width,self.height,id='f')
        self.addPageTemplates([PageTemplate(id='pt',frames=[f],onPage=self.footer,onPageEnd=self.header)])
        self.ch=''
    def afterFlowable(self, fl):
        if isinstance(fl, Mark): self.ch=fl.ch
    def header(self,c,doc):
        if not self.ch: return
        c.saveState(); c.setFont('DVSB',7.5); c.setFillColor(BLUE)
        c.drawRightString(A4[0]-17*mm,A4[1]-10*mm,self.ch); c.restoreState()
    def footer(self,c,doc):
        c.saveState(); c.setFont('DVS',7.5); c.setFillColor(GRAY)
        c.drawString(17*mm,9*mm,'R2-D2 Macro System · R2-2026-10-13.102 · user handbook')
        c.drawRightString(A4[0]-17*mm,9*mm,f'Page {doc.page}')
        c.setStrokeColor(colors.HexColor('#c9d4e4')); c.setLineWidth(0.6); c.line(17*mm,12*mm,A4[0]-17*mm,12*mm)
        c.restoreState()

# ---- R82 diagrams: file flow, calibration ladder, font specimen, label anatomy, range variants --

def _font_lines(m, text, fname, x0, base, cap_px, stroke=0.8, col=None):
    """render stroke-font text with the REAL glyph data from r2_postproc.
    Returns (list_of_PolyLine, advance_end_x). cap_px = cap height in px."""
    col = col or colors.black
    g = m._label_glyphs(fname)
    scale = cap_px / max(0.5, g['cap_units'])
    out = []
    x = x0
    for ch in text:
        adv, sts = g.get(ch, (3.0, []))
        for st in sts:
            pts = []
            for (px, py) in st:
                pts.append(x + px * scale)
                pts.append(base - (py - g['baseline']) * scale)
            if len(pts) >= 4:
                out.append(PolyLine(points=pts, strokeColor=col, strokeWidth=stroke))
        x += adv * scale
    return out, x


def d_file_flow():
    d = Drawing(480, 205)
    d.add(String(240, 195, 'Every file gets intercepted — the flow from upload to print', fontName='DVSB', fontSize=9.5, textAnchor='middle', fillColor=BLUE))
    def box(x, y, w, h, t1, t2='', c=BLUE, fs=7.2):
        d.add(Rect(x, y, w, h, rx=5, fill=1, stroke=0, fillColor=c))
        d.add(String(x + w / 2, y + h / 2 + (2.4 if t2 else 0), t1, fontName='DVSB', fontSize=fs, textAnchor='middle', fillColor=colors.white))
        if t2:
            d.add(String(x + w / 2, y + h / 2 - 6, t2, fontName='DVS', fontSize=6.2, textAnchor='middle', fillColor=colors.white))
    def arr(x1, y1, x2, y2):
        d.add(Line(x1, y1, x2, y2, strokeColor=GRAY, strokeWidth=1.1))
        import math as _fm
        a = _fm.atan2(y2 - y1, x2 - x1)
        for da in (0, 2.55, -2.55):
            d.add(Polygon(points=[x2, y2, x2 - 6 * _fm.cos(a - da), y2 - 6 * _fm.sin(a - da)], fillColor=GRAY, stroke=0))
    box(160, 168, 160, 20, 'upload / copy / scp', 'Mainsail · USB · scp', colors.HexColor('#2f6db3'))
    box(160, 136, 160, 20, 'gcodes folder', 'systemd service watches (1 s)', GRAY)
    box(120, 100, 240, 22, 'r2_postproc.py — the interceptor', '', BLUE)
    box(8, 54, 145, 34, 'G-code', 'tagged: LAYER_MARK +', GREEN)
    d.add(String(80, 56, 'APPLY_TYPE + _FILE_INFO', fontName='DVS', fontSize=6.0, textAnchor='middle', fillColor=colors.white))
    box(160, 52, 150, 32, 'images / text', 'png/jpg/svg/pdf/txt ->', GREEN)
    d.add(String(235, 56, 'pen-plot file in place', fontName='DVS', fontSize=6.0, textAnchor='middle', fillColor=colors.white))
    box(318, 54, 150, 34, 'generators', 'Range · Labels · towers', GREEN)
    d.add(String(393, 56, '· bridge · resonance', fontName='DVS', fontSize=6.0, textAnchor='middle', fillColor=colors.white))
    box(160, 14, 240, 22, 'start dialog: AS LEGACY or AS SLICED', '', ORANGE)
    d.add(String(240, 40, 'PRINT -> held at position 0 -> decision', fontName='DVS', fontSize=6.4, textAnchor='middle', fillColor=GRAY))
    d.add(String(240, 2, 'then: homing -> bed temp -> adaptive mesh -> nozzle wipe -> purge -> L1 rules -> layer 2 = L2', fontName='DVS', fontSize=6.6, textAnchor='middle', fillColor=GRAY))
    arr(240, 168, 240, 156); arr(240, 136, 240, 122)
    arr(200, 100, 80, 88); arr(240, 100, 240, 84); arr(285, 100, 393, 88)
    arr(240, 52, 240, 36)
    return d


def d_calib_ladder():
    d = Drawing(480, 118)
    d.add(String(240, 108, 'The calibration ladder — the Maintenance menu follows it top to bottom', fontName='DVSB', fontSize=9.5, textAnchor='middle', fillColor=BLUE))
    r1 = ['1 PID', '2 Leveling', '3 Bed mesh', '4 Extruder', '5 Shaper']
    r2 = ['6 Temp tower', '7 PA + smooth', '8 Flow', '9 Retract', '10 Bridge', '11 Ironing']
    def row(items, y, c, label):
        d.add(String(4, y + 6, label, fontName='DVSB', fontSize=6.4, fillColor=c))
        x = 74
        w = (452 - 74 - 6 * (len(items) - 1)) / len(items)
        for i, s in enumerate(items):
            d.add(Rect(x, y, w, 20, rx=5, fill=1, stroke=0, fillColor=c))
            d.add(String(x + w / 2, y + 6.5, s, fontName='DVSB', fontSize=7.0, textAnchor='middle', fillColor=colors.white))
            if i < len(items) - 1:
                d.add(Line(x + w + 0.5, y + 10, x + w + 5.5, y + 10, strokeColor=GRAY, strokeWidth=1.1))
                d.add(Polygon(points=[x + w + 6, y + 10, x + w + 2, y + 11.8, x + w + 2, y + 8.2], fillColor=GRAY, stroke=0))
            x += w + 6
    row(r1, 78, BLUE, 'once per\nprinter')
    row(r2, 36, colors.HexColor('#2f8f4e'), 'per\nmaterial')
    d.add(Line(240, 78, 240, 60, strokeColor=GRAY, strokeWidth=1.1))
    d.add(Polygon(points=[240, 57, 237.4, 62, 242.6, 62], fillColor=GRAY, stroke=0))
    d.add(String(252, 64, 'shaper honest -> PA/flow tests are meaningful', fontName='DVS', fontSize=6.4, fillColor=GRAY))
    d.add(String(240, 14, 'then: care — Clean Nozzle · Filament (cold pull) · Z Gantry Sync · KAMP · Tests', fontName='DVS', fontSize=7.0, textAnchor='middle', fillColor=GRAY))
    return d


def d_font_specimen():
    import importlib.util as _ilu
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'r2_postproc.py')
    _sp = _ilu.spec_from_file_location('r2p_fonts', _p)
    _m = _ilu.module_from_spec(_sp); _sp.loader.exec_module(_m)
    d = Drawing(480, 208)
    d.add(String(240, 199, 'The five label fonts — same cap height, real glyph data from the generator', fontName='DVSB', fontSize=9.5, textAnchor='middle', fillColor=BLUE))
    rows = [('SMOOTH', 'proportional, handwriting-like — the all-rounder'),
            ('MONO', 'even letter widths — technical, numbers'),
            ('COND', 'Oswald: condensed + tall x-height — the small-text workhorse'),
            ('NARROW', 'Roboto Condensed: clean + narrow'),
            ('CAPS', 'Bebas: everything prints as capitals — key fobs')]
    y = 168
    for fname, desc in rows:
        lines, xe = _font_lines(_m, 'Garage 0815', fname, 96, y, 15.5)
        for ln in lines:
            d.add(ln)
        d.add(String(8, y - 4, fname, fontName='DVSB', fontSize=7.6, fillColor=BLUE))
        d.add(String(96, y - 22, desc, fontName='DVS', fontSize=6.2, fillColor=GRAY))
        d.add(Line(96, y - 15.5, min(xe, 470), y - 15.5, strokeColor=colors.HexColor('#dfe6f0'), strokeWidth=0.5))
        y -= 32.5
    d.add(String(240, 6, 'stroke = letter line width (0.6 mm = one line per stroke) · letters never get shorter — the label grows', fontName='DVS', fontSize=6.6, textAnchor='middle', fillColor=GRAY))
    return d


def d_label_anatomy():
    import importlib.util as _ilu
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'r2_postproc.py')
    _sp = _ilu.spec_from_file_location('r2p_fonts', _p)
    _m = _ilu.module_from_spec(_sp); _sp.loader.exec_module(_m)
    d = Drawing(480, 150)
    d.add(String(240, 141, 'Label anatomy — hole, margins, auto-fit and the grown fallback', fontName='DVSB', fontSize=9.5, textAnchor='middle', fillColor=BLUE))
    # left: normal 50x15 label, hole LEFT  ·  right: grown label (same scale!)
    sc = 2.7
    y0 = 48
    x0, w = 30, 50 * sc
    x1, w1 = 300, 61 * sc
    h = 15 * sc
    d.add(Rect(x0, y0, w, h, rx=3, fillColor=colors.HexColor('#f4f7fb'), strokeColor=BLUE, strokeWidth=1.2))
    d.add(Circle(x0 + 2 * sc, y0 + h / 2, 2.5 * sc, fillColor=colors.white, strokeColor=GRAY, strokeWidth=1.0))
    lines, xe = _font_lines(_m, 'GARAGE', 'COND', x0 + 10 * sc, y0 + 5.4 * sc, 7.6 * sc, stroke=1.0, col=BLUE)
    for ln in lines:
        d.add(ln)
    d.add(String(x0 + w / 2, y0 + h + 12, '50 × 15 mm · hole LEFT, 2 mm from the edge', fontName='DVS', fontSize=6.4, textAnchor='middle', fillColor=GRAY))
    d.add(String(x0 + w / 2, y0 + h + 4, 'text fills ~94% of the free area', fontName='DVS', fontSize=6.0, textAnchor='middle', fillColor=GRAY))
    d.add(Line(x0, y0 - 7, x0 + 2 * sc, y0 - 7, strokeColor=GREEN, strokeWidth=1.0))
    d.add(String(x0 + 1.0 * sc, y0 - 16, '2mm', fontName='DVS', fontSize=5.4, textAnchor='middle', fillColor=GREEN))
    # right: grown label (too long text -> grow), SAME scale
    d.add(Rect(x1, y0, w1, h, rx=3, fillColor=colors.HexColor('#f4f7fb'), strokeColor=GREEN, strokeWidth=1.4))
    d.add(Circle(x1 + 2 * sc, y0 + h / 2, 2.5 * sc, fillColor=colors.white, strokeColor=GRAY, strokeWidth=1.0))
    lines, xe = _font_lines(_m, 'WERKSTATT', 'COND', x1 + 10 * sc, y0 + 5.4 * sc, 7.6 * sc, stroke=1.0, col=GREEN)
    for ln in lines:
        d.add(ln)
    d.add(String(x1 + w1 / 2, y0 + h + 12, 'same text too long -> label GROWS (50 -> 61 mm)', fontName='DVS', fontSize=6.4, textAnchor='middle', fillColor=GREEN))
    d.add(String(x1 + w1 / 2, y0 + h + 4, 'text is NEVER shortened · grows up to bed size (width first)', fontName='DVS', fontSize=6.0, textAnchor='middle', fillColor=GRAY))
    # center arrows between panels
    d.add(Line(x0 + w + 10, y0 + h / 2, x1 - 10, y0 + h / 2, strokeColor=GRAY, strokeWidth=1.0, strokeDashArray=[3, 2]))
    d.add(String((x0 + w + x1) / 2, y0 + h / 2 + 6, 'auto-fit', fontName='DVS', fontSize=6.2, textAnchor='middle', fillColor=GRAY))
    d.add(String(240, 14, 'hole NONE/LEFT/RIGHT/TOP/BOTTOM · stroke = line width · floor cap 2.8 mm (readability with a 0.6 nozzle)', fontName='DVS', fontSize=6.6, textAnchor='middle', fillColor=GRAY))
    return d


def d_range_variants():
    d = Drawing(480, 158)
    d.add(String(240, 149, 'Range generator — floor shapes, fills and the brim (top views of the SAME layer)', fontName='DVSB', fontSize=9.5, textAnchor='middle', fillColor=BLUE))
    # the demo layer: L-shape (concave) — vertical bar + horizontal bar
    def hatch_rect(x0, y0, w, h, step, col):
        # 45-degree hatch across a rect, clipped by sampling (schematic)
        i = -h
        while i < w:
            xa, ya, xb, yb = x0 + i, y0, x0 + i + h, y0 + h
            seg = []
            for k in range(0, 101):
                t = k / 100.0
                x = xa + (xb - xa) * t
                y = ya + (yb - ya) * t
                ins = (x0 - 0.01 <= x <= x0 + w + 0.01
                       and y0 - 0.01 <= y <= y0 + h + 0.01)
                if ins:
                    seg.append((x, y))
                else:
                    if len(seg) > 1:
                        d.add(Line(seg[0][0], seg[0][1], seg[-1][0], seg[-1][1],
                                   strokeColor=col, strokeWidth=0.55))
                    seg = []
            if len(seg) > 1:
                d.add(Line(seg[0][0], seg[0][1], seg[-1][0], seg[-1][1],
                           strokeColor=col, strokeWidth=0.55))
            i += step
    def panel(x, title, sub, hull=False, solid=False, brim=0, col=BLUE):
        d.add(String(x + 33, 128, title, fontName='DVSB', fontSize=6.9, textAnchor='middle', fillColor=col))
        d.add(String(x + 33, 16, sub, fontName='DVS', fontSize=5.6, textAnchor='middle', fillColor=GRAY))
        ox, oy, s = x + 4, 38, 2.35
        # L-shape geometry in local units
        bar_h = (10, 4, 30, 12)    # x, y, w, h of the horizontal bar
        col_v = (22, 16, 18, 14)   # the vertical column (right side)
        # outline polygon (L)
        Lp = [(10, 4), (40, 4), (40, 30), (22, 30), (22, 16), (10, 16)]
        d.add(Polygon(points=[c for (a, b) in Lp for c in (ox + a * s, oy + b * s)],
                      fillColor=colors.HexColor('#eef3fa'), strokeColor=col, strokeWidth=1.2))
        step = 3.2 if solid else 6.0
        if hull:
            # convex hull rect + hatch over everything
            hatch_rect(ox + 10 * s, oy + 4 * s, 30 * s, 26 * s, step * s, colors.HexColor('#9db4d6'))
            d.add(Polygon(points=[c for (a, b) in [(10, 4), (40, 4), (40, 30), (10, 30)] for c in (ox + a * s, oy + b * s)],
                          fillColor=None, strokeColor=col, strokeWidth=1.2, strokeDashArray=[3, 2]))
        else:
            # true outline: hatch only the L (two rects)
            hatch_rect(ox + 10 * s, oy + 4 * s, 30 * s, 12 * s, step * s, colors.HexColor('#9db4d6'))
            hatch_rect(ox + 22 * s, oy + 16 * s, 18 * s, 14 * s, step * s, colors.HexColor('#9db4d6'))
        if brim:
            for k in range(brim):
                off = 2.4 * (k + 1)
                d.add(Polygon(points=[c for (a, b) in [(10 - off, 4 - off), (40 + off, 4 - off), (40 + off, 30 + off), (10 - off, 30 + off)] for c in (ox + a * s, oy + b * s)],
                              fillColor=None, strokeColor=GREEN, strokeWidth=0.9))
    panel(6, 'FOOTPRINT + GRID', 'hull bridges concavities', hull=True)
    panel(126, 'OUTLINE + GRID', 'outline follows the wall', col=GREEN)
    panel(246, 'FOOTPRINT + SOLID', 'lines overlap: solid', hull=True, solid=True)
    panel(358, 'BRIM (Brim 3)', 'zero-gap loops', hull=True, brim=3, col=ORANGE)
    d.add(String(240, 28, 'Floor = generated raft UNDER the section (welds flush, zero gap) · Top = solid cap OVER the last layer', fontName='DVS', fontSize=6.4, textAnchor='middle', fillColor=GRAY))
    return d

E=[]

# ---- R86 diagrams: cable-tie anatomy + angle-plate anatomy ----------------------

def d_tie_anatomy():
    d = Drawing(480, 208)
    d.add(String(240, 199, 'Cable tie anatomy — strap, teeth, and the auto-scaled closure head',
                 fontName='DVSB', fontSize=9.5, textAnchor='middle', fillColor=BLUE))

    # ---- top view: head + strap with teeth + tip (left half of the panel) ----
    y0 = 96
    d.add(String(120, 180, 'TOP VIEW (width 8 mm example)', fontName='DVSB', fontSize=6.9,
                 textAnchor='middle', fillColor=GRAY))
    sc = 2.1
    # R89 CLASSIC head: HL = width+4.5 = 12.5, HW = width+2.6 = 10.6 at width 8
    hx, hy, hl, hw = 30, y0, 12.5 * sc, 10.6 * sc
    d.add(Rect(hx, hy, hl, hw, fillColor=colors.HexColor('#eef3fa'), strokeColor=BLUE, strokeWidth=1.3))
    slotw = 8.5 * sc                    # slot = width + 0.5
    cy = hy + hw / 2
    # slot channel (open through the head)
    d.add(Rect(hx, cy - slotw / 2, hl, slotw, fillColor=colors.white, strokeColor=GRAY, strokeWidth=0.8))
    # pawl strip at the channel ENTRY (top view: the short strip at the left end)
    d.add(Rect(hx + 1.2 * sc, cy - (slotw / 2 + 0.9), max(2.5, 8 * 0.4) * sc, slotw + 1.8,
               fillColor=colors.HexColor('#bcd0ea'), strokeColor=BLUE, strokeWidth=0.8))
    d.add(String(hx + 2.8 * sc, cy + slotw / 2 + 12, 'pawl strip (entry)', fontName='DVS',
                 fontSize=5.8, textAnchor='middle', fillColor=GRAY))
    # strap with teeth
    sx = hx + hl
    d.add(Rect(sx, cy - 8 * sc / 2, 120 * sc, 8 * sc, fillColor=colors.HexColor('#eef3fa'),
               strokeColor=BLUE, strokeWidth=1.2))
    # chamfered tip
    d.add(Polygon(points=[sx + 120 * sc, cy - 4 * sc * 0.75, sx + 116 * sc, cy - 4 * sc,
                          sx + 116 * sc, cy + 4 * sc, sx + 120 * sc, cy + 4 * sc * 0.75],
                  fillColor=colors.HexColor('#eef3fa'), strokeColor=BLUE, strokeWidth=1.0))
    # teeth (low nub + steep lock flank, pitch 3.6 at width 8)
    tx = sx + 4 * sc
    while tx < sx + 112 * sc:
        d.add(Rect(tx, cy - 4 * sc, 1.8 * sc, 8 * sc, fillColor=colors.HexColor('#9db4d6'),
                   strokeColor=BLUE, strokeWidth=0.6))
        d.add(Rect(tx + 0.6 * sc, cy - 4 * sc, 0.8 * sc, 8 * sc, fillColor=colors.HexColor('#5a7fb5'),
                   strokeColor=None))
        tx += 3.6 * sc
    d.add(String(hx + hl / 2, hy - 12, 'head (width+4.5) x (width+2.6) · slot = width + 0.5', fontName='DVS',
                 fontSize=6.2, textAnchor='middle', fillColor=GRAY))
    d.add(String(sx + 60 * sc, cy + 4 * sc + 8, 'teeth: low ramp (light) + steep flank (dark), pitch 0.45 x width',
                 fontName='DVS', fontSize=6.2, textAnchor='middle', fillColor=GRAY))
    d.add(String(sx + 118 * sc, cy - 14, 'chamfered tip', fontName='DVS', fontSize=5.8,
                 textAnchor='end', fillColor=GRAY))
    # dimension line: strap width
    d.add(Line(sx + 20 * sc, cy - 4 * sc - 6, sx + 20 * sc, cy + 4 * sc + 6,
               strokeColor=GREEN, strokeWidth=0.9))
    d.add(String(sx + 22 * sc, cy - 4 * sc - 15, 'Width 2-12', fontName='DVS', fontSize=5.8,
                 textAnchor='middle', fillColor=GREEN))

    # ---- cross-section through the head (right half) -------------------------
    x1 = 300
    d.add(String(390, 180, 'HEAD CROSS-SECTION (CLASSIC)', fontName='DVSB', fontSize=6.9,
                 textAnchor='middle', fillColor=GRAY))
    s = 2.1
    bx, by = x1, 100
    # layers bottom-up: base plate (2), channel band (layers+3), ceiling (2)
    zb = [12, 9]           # heights of the two base layers
    ch = 18                # channel band
    ce = [5, 5]            # ceiling layers
    # base plate (the channel floor)
    d.add(Rect(bx, by, 60 * s, (zb[0] + zb[1]) * 1.0, fillColor=colors.HexColor('#dbe6f4'),
               strokeColor=BLUE, strokeWidth=1.1))
    d.add(String(bx - 4, by + 14, 'base', fontName='DVS', fontSize=5.8, textAnchor='end', fillColor=GRAY))
    # channel walls
    wy = by + zb[0] + zb[1]
    wallh = ch
    d.add(Rect(bx, wy, 60 * s, 6, fillColor=colors.HexColor('#dbe6f4'), strokeColor=BLUE, strokeWidth=1.0))
    d.add(Rect(bx, wy + wallh - 6, 60 * s, 6, fillColor=colors.HexColor('#dbe6f4'), strokeColor=BLUE, strokeWidth=1.0))
    # strap + teeth inside the channel
    d.add(Rect(bx + 8, wy + 6, 44, 8, fillColor=colors.HexColor('#9db4d6'),
               strokeColor=BLUE, strokeWidth=0.8))
    d.add(Rect(bx + 18, wy + 14, 6, 4, fillColor=colors.HexColor('#5a7fb5'), strokeColor=None))
    d.add(Rect(bx + 30, wy + 14, 6, 4, fillColor=colors.HexColor('#5a7fb5'), strokeColor=None))
    d.add(String(bx + 30, wy + 24, 'strap + teeth ride in the channel (1 layer clearance)',
                 fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=GRAY))
    # ceiling band: side walls + the PAWL at the entry reaching one layer DOWN
    cyy = wy + wallh
    d.add(Rect(bx, cyy, 8, 10, fillColor=colors.HexColor('#dbe6f4'), strokeColor=BLUE, strokeWidth=1.0))
    d.add(String(bx + 6, cyy + 22, 'entry', fontName='DVS', fontSize=5.6, textAnchor='end', fillColor=GRAY))
    d.add(Rect(bx + 8, cyy, 44, 5, fillColor=colors.HexColor('#dbe6f4'), strokeColor=BLUE, strokeWidth=0.9))
    # the pawl: hangs one layer into the slot, right at the entry
    d.add(Rect(bx + 8, cyy - 5, 10, 5, fillColor=colors.HexColor('#bcd0ea'), strokeColor=BLUE, strokeWidth=0.9))
    d.add(String(bx + 62, cyy + 32, 'pawl (darker): the first ceiling layer drops INTO the slot at the entry —'
                 ' the tooth flanks catch under it',
                 fontName='DVS', fontSize=5.6, textAnchor='middle', fillColor=GRAY))
    d.add(Rect(bx + 52, cyy, 10 * s - 52 + 60, 10, fillColor=colors.HexColor('#dbe6f4'),
               strokeColor=BLUE, strokeWidth=1.0))
    d.add(String(bx + 84, cyy + 22, 'exit (anchored)', fontName='DVS', fontSize=5.6,
                 textAnchor='start', fillColor=GRAY))

    # ---- bottom strip: the two variants + width auto-scaling -----------------
    d.add(String(240, 84, 'THE TWO CLOSURES', fontName='DVSB', fontSize=6.9,
                 textAnchor='middle', fillColor=GRAY))
    # CLASSIC: small head box, pawl strip at the entry (left), tooth strap
    x = 40
    d.add(String(x + 52, 70, 'CLASSIC — one-way', fontName='DVSB', fontSize=6.8,
                 textAnchor='middle', fillColor=BLUE))
    yy = 30
    d.add(Rect(x, yy, 104, 28, fillColor=colors.HexColor('#eef3fa'), strokeColor=BLUE, strokeWidth=1.2))
    d.add(Rect(x + 6, yy + 4, 26, 20, fillColor=colors.HexColor('#dbe6f4'), strokeColor=BLUE, strokeWidth=1.0))
    d.add(Rect(x + 9, yy + 16, 5, 8, fillColor=colors.HexColor('#bcd0ea'), strokeColor=BLUE, strokeWidth=0.9))
    d.add(String(x + 19, yy + 34, 'pawl', fontName='DVS', fontSize=5.4, textAnchor='middle', fillColor=BLUE))
    for k in range(4):
        d.add(Rect(x + 40 + k * 12, yy + 10, 4, 8, fillColor=colors.HexColor('#9db4d6'),
                   strokeColor=BLUE, strokeWidth=0.7))
    d.add(String(x + 52, yy - 10, 'thread in, pull tight, cut to remove', fontName='DVS',
                 fontSize=5.6, textAnchor='middle', fillColor=GRAY))
    # LOOP: frame ring with open slot + strap with beads
    x = 260
    d.add(String(x + 52, 70, 'LOOP — adjustable + reusable', fontName='DVSB', fontSize=6.8,
                 textAnchor='middle', fillColor=GREEN))
    yy = 30
    d.add(Rect(x, yy, 104, 28, fillColor=colors.HexColor('#eef3fa'), strokeColor=GREEN, strokeWidth=1.2))
    d.add(Rect(x + 6, yy + 4, 30, 20, fillColor=colors.HexColor('#dbe6f4'), strokeColor=GREEN, strokeWidth=1.0))
    d.add(Rect(x + 14, yy + 9, 18, 10, fillColor=colors.white, strokeColor=GRAY, strokeWidth=0.8))
    d.add(String(x + 21, yy + 34, 'loop (open slot)', fontName='DVS', fontSize=5.4,
                 textAnchor='middle', fillColor=GREEN))
    for k in range(4):
        bxk = x + 42 + k * 12
        d.add(Polygon(points=[bxk + 3, yy + 14 + 3, bxk + 6, yy + 14, bxk + 3, yy + 14 - 3, bxk, yy + 14],
                      fillColor=colors.HexColor('#9db4d6'), strokeColor=GREEN, strokeWidth=0.8))
    d.add(String(x + 66, yy + 34, 'beads', fontName='DVS', fontSize=5.4,
                 textAnchor='middle', fillColor=GREEN))
    d.add(String(x + 52, yy - 10, 'catches at every bead, lifts back out', fontName='DVS',
                 fontSize=5.6, textAnchor='middle', fillColor=GRAY))

    # width auto-scaling mini strip
    d.add(String(240, 10, 'Width sets everything: width 2 -> head 8x6.6 · width 8 -> head 12.5x10.6 · '
                 'width 12 -> head 16.5x14.6 (slot, tooth pitch, bead gap scale with it)',
                 fontName='DVS', fontSize=6.2, textAnchor='middle', fillColor=GRAY))
    return d


def d_litho_anatomy():
    d = Drawing(480, 208)
    d.add(String(240, 199, 'Lithophane — brightness becomes thickness, levels posterize',
                 fontName='DVSB', fontSize=9.5, textAnchor='middle', fillColor=BLUE))

    # ---- left: the standing plate (side view) with thickness ramp -----------
    d.add(String(110, 182, 'SIDE VIEW — STANDING ON THE BED', fontName='DVSB', fontSize=6.9,
                 textAnchor='middle', fillColor=GRAY))
    x0, y0 = 40, 40
    d.add(Rect(x0, y0, 24, 6, fillColor=colors.HexColor('#dbe6f4'), strokeColor=GRAY, strokeWidth=0.7))
    d.add(String(x0 + 12, y0 - 10, 'brim', fontName='DVS', fontSize=5.6, textAnchor='middle', fillColor=GRAY))
    # the plate: thickness ramps from 0.7 (light) to 3.0 (dark)
    steps = 12
    for k in range(steps):
        h = 14 + k * 5
        shade = 235 - k * 16
        d.add(Rect(x0 + 24 + k * 9, y0, 9, h,
                   fillColor=colors.Color(shade / 255.0, shade / 255.0, shade / 255.0),
                   strokeColor=GRAY, strokeWidth=0.5))
    d.add(String(x0 + 24, y0 + 96, 'thin 0.7 mm = light (glows first)', fontName='DVS',
                 fontSize=5.8, textAnchor='start', fillColor=GREEN))
    d.add(String(x0 + 24 + 9 * steps, y0 + 96, 'thick 3.0 mm = dark', fontName='DVS',
                 fontSize=5.8, textAnchor='end', fillColor=GRAY))
    d.add(String(x0 + 78, y0 - 10, '100% solid, one picture row per layer', fontName='DVS',
                 fontSize=5.8, textAnchor='middle', fillColor=GRAY))
    # light rays behind
    for k in range(3):
        d.add(Line(x0 - 18, y0 + 20 + k * 18, x0 - 4, y0 + 20 + k * 18,
                   strokeColor=colors.HexColor('#e8b84b'), strokeWidth=1.4))
    d.add(String(x0 - 12, y0 + 76, 'back-light', fontName='DVS', fontSize=5.6,
                 textAnchor='middle', fillColor=colors.HexColor('#b58a1f')))

    # ---- right: Levels effect (0 = photo vs 4 vs 12) -------------------------
    d.add(String(330, 182, 'LEVELS — HOW MANY BRIGHTNESS STEPS', fontName='DVSB', fontSize=6.9,
                 textAnchor='middle', fillColor=GRAY))
    def ramp(x, y, w, h, n):
        if n == 0:      # continuous gradient -> 24 stripes
            for k in range(24):
                v = 235 - k * 9
                d.add(Rect(x + k * w / 24.0, y, w / 24.0, h,
                           fillColor=colors.Color(v / 255.0, v / 255.0, v / 255.0),
                           strokeColor=None))
        else:
            for k in range(n):
                v = 235 - int(k * 200 / max(1, n - 1))
                d.add(Rect(x + k * w / float(n), y, w / float(n), h,
                           fillColor=colors.Color(v / 255.0, v / 255.0, v / 255.0),
                           strokeColor=colors.white, strokeWidth=0.8))
        d.add(Rect(x, y, w, h, fillColor=None, strokeColor=GRAY, strokeWidth=0.8))
    d.add(String(268, 158, '0 = photo (continuous)', fontName='DVS', fontSize=5.8,
                 textAnchor='start', fillColor=GRAY))
    ramp(268, 138, 130, 14, 0)
    d.add(String(268, 122, '4 = posterized (chunky retro)', fontName='DVS', fontSize=5.8,
                 textAnchor='start', fillColor=GRAY))
    ramp(268, 102, 130, 14, 4)
    d.add(String(268, 86, '12 = subtle terraces', fontName='DVS', fontSize=5.8,
                 textAnchor='start', fillColor=GRAY))
    ramp(268, 66, 130, 14, 12)
    d.add(String(330, 46, 'every step prints as ONE thickness — chunky at 2-4, photo-like at 8-12',
                 fontName='DVS', fontSize=5.6, textAnchor='middle', fillColor=GRAY))
    d.add(String(330, 26, 'auto-optimized before slicing: contrast stretch · smoothing · mirror '
                 '(white/natural PLA glows best)',
                 fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=GREEN))
    return d


def d_seal_anatomy():
    d = Drawing(480, 208)
    d.add(String(240, 199, 'Gasket — flat face vs groove with two sealing lips',
                 fontName='DVSB', fontSize=9.5, textAnchor='middle', fillColor=BLUE))

    # ---- left: top view ring ----
    d.add(String(120, 182, 'TOP VIEW (OD / ID)', fontName='DVSB', fontSize=6.9,
                 textAnchor='middle', fillColor=GRAY))
    cx, cy, ro, ri = 120, 118, 64, 34
    d.add(Circle(cx, cy, ro, fillColor=colors.HexColor('#eef3fa'), strokeColor=BLUE, strokeWidth=1.3))
    d.add(Circle(cx, cy, ri, fillColor=colors.white, strokeColor=BLUE, strokeWidth=1.1))
    d.add(Line(cx + ri * 0.72, cy + ri * 0.72, cx + ro * 0.72, cy + ro * 0.72,
               strokeColor=GREEN, strokeWidth=0.9))
    d.add(String(cx + 58, cy + 62, 'OD 12-200', fontName='DVS', fontSize=5.8,
                 textAnchor='middle', fillColor=GREEN))
    d.add(String(cx, cy - 4, 'ID 6-190', fontName='DVS', fontSize=5.8,
                 textAnchor='middle', fillColor=GRAY))
    d.add(String(cx, cy - 50, 'one CONTINUOUS spiral per band — no seam, no start blob',
                 fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=GRAY))

    # ---- right: the two faces in cross-section --------------------------------
    d.add(String(330, 182, 'THE TWO FACES (CROSS-SECTION)', fontName='DVSB', fontSize=6.9,
                 textAnchor='middle', fillColor=GRAY))
    # FLAT
    y = 130
    d.add(String(268, y + 32, 'FLAT — the all-round gasket', fontName='DVSB', fontSize=6.4,
                 textAnchor='start', fillColor=BLUE))
    d.add(Rect(268, y, 190, 12, fillColor=colors.HexColor('#dbe6f4'), strokeColor=BLUE, strokeWidth=1.1))
    d.add(Line(268, y + 16, 458, y + 16, strokeColor=GREEN, strokeWidth=1.2))
    d.add(String(363, y + 20, 'flange contact (full face)', fontName='DVS', fontSize=5.6,
                 textAnchor='middle', fillColor=GREEN))
    # NUT
    y = 70
    d.add(String(268, y + 32, 'NUT — groove + two sealing lips', fontName='DVSB', fontSize=6.4,
                 textAnchor='start', fillColor=GREEN))
    d.add(Rect(268, y, 190, 12, fillColor=colors.HexColor('#dbe6f4'), strokeColor=GREEN, strokeWidth=1.1))
    d.add(Rect(318, y, 90, 5, fillColor=colors.white, strokeColor=GREEN, strokeWidth=0.9))
    d.add(Line(268, y + 16, 458, y + 16, strokeColor=GREEN, strokeWidth=1.2))
    d.add(String(288, y + 20, 'lip', fontName='DVS', fontSize=5.4, textAnchor='middle', fillColor=GREEN))
    d.add(String(438, y + 20, 'lip', fontName='DVS', fontSize=5.4, textAnchor='middle', fillColor=GREEN))
    d.add(String(363, y - 12, 'groove: 2 raised lips = higher contact pressure on uneven flanges '
                 '(falls back to FLAT if the band is too narrow)',
                 fontName='DVS', fontSize=5.6, textAnchor='middle', fillColor=GRAY))
    d.add(String(330, 26, 'Height 0.4-6 mm (1.2 standard, 2+ for NUT) · TPU seals best, PETG works '
                 '— the file already prints at 15 mm/s',
                 fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=GREEN))
    return d


def d_frame_anatomy():
    d = Drawing(480, 208)
    d.add(String(240, 199, 'Frame — the zero-overhang profile & the two closures',
                 fontName='DVSB', fontSize=9.5, textAnchor='middle', fillColor=BLUE))

    # ---- left: cross-section through the wall (front UP) --------------------
    d.add(String(120, 182, 'CROSS-SECTION (PRINTS LYING, FRONT UP)',
                 fontName='DVSB', fontSize=6.9, textAnchor='middle', fillColor=GRAY))
    bx, by = 34, 46
    # front band (ironed top) + shelf + groove + back band, then the plate
    d.add(Rect(bx, by + 96, 152, 14, fillColor=colors.HexColor('#dbe6f4'),
               strokeColor=BLUE, strokeWidth=1.1))
    d.add(String(bx + 76, by + 101, 'FRONT — ironing pass (the visible face)',
                 fontName='DVSB', fontSize=5.4, textAnchor='middle', fillColor=BLUE))
    # shelf + view step (left half only wall, right half the bridge)
    d.add(Rect(bx, by + 84, 152, 12, fillColor=colors.HexColor('#dbe6f4'),
               strokeColor=BLUE, strokeWidth=1.0))
    d.add(String(bx + 76, by + 88, 'shelf — photo stop (bridge over the groove)',
                 fontName='DVS', fontSize=5.4, textAnchor='middle', fillColor=GRAY))
    # groove zone: photo + plate + nub
    d.add(Rect(bx + 8, by + 70, 60, 9, fillColor=colors.HexColor('#f7ddd2'),
               strokeColor=ORANGE, strokeWidth=0.8))
    d.add(String(bx + 38, by + 73, 'photo', fontName='DVS', fontSize=5.2,
                 textAnchor='middle', fillColor=ORANGE))
    d.add(Rect(bx + 8, by + 58, 60, 10, fillColor=colors.HexColor('#e8e2f4'),
               strokeColor=colors.HexColor('#7b5fb5'), strokeWidth=0.8))
    d.add(String(bx + 38, by + 61, 'backplate 0.8', fontName='DVS', fontSize=5.2,
                 textAnchor='middle', fillColor=colors.HexColor('#7b5fb5')))
    # nubs above the plate at the wall inner edge
    for nxx in (bx + 2, bx + 72):
        d.add(Rect(nxx, by + 58, 6, 12, fillColor=colors.HexColor('#cfe3cf'),
                   strokeColor=GREEN, strokeWidth=0.9))
    d.add(String(bx + 40, by + 47, 'nubs 1mm over the plate — bayonet (drop in, slide 2.5mm)',
                 fontName='DVS', fontSize=5.3, textAnchor='middle', fillColor=GREEN))
    # back band + wall
    d.add(Rect(bx, by + 40, 152, 18, fillColor=colors.HexColor('#eef3fa'),
               strokeColor=BLUE, strokeWidth=1.0))
    d.add(String(bx + 76, by + 47, 'back band (case: the deep box)',
                 fontName='DVS', fontSize=5.4, textAnchor='middle', fillColor=GRAY))
    d.add(String(bx + 76, by + 28, 'groove = photo + plate + play · depth < 15 = flat frame, '
                 '15+ = case', fontName='DVS', fontSize=5.5, textAnchor='middle', fillColor=GRAY))
    d.add(String(bx + 76, by + 16, 'border 4-30 · corner r 0-30 · RECT or OVAL · every part '
                 'an exclude object', fontName='DVS', fontSize=5.5, textAnchor='middle', fillColor=GRAY))

    # ---- right: front view + the two closures -------------------------------
    d.add(String(350, 182, 'THE TWO CLOSURES', fontName='DVSB', fontSize=6.9,
                 textAnchor='middle', fillColor=GRAY))
    # BACK: front view with view opening + plate with notches
    fx, fy = 288, 96
    d.add(String(fx + 40, fy + 72, 'BACK — bayonet plate', fontName='DVSB',
                 fontSize=6.4, fillColor=BLUE))
    d.add(Rect(fx, fy, 80, 60, fillColor=colors.HexColor('#eef3fa'),
               strokeColor=BLUE, strokeWidth=1.2, rx=6))
    d.add(Rect(fx + 12, fy + 9, 56, 42, fillColor=colors.white,
               strokeColor=BLUE, strokeWidth=0.9, rx=4))
    d.add(String(fx + 40, fy + 27, 'photo', fontName='DVS', fontSize=5.4,
                 textAnchor='middle', fillColor=GRAY))
    # the plate below with L/R notches + slide arrow
    d.add(Rect(fx + 6, fy - 26, 68, 20, fillColor=colors.HexColor('#e8e2f4'),
               strokeColor=colors.HexColor('#7b5fb5'), strokeWidth=1.0))
    d.add(Rect(fx + 6, fy - 16, 8, 10, fillColor=colors.white,
               strokeColor=colors.HexColor('#7b5fb5'), strokeWidth=0.8))
    d.add(Rect(fx + 66, fy - 16, 8, 10, fillColor=colors.white,
               strokeColor=colors.HexColor('#7b5fb5'), strokeWidth=0.8))
    d.add(String(fx + 40, fy - 20, 'notches', fontName='DVS', fontSize=5.0,
                 textAnchor='middle', fillColor=colors.HexColor('#7b5fb5')))
    d.add(Line(fx + 40, fy - 34, fx + 40, fy - 42, strokeColor=GREEN, strokeWidth=1.4))
    d.add(Polygon(points=[fx + 40, fy - 46, fx + 36, fy - 40, fx + 44, fy - 40],
                  fillColor=GREEN, stroke=0))
    d.add(String(fx + 52, fy - 43, 'slide 2.5mm = locked', fontName='DVS',
                 fontSize=5.4, fillColor=GREEN))
    # SIDE: slot in the left wall
    sx, sy = 400, 96
    d.add(String(sx + 36, sy + 72, 'SIDE — slide-in slot', fontName='DVSB',
                 fontSize=6.4, fillColor=GREEN))
    d.add(Rect(sx, sy, 72, 60, fillColor=colors.HexColor('#eef3fa'),
               strokeColor=GREEN, strokeWidth=1.2, rx=6))
    d.add(Rect(sx + 10, sy + 9, 52, 42, fillColor=colors.white,
               strokeColor=GREEN, strokeWidth=0.9, rx=4))
    # the slot: gap in the left wall + arrow
    d.add(Rect(sx - 2, sy + 24, 14, 12, fillColor=colors.white,
               strokeColor=GREEN, strokeWidth=1.0))
    d.add(Line(sx - 18, sy + 30, sx - 6, sy + 30, strokeColor=GREEN, strokeWidth=1.4))
    d.add(Polygon(points=[sx - 2, sy + 30, sx - 9, sy + 26, sx - 9, sy + 34],
                  fillColor=GREEN, stroke=0))
    d.add(String(sx + 36, sy - 10, 'photo + plate slide in', fontName='DVS',
                 fontSize=5.4, textAnchor='middle', fillColor=GREEN))
    d.add(String(350, 26, 'hang keyhole hidden in the plate (4 sides) · stand studs plug '
                 'into 2 plate holes · no room = 2 plates (frame | plate+stand), kit only if even the frame overflows',
                 fontName='DVS', fontSize=5.6, textAnchor='middle', fillColor=GREEN))
    return d


def d_angle_anatomy():
    d = Drawing(480, 196)
    d.add(String(240, 187, 'Angle plate & flat connector — auto hole layout, countersink, stiffening',
                 fontName='DVSB', fontSize=9.5, textAnchor='middle', fillColor=BLUE))

    # ---- left: 90 deg plate top view with the auto hole layout ---------------
    d.add(String(112, 176, 'ANGLE 90° — TOP VIEW (60/60, width 25)', fontName='DVSB', fontSize=6.9,
                 textAnchor='middle', fillColor=GRAY))
    s = 1.62
    ox, oy = 34, 44
    Lp = [(0, 0), (60, 0), (60, 25), (25, 25), (25, 60), (0, 60)]
    d.add(Polygon(points=[c for (a, b) in Lp for c in (ox + a * s, oy + b * s)],
                  fillColor=colors.HexColor('#eef3fa'), strokeColor=BLUE, strokeWidth=1.3))
    # corner zone (legs overlap there) + hole centerline zones
    d.add(Rect(ox, oy, 25 * s, 25 * s, fillColor=colors.HexColor('#f7ddd2'),
               strokeColor=None))
    d.add(String(ox + 12.5 * s, oy + 13.5 * s, 'corner', fontName='DVS', fontSize=5.2,
                 textAnchor='middle', fillColor=ORANGE))
    d.add(String(ox + 12.5 * s, oy + 9.5 * s, 'zone', fontName='DVS', fontSize=5.2,
                 textAnchor='middle', fillColor=ORANGE))
    # holes on leg A (y = 12.5): centers 30.5 / 54.5
    for cxx in (30.5, 54.5):
        d.add(Circle(ox + cxx * s, oy + 12.5 * s, 2 * s, fillColor=colors.white,
                     strokeColor=GREEN, strokeWidth=1.1))
        d.add(Circle(ox + cxx * s, oy + 12.5 * s, 0.7 * s, fillColor=GREEN, strokeColor=None))
    # holes on leg B (x = 12.5)
    for cyy in (30.5, 54.5):
        d.add(Circle(ox + 12.5 * s, oy + cyy * s, 2 * s, fillColor=colors.white,
                     strokeColor=GREEN, strokeWidth=1.1))
        d.add(Circle(ox + 12.5 * s, oy + cyy * s, 0.7 * s, fillColor=GREEN, strokeColor=None))
    # gusset rib over the corner
    tri = [(2.2, 2.2), (20, 2.2), (2.2, 20)]
    d.add(Polygon(points=[c for (a, b) in tri for c in (ox + a * s, oy + b * s)],
                  fillColor=colors.HexColor('#cfe0f2'), strokeColor=BLUE, strokeWidth=1.0,
                  strokeDashArray=[2.5, 2]))
    d.add(String(ox + 9 * s, oy + 6.5 * s, 'rib', fontName='DVS', fontSize=5.4,
                 textAnchor='middle', fillColor=BLUE))
    d.add(String(ox + 26 * s, oy - 12, 'holes auto-space on the centerline', fontName='DVS',
                 fontSize=6.0, textAnchor='middle', fillColor=GRAY))
    d.add(String(ox + 26 * s + 10, oy - 20, 'diameter clamps to width-6 · 2+2 placed', fontName='DVSB',
                 fontSize=6.0, textAnchor='middle', fillColor=GREEN))

    # ---- right top: countersink cross-section ---------------------------------
    x1 = 300
    d.add(String(390, 176, 'COUNTERSINK (CROSS-SECTION)', fontName='DVSB', fontSize=6.9,
                 textAnchor='middle', fillColor=GRAY))
    px, py, pw = x1, 118, 180
    d.add(Rect(px, py, pw, 26, fillColor=colors.HexColor('#eef3fa'), strokeColor=BLUE, strokeWidth=1.2))
    # stepped cone: 4 -> 6 -> 8
    d.add(Polygon(points=[px + 70, py, px + 84, py, px + 98, py + 26, px + 56, py + 26],
                  fillColor=colors.white, strokeColor=GREEN, strokeWidth=1.1))
    d.add(Line(px + 70, py, px + 56, py + 26, strokeColor=GREEN, strokeWidth=1.1))
    d.add(Line(px + 84, py, px + 98, py + 26, strokeColor=GREEN, strokeWidth=1.1))
    # screw (schematic, flat head sits flush)
    d.add(Polygon(points=[px + 66, py + 26, px + 88, py + 26, px + 88, py + 34, px + 66, py + 34],
                  fillColor=colors.HexColor('#9db4d6'), strokeColor=GRAY, strokeWidth=0.8))
    d.add(Rect(px + 73, py - 22, 8, 22, fillColor=colors.HexColor('#9db4d6'),
               strokeColor=GRAY, strokeWidth=0.8))
    d.add(String(px + 90, py + 30, 'flat-head screw sits FLUSH', fontName='DVS', fontSize=5.8,
                 anchor='start', textAnchor='start', fillColor=GRAY))
    d.add(String(px + 90, py + 8, 'top 2 layers: 1.5x then 2x hole', fontName='DVS', fontSize=5.8,
                 textAnchor='start', fillColor=GREEN))
    d.add(String(px + 90, py - 2, 'hole D stays through the plate', fontName='DVS', fontSize=5.8,
                 textAnchor='start', fillColor=GRAY))
    d.add(String(px + pw / 2, py - 34, 'OFF = straight hole for screw head + nut', fontName='DVS',
                 fontSize=5.8, textAnchor='middle', fillColor=GRAY))

    # ---- right bottom: angle variants + flat splice ---------------------------
    d.add(String(390, 76, 'ANGLE & FLAT — what the parameters do', fontName='DVSB', fontSize=6.9,
                 textAnchor='middle', fillColor=GRAY))
    def plate(x, y, deg, label, col, flat=False):
        s2 = 0.78
        if flat:
            pts = [(0, 0), (46, 0), (46, 10), (0, 10)]
        else:
            import math as _m
            th = _m.radians(deg)
            uA = (1, 0)
            uB = (_m.cos(th), _m.sin(th))
            la, lb, w = 34, 30, 11
            A2 = (la, 0)
            A3 = (la, w)
            B1 = (lb * uB[0], lb * uB[1])
            B2 = (B1[0] + w * uB[1], B1[1] - w * uB[0])
            B0 = (w * uB[1], -w * uB[0])
            # inner corner: intersect y=w line with B inner edge
            # B inner edge: from B0 dir uB: point = B0 + t*uB, y = -w*cos + t*sin = w -> t = w(1+cos)/sin
            if abs(uB[1]) > 1e-9:
                t = w * (1 + uB[0]) / uB[1]
                P_in = (B0[0] + t * uB[0], w)
            pts = [(0, 0), A2, A3, P_in, B2, B1]
        d.add(Polygon(points=[c for (a, b) in pts for c in (x + a * s2, y + b * s2)],
                      fillColor=colors.HexColor('#eef3fa'), strokeColor=col, strokeWidth=1.2))
        if flat:
            for hx in (9, 20, 33):
                d.add(Circle(x + hx * s2, y + 5 * s2, 2.2, fillColor=colors.white,
                             strokeColor=GREEN, strokeWidth=0.9))
                d.add(Circle(x + (46 - hx) * s2, y + 5 * s2, 2.2, fillColor=colors.white,
                             strokeColor=GREEN, strokeWidth=0.9))
        d.add(String(x + 18, y - 10, label, fontName='DVS', fontSize=5.6,
                     textAnchor='middle', fillColor=col))
    plate(300, 44, 45, 'Angle 45° — sharp', BLUE)
    plate(380, 44, 135, 'Angle 135°', ORANGE)
    plate(300, 22, 0, 'FLAT splice', GREEN, flat=True)
    d.add(String(386, 14, 'same hole pattern on BOTH halves', fontName='DVS', fontSize=5.4,
                 textAnchor='middle', fillColor=GREEN))
    d.add(String(240, 4, 'Leg A/B set independently (20-150) · Width 8-60 · Layers 4-12 · rib = gusset over '
                 'the corner (none / gusset / stepped)', fontName='DVS', fontSize=6.0,
                 textAnchor='middle', fillColor=GRAY))
    return d


def d_range_hole():
    """R86.2: floor hole (boss ring) + top hole (bridge-first) anatomy."""
    d = Drawing(480, 208)
    d.add(String(240, 198, 'Range holes — centered, with a thick boss ring', fontName='DVSB',
                 fontSize=9.5, textAnchor='middle', fillColor=BLUE))
    d.add(Rect(18, 46, 216, 138, fillColor=colors.white, strokeColor=GRAY, strokeWidth=1.2))
    d.add(String(126, 172, 'FLOOR hole — top view', fontName='DVSB', fontSize=8,
                 textAnchor='middle', fillColor=BLUE))
    d.add(Rect(44, 66, 164, 92, fillColor=LBLUE, strokeColor=BLUE, strokeWidth=1.2))
    import math as _m862
    _pts862 = []
    for _i862 in range(0, 180):
        _ang862 = _i862 * 360.0 / 56.0 * 3.14159265 / 180.0
        _r862 = 9.5 + (20.0 - 9.5) * _i862 / 179.0
        _pts862.append((126 + _r862 * _m862.cos(_ang862), 112 + _r862 * _m862.sin(_ang862)))
    d.add(PolyLine(points=_pts862, fillColor=None, strokeColor=ORANGE, strokeWidth=1.4))
    d.add(String(126, 109, 'hole', fontName='DVS', fontSize=6, textAnchor='middle', fillColor=GRAY))
    for yy in (78, 92, 106, 120, 134, 148):
        d.add(Line(46, yy, 104, yy, strokeColor=BLUE, strokeWidth=0.7))
        d.add(Line(148, yy, 206, yy, strokeColor=BLUE, strokeWidth=0.7))
    d.add(String(126, 58, 'boss = 1 continuous spiral (thick rim), hatch', fontName='DVS', fontSize=6.2,
                 textAnchor='middle', fillColor=GRAY))
    d.add(String(126, 51, 'stops at its outer edge - E14 15 / E27 28 mm', fontName='DVS', fontSize=6.2,
                 textAnchor='middle', fillColor=GRAY))
    d.add(Rect(246, 46, 216, 138, fillColor=colors.white, strokeColor=GRAY, strokeWidth=1.2))
    d.add(String(354, 172, 'TOP hole — bridge-first, side view', fontName='DVSB', fontSize=8,
                 textAnchor='middle', fillColor=BLUE))
    d.add(Rect(286, 60, 136, 9, fillColor=LBLUE, strokeColor=BLUE, strokeWidth=1))
    d.add(String(281, 63, 'body', fontName='DVS', fontSize=5.8, textAnchor='end', fillColor=GRAY))
    d.add(Rect(286, 70, 136, 8, fillColor=LBLUE, strokeColor=BLUE, strokeWidth=1))
    d.add(Line(326, 74, 386, 74, strokeColor=ORANGE, strokeWidth=2.4))
    d.add(String(430, 72, 'layer 1: anchor', fontName='DVS', fontSize=5.8, textAnchor='end', fillColor=ORANGE))
    d.add(String(430, 65, 'ring at the edge', fontName='DVS', fontSize=5.8, textAnchor='end', fillColor=ORANGE))
    for yy in (80, 90):
        d.add(Rect(286, yy, 32, 8, fillColor=LBLUE, strokeColor=BLUE, strokeWidth=1))
        d.add(Rect(390, yy, 32, 8, fillColor=LBLUE, strokeColor=BLUE, strokeWidth=1))
    d.add(String(430, 84, 'layers 2+: hole open,', fontName='DVS', fontSize=5.8, textAnchor='end', fillColor=GREEN))
    d.add(String(430, 77, 'boss rim on top', fontName='DVS', fontSize=5.8, textAnchor='end', fillColor=GREEN))
    d.add(String(354, 84, 'air', fontName='DVS', fontSize=5.6, textAnchor='middle', fillColor=GRAY))
    d.add(String(354, 94, 'air', fontName='DVS', fontSize=5.6, textAnchor='middle', fillColor=GRAY))
    d.add(String(354, 120, 'nothing sags: every clipped', fontName='DVS', fontSize=6.2, textAnchor='middle', fillColor=GRAY))
    d.add(String(354, 113, 'line welds onto the ring', fontName='DVS', fontSize=6.2, textAnchor='middle', fillColor=GRAY))
    d.add(String(354, 106, 'Top auto-raises to 3 layers', fontName='DVS', fontSize=6.2, textAnchor='middle', fillColor=GRAY))
    d.add(String(240, 34, 'Floor hole: cable feed, E14/E27 lampholder (thread 15 / 28 mm; body: measure + 0.3) · '
                 'diameter clamps to the REAL outline + 2mm', fontName='DVS', fontSize=6.0,
                 textAnchor='middle', fillColor=GRAY))
    d.add(String(240, 4, 'Console: SET_LAYER_RANGE FLOOR=3 FLOOR_HOLE=15 TOP=3 TOP_HOLE=28 · presets E14 = 15.0, E27 = 28.0',
                 fontName='DVS', fontSize=6.0, textAnchor='middle', fillColor=GRAY))
    return d


def d_wiring():
    """R86.2: power + CAN architecture with the BTT Relay / U2C / EBB42."""
    d = Drawing(480, 252)
    d.add(String(240, 242, 'One harness to the toolhead - printer off, Pi stays on', fontName='DVSB',
                 fontSize=9.5, textAnchor='middle', fillColor=BLUE))
    d.add(Rect(14, 196, 60, 30, fillColor=colors.white, strokeColor=RED, strokeWidth=1.4))
    d.add(String(44, 210, '230V', fontName='DVSB', fontSize=8, textAnchor='middle', fillColor=RED))
    d.add(String(44, 202, 'mains', fontName='DVS', fontSize=6.5, textAnchor='middle', fillColor=RED))
    d.add(Rect(96, 196, 74, 30, fillColor=colors.white, strokeColor=RED, strokeWidth=1.4))
    d.add(String(133, 210, 'RELAY V1.2', fontName='DVSB', fontSize=7.5, textAnchor='middle', fillColor=RED))
    d.add(String(133, 202, '10A/250VAC - L only', fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=RED))
    d.add(Rect(192, 196, 66, 30, fillColor=colors.white, strokeColor=BLACK, strokeWidth=1.4))
    d.add(String(225, 210, 'PSU 24V', fontName='DVSB', fontSize=8, textAnchor='middle', fillColor=BLACK))
    d.add(String(225, 202, 'N + PE direct!', fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=GRAY))
    d.add(Line(74, 211, 96, 211, strokeColor=RED, strokeWidth=1.6))
    d.add(String(85, 216, 'L', fontName='DVSB', fontSize=6.5, textAnchor='middle', fillColor=RED))
    d.add(Line(170, 211, 192, 211, strokeColor=RED, strokeWidth=1.6))
    d.add(String(225, 188, 'never switch PE', fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=RED))
    d.add(Rect(120, 140, 96, 34, fillColor=colors.white, strokeColor=BLUE, strokeWidth=1.4))
    d.add(String(168, 160, 'SKR Mini E3 V3', fontName='DVSB', fontSize=7.5, textAnchor='middle', fillColor=BLUE))
    d.add(String(168, 152, 'bed, X/Y/Z, LCD, frame LEDs', fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=GRAY))
    d.add(String(168, 145, 'UART to Pi (10k series!)', fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=GRAY))
    d.add(Rect(300, 140, 96, 34, fillColor=colors.white, strokeColor=BLUE, strokeWidth=1.4))
    d.add(String(348, 160, 'EBB42 CAN V1.2.1', fontName='DVSB', fontSize=7.5, textAnchor='middle', fillColor=BLUE))
    d.add(String(348, 152, 'at the extruder stepper', fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=GRAY))
    d.add(String(348, 145, 'heater, fans, probe, LEDs', fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=GRAY))
    d.add(Line(216, 196, 168, 174, strokeColor=BLACK, strokeWidth=1.2))
    d.add(String(178, 184, '24V (switched)', fontName='DVS', fontSize=5.8, fillColor=GRAY))
    d.add(Line(240, 196, 340, 174, strokeColor=BLACK, strokeWidth=1.2))
    d.add(String(300, 186, '24V + GND, 20AWG', fontName='DVS', fontSize=5.8, fillColor=GRAY))
    d.add(Rect(60, 78, 118, 34, fillColor=colors.white, strokeColor=GREEN, strokeWidth=1.4))
    d.add(String(119, 98, 'Pi Zero 2', fontName='DVSB', fontSize=8, textAnchor='middle', fillColor=GREEN))
    d.add(String(119, 90, 'OWN 5V USB PSU (>=2.5A)', fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=GREEN))
    d.add(String(119, 83, 'runs Mainsail + klipper', fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=GRAY))
    d.add(Rect(240, 78, 86, 34, fillColor=colors.white, strokeColor=GREEN, strokeWidth=1.4))
    d.add(String(283, 98, 'U2C V2.1', fontName='DVSB', fontSize=8, textAnchor='middle', fillColor=GREEN))
    d.add(String(283, 90, 'USB to CAN', fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=GRAY))
    d.add(String(283, 83, '120R jumper ON', fontName='DVS', fontSize=5.8, textAnchor='middle', fillColor=ORANGE))
    d.add(Line(178, 95, 240, 95, strokeColor=GREEN, strokeWidth=1.6))
    d.add(String(209, 100, 'USB', fontName='DVS', fontSize=6, textAnchor='middle', fillColor=GREEN))
    d.add(Line(326, 112, 348, 140, strokeColor=ORANGE, strokeWidth=1.6))
    d.add(String(344, 122, 'CAN H/L twisted, 120R ON', fontName='DVS', fontSize=5.8, fillColor=ORANGE))
    d.add(String(344, 116, '(exactly 2 terminators)', fontName='DVS', fontSize=5.8, fillColor=ORANGE))
    d.add(Line(140, 140, 118, 196, strokeColor=RED, strokeWidth=1.2, strokeDashArray=[4, 3]))
    d.add(String(96, 168, 'control pin', fontName='DVS', fontSize=5.8, fillColor=RED))
    d.add(String(96, 162, 'HIGH = ON', fontName='DVS', fontSize=5.8, fillColor=RED))
    d.add(String(96, 156, 'klipper dead', fontName='DVS', fontSize=5.8, fillColor=RED))
    d.add(String(96, 150, '= printer OFF', fontName='DVS', fontSize=5.8, fillColor=RED))
    d.add(String(240, 60, 'button on the relay = manual ON - then FIRMWARE_RESTART (the MCUs were completely off)',
                 fontName='DVS', fontSize=6.2, textAnchor='middle', fillColor=GRAY))
    d.add(String(240, 50, 'CAN-H to CAN-L with everything off: ~60 ohm = two 120R - the termination check',
                 fontName='DVS', fontSize=6.2, textAnchor='middle', fillColor=GRAY))
    d.add(String(240, 4, 'Relay switches the 230V PHASE only (L). Printer ~1.5A at 230V - never use it on the 24V side (bed ~10A DC arc!)',
                 fontName='DVS', fontSize=6.0, textAnchor='middle', fillColor=RED))
    return d

# ---- cover ----
E+= [Spacer(1,10*mm),Paragraph('R2-D2 Macro System',S['title']),Spacer(1,2*mm),
     Paragraph('The Complete User Handbook — illustrated edition',S['sub']),Spacer(1,3*mm),
     Paragraph('Version R2-2026-10-13.102 · Ender-3 + BTT SKR mini E3 + Pi Zero 2 W (Mainsail)',S['sub']),
     Spacer(1,6*mm),CENT(d_robot()),Spacer(1,6*mm),
     Paragraph('The USER HANDBOOK: from file to print in one read — every file type (by layer / by object / vase /<br/>'
               'legacy / movement data), the start dialog, pre-print settings, live tuning, pauses, object skip ·<br/>'
               'the generators: RANGE (partial prints), LABELS (five fonts, auto-grow), PLOTTER (images, text) ·<br/>'
               'the calibration ladder in the right order · maintenance &amp; care · full reference: menus,<br/>'
               '140+ macros, overrides, sounds, LEDs, troubleshooting, cheat sheet · appendices: installation,<br/>'
               'power &amp; electrics, first start, version history',
               S['sub']),Spacer(1,22*mm),
     Paragraph('Companions: INSTALL.md · ISHAPER.md · slicer/ORCA.md + slicer/CURA.md · MANUAL.md (plain text)',S['sub']),
     PageBreak()]

# ---- TOC ----
E+=[Mark('Contents'),H1('Contents'),HRFlowable(width='100%', thickness=1.1, color=BLUE, spaceBefore=1, spaceAfter=14),
TBL(['Ch.','Topic'],[
 ['1','Safety first — fire &amp; hardware'],['2','The system in five minutes'],
 ['3','From file to print — the daily workflow'],['4','Scenario library — every file type walked through'],
 ['5','The generators: Range, Labels, Plotter, Cable ties, Angles, Lithophanes, Gaskets &amp; Frames'],['6','During the print: tuning, pauses, objects'],
 ['7','Filament: load / unload / change / runout / cold pull'],['8','Temperature system L1/L2'],
 ['9','Speed, acceleration &amp; machine limits'],['10','Calibration — the ladder to good prints'],
 ['11','Bed mesh &amp; KAMP'],['12','Purge / prime line'],['13','Maintenance &amp; care'],
 ['14','LCD menu reference'],['15','Overrides reference'],['16','Sound reference'],['17','LED reference'],
 ['18','Console messages'],['19','System: Klipper &amp; Pi'],['20','Variables &amp; editing'],
 ['21','What happens when a macro executes'],['22','Troubleshooting'],['23','Limits &amp; known behavior'],
 ['24','Cheat sheet: LCD paths &amp; Mainsail commands'],['25','Complete macro index — all macros with parameters'],
 ['A–D','Appendices: Installation · Power &amp; electrics · First start · Version history'],
],[14*mm,150*mm],pad=2),
P('<b>21 diagrams:</b> file flow (3) · state machine + override stack (2) · start choreography (4) · range '
  'variants, font specimens, label anatomy (5) · L1/L2 curves, sequential detection, park anatomy (6) · runout '
  'flow (7) · calibration ladder (10) · mesh dispatch (11) · prime line (12) · menu tree (14) · LED &amp; volume '
  'vocabulary (17) · power tree, wiring, UART, Neopixel (B).')]

def chapter(num, title, *flow):
    E.append(PageBreak()); E.append(Mark(f'{num} · {title}')); E.append(H1(f'{num} · {title}'))
    E.append(HRFlowable(width='100%', thickness=1.1, color=BLUE, spaceBefore=1, spaceAfter=14))
    flat=[]
    for f in flow: flat.extend(f) if isinstance(f, list) else flat.append(f)
    i=0
    def _iscap(x): return isinstance(x, Paragraph) and getattr(x.style, 'name', '') == 'cap'
    def _ish2(x): return isinstance(x, Paragraph) and getattr(x.style, 'name', '') == 'h2'
    while i < len(flat):
        f=flat[i]
        if _ish2(f) and i+2 < len(flat) and isinstance(flat[i+1], Drawing) and _iscap(flat[i+2]):
            flat[i+1].hAlign='CENTER'; E.append(KeepTogether([f, flat[i+1], flat[i+2]])); i += 3; continue
        if isinstance(f, Drawing) and i+1 < len(flat) and _iscap(flat[i+1]):
            f.hAlign='CENTER'; E.append(KeepTogether([f, flat[i+1]])); i += 2; continue
        E.append(f); i += 1

chapter('1','Safety first — fire &amp; hardware',
  P('A 3D printer combines hot heaters, high currents and unattended hours. This system adds software guardrails — '
    'software is never a substitute for hardware safety.'),
  H2('Hardware safety you should have'),
  *B('<b>Smoke detector</b> in the printer room — printers are fire load, especially overnight.',
     'Fused mains side, PSU with protection circuitry, cables in good condition.',
     'Cable strain relief at the heatbed (the classic Ender-3 chafe point).',
     'Clean bed, free airflow around the electronics, nothing flammable stacked on top.',
     'Never print behind a locked door; do not leave the printer alone for days.'),
  H2('What the macro system does for you'),
  *B('Heaters off at print end (heaters_off_at_end) + hotend fan cool-down (cooldown_fan_time, default 30 s).',
     'Pauses KEEP temperatures on purpose (you want to continue) — CANCEL_PRINT turns heaters off.',
     'SYS_SHUTDOWN: heaters/fans/LEDs off BEFORE the Pi goes down (two presses).',
     'After a Klipper error: alarm sound + red/white LED strobe, system goes idle.',
     'Runout pauses at the next layer boundary — detected BEFORE the print starves.',
     'EMERGENCY_STOP (System menu or console) halts everything immediately.'),
  H2('Smoke / heat action plan'),
  CODE('EMERGENCY_STOP -> switch off at the MAINS -> if smoking:\n'
       'extinguish with CO2/foam only - NEVER water on live electronics'),
  P('<b>Not</b> protected by macros: a stuck MOSFET, a blocked fan, a loose heater cartridge. Inspect the printer regularly.'))


chapter('2','The system in five minutes',
  CENT(d_state_machine()),CAP("The mode state machine — the watcher re-syncs it from printer.print_stats every second"),
  H2('One idea: every file gets intercepted'),
  P("A small Python service watches the gcodes folder and enriches every arriving file; the macro layer catches "
    "every print start and holds it until you have decided how it should run. Between the two, the printer always "
    "knows what a file contains — material, layers, features, speeds — and can take over any parameter without "
    "re-slicing. This is also why the SAME file prints in a different material: load another preset, start AS LEGACY."),
  TBL(['Tool','What it does','When it runs'],[
   ['r2_postproc.py','THE interceptor: tags every new G-code (LAYER_MARK, APPLY_TYPE, _FILE_INFO with measured '
    'per-feature speeds/accels), contains the generators (Range, Labels, towers, bridging, resonance) and the '
    'plot converters (PNG/JPEG/SVG/PDF/TXT)','continuously (service, 1 s)'],
   ['make_label_fonts.py','builds the label fonts baked into r2_postproc.py (SMOOTH, MONO, COND, NARROW, CAPS)','build time only'],
   ['macro_render_test.py / config_validator.py / r81_golden_check.py','the test battery the package is built against','after edits'],
  ],[34*mm,100*mm,26*mm]),
  P("Files are never destroyed: tagging rewrites a file once when it arrives (already-tagged files skip); "
    "generators and converters always write NEW files."),
  H2('The watcher (macro side, 1-second heartbeat)'),
  *B('catches prints started WITHOUT PRINT_START (legacy files) and activates overrides + live tuning',
     'counts layers via Z when the file has no LAYER_MARK markers (and in AS LEGACY mode)',
     'switches L1 to L2 temps/fan/speed at the tracked layer 2 — the mirror of LAYER_MARK',
     'detects sequential object changes (Z falling edge)',
     'temperature tower band control and self-healing: stuck pause states resolved, expired cancels disarmed (60 s)',
     'keeps print_stats and the internal mode in sync — the LCD never lies about the state'),
  H2('Overrides instead of re-slicing'),
  CODE('Rule:     override ON + value > 0  =  applied. Otherwise the file rules.\n'
       'Priority: LCD override (ON)  >  file value  >  material preset.'),
  CENT(d_stack()),CAP("The override stack — which layer wins when several want to say something"),
  P("M104/M109/M140/M190/M106/M204/M220/M221/SET_PRESSURE_ADVANCE/SET_RETRACTION from the file are intercepted "
    "and redirected — strictly by layer (ch. 8). The interceptors remember what the FILE asked for — temps, PA, "
    "retraction, fan value, flow factor (shown as File H:215/210C hints in the menus)."),
  H2('Render before execute'),
  P("Klipper renders a whole macro template BEFORE running it — a macro cannot see values it just set. "
    "Verification phases therefore run as delayed_gcode seconds later (ch. 21). This one fact explains most "
    "quirks you will meet:"),
  TBL(['What you see','What it really is','What to do'],[
   ['a macro seems to wait for a state it just set','render-before-execute — the delayed phase runs seconds later','nothing — by design'],
   ['M104 logs OVERWRITE, temp stays','AS SLICED run — the file is king','switch mode or set the overwrite ON'],
   ['State re-synced after an object change','watcher self-healing after a double resume','cosmetic — safe to ignore'],
   ['LCD shows a File: value next to your override','the interceptor captured the file value for comparison','use it to compare on the spot'],
  ],[52*mm,64*mm,66*mm]))


chapter('3','From file to print — the daily workflow',
  CENT(d_file_flow()),CAP("The complete path: upload, interceptor, start dialog, start choreography"),
  H2('3.1 Getting a file onto the printer'),
  P("Drag the file into the Mainsail gcode panel (or USB / scp / download) — within a second the postproc service "
    "has tagged it: ; R2-POSTPROC v4 at the top, a _FILE_INFO parameter block, LAYER_MARK before every layer and "
    "APPLY_TYPE after every ;TYPE: comment. The console logs one line per file. Files already carrying the tag are skipped."),
  P("The moment you SELECT a file, its _FILE_INFO is replayed: Pre-Print > File (G-code) immediately shows THAT "
    "file — type (MARKED / LEGACY / PLOT), material, layers, line widths, flow ratio, by-object, the features it "
    "contains (TYPES=) and the MEASURED original speed/accel of each feature (FS_*/FA_*)."),
  H2('3.2 File types and how the system tells them apart'),
  TBL(['File type','Detected by','What the system does'],[
   ['print by layer (normal)','layer comments or Z-scan, BY_OBJECT=0','the normal case: L1 rules on layer 1, L2 at layer 2, per-feature overrides'],
   ['print by object (sequential)','several objects + Z falling edges','every object restarts with L1 temps + L1 speed; layer counter re-anchors per object'],
   ['multi-object with object data','EXCLUDE_OBJECT_DEFINE lines','adaptive KAMP mesh, per-object skip, smart parking'],
   ['vase mode (continuous Z)','Z-scan: slow continuous rise','accumulated layer marks — vase prints still get layer events'],
   ['legacy file (no markers)','no tag, no PRINT_START','LEGACY start dialog; AS LEGACY = full takeover with Z layer counting'],
   ['old mod file','calls its own START_PRINT','real legacy start: home, heat, purge — then your decision'],
   ['pure movement data','nothing heats, nothing calls','net probe: home + heat + purge, then 1:1'],
   ['plot file (pen)','; R2-PLOT header','plotter flow, live tuning works while plotting'],
   ['generated file (Range/Labels/towers)','tag + PRINT_START header','normal start flow like any sliced file'],
  ],[40*mm,52*mm,66*mm]),
  H2('3.3 Pre-Print — the settings before you start'),
  TBL(['Entry','Contents'],[
   ['File (G-code)','full slicer summary + slicer/firmware of the file + 16 feature activator rows (file value + ON switch, n/a guard)'],
   ['Material','LOAD NOW + all values + Save as preset — active-material edits apply live'],
   ['Temperatures / Motion','L1/L2 bed+hotend, fan L2, PA + smooth, retraction, accel, velocity, MCR, corner'],
   ['Features','16 submenus: file original + ON + speed percent + accel per feature'],
   ['Flow / 1st layer','global flow 1–300 percent, first-layer speed (default 75 percent)'],
   ['Bed Mesh','ON/AUTO/OFF, adaptive, travel cap, profiles'],
   ['Profiles','per-file profiles (pre/post), the 8 default profiles, material presets - see 3.3a (.84)'],
   ['Range/Stop','planned end at layer N + the range generator: From/To, Floor/Top shapes+fills, Fl.hole + Top hole 0-80 mm centered, Brim, Create (ch. 5.1)'],
   ['Filament','load / unload / change before the print'],
   ['RetFix','ON/OFF - auto-treats every NEW upload (retract pairs -> G10/G11). For the SELECTED file use File > RetFix file / Vol->mm fix: repaired ON DISK, no re-upload (beeps at start + done, markers survive); Marlin-volumetric files get a loud warning'],
   ['Ret verdict (.86)','Pre-Print > File > Ret: line - FIX! (Bowden-era retracts override yours, SHOULD fix) / can X.Xmm (optional) / fixed (already rewritten) / fw (slicer G10/G11) - the RetFix offer appears only for fix/can; STALE (v4) files show -- until retagged'],
   ['RETAG (.86)','System > File check (2x): upgrades STALE v4 files in place - same markers, new info line (MAXRATE/SEAM/CFG keys/retract verdict), .r2bak backup, 20 per run'],
   ['Click pacing','multi-value actions (material, presets, range, fixes) insert ~100ms pauses between disk writes - Pi Zero burst protection; no-ops while printing'],
  ],[34*mm,126*mm]),
  P("<b>The golden rule:</b> overrides only apply when they are ON. A stored value without ON never touches the "
    "print; the file rules until you switch something on."),
  H2('3.3a Per-file profiles — the memory of every print (.84)'),
  P("Every legacy-printed file can carry its OWN profile: all pre-print settings (temps, PA, retraction, "
    "motion, flow, fan, ironing, first-layer speed, material, all 16 feature switches + values) plus everything "
    "tuned LIVE during the print. Two slots: <b>pre</b> (saved MANUALLY from Pre-Print > Profiles > This file) "
    "and <b>post</b> (saved AUTOMATICALLY at PRINT_END of a successful print - the state it finished with; "
    "cancelled prints write nothing). Auto-load on file selection picks the NEWER slot; the auto-save NEVER "
    "overwrites a manual 'pre'. The key is the path under the gcodes root, so Petg/vase.gcode and vase.gcode "
    "are two files - exactly like the selection list. Applying a profile writes the values AND their ON "
    "switches (the old load-default-preset bug is fixed with the same code path)."),
  TBL(['Sub-menu','Contents'],[
   ['Material','LOAD / SAVE / RESET for PLA, PETG, TPU + LOAD/SAVE ABS/ASA - SAVE writes the material values WITHOUT loading it first'],
   ['Defaults','the 8 standalone default profiles: Save, Info, Load 1-8, Delete 1-8'],
   ['This file','Save as pre / Load pre / Load post / Delete pre / Delete post (only existing slots appear) + Auto-load + Auto-save post toggles'],
  ],[34*mm,126*mm]),
  H2('3.4 The start dialog — AS LEGACY or AS SLICED'),
  TBL(['Mode','What rules'],[
   ['AS SLICED','the FILE, truly 1:1 — no overrides, no first-layer brake beyond the L1/L2 rules (which stay on). Live commands still apply'],
   ['AS LEGACY','takeover with YOUR parameters: overrides ON, mesh + purge, Z layer tracking, sequential handling'],
   ['CANCEL','aborts cleanly — nothing was heated'],
  ],[30*mm,130*mm]),
  P("How to decide: sliced with this system profile and values as wanted — either mode works. Foreign file, old "
    "profile, or your material preset / feature speeds / first-layer brake should apply — <b>AS LEGACY</b> "
    "(recommended default). Range and label files announce it in their header comment. start_confirm OFF = "
    "immediate LEGACY takeover."),
  H2('3.5 While it prints / after the print'),
  P("Everything is adjustable while the job runs — global and per-feature speed, flow, PA, accel, temps, "
    "babystepping — plus pauses, object skips and the planned end (ch. 6). After PRINT_END: lift, park away from "
    "the part, stats, fanfare, cooldown, heaters off; _PRINT_CLEANUP resets all per-print state — your pre-print "
    "settings, material and mesh deliberately KEPT."),
  H2('3.6 Foreign G-code — other slicers, other firmware, other hardware'),
  P("Files not sliced by you, not sliced for Klipper, or sliced for a DIFFERENT extruder. Twelve slicer families are "
    "recognized by their header (OrcaSlicer, PrusaSlicer, SuperSlicer, Bambu Studio, Cura, Elegoo, Kiri:Moto, "
    "AstroPrint, SliceBeam, ideaMaker, Simplify3D, FlashPrint) and their dialects normalized: layer comments "
    "(LAYER_CHANGE / LAYER:n / CHANGE_LAYER) all become LAYER_MARKs, feature names (Outer wall vs WALL-OUTER vs "
    "Support/Base) map to the same 16 internal codes (census table below), config headers feed the preview. Two Marlin habits break "
    "on Klipper — both detected, flagged and fixed IN PLACE:"),
  TBL(['Case','Symptom','The fix (one click)'],[
   ['Marlin-volumetric file (FLAVOR:Marlin (Volumetric), Cura)','E counts mm³ instead of mm — the print starves',
     'Pre-Print &gt; File &gt; Vol-&gt;mm fix: every E divided by 2.405 mm², markers neutralized, idempotent'],
   ['Old Bowden-era file (5–6 mm retracts baked in)','overrides your tuned ~0.8 mm direct-drive retraction',
     'Pre-Print &gt; File &gt; RetFix file (or RetFix ON for future uploads): pairs become G10/G11 — your retraction applies, live-tunable. '
     'The offer only shows when it applies: firmware-retraction files (G10/G11) and already-fixed files never show it; the file info names the case (field log .72)'],
   ['Marlin file without those quirks','nothing breaks','LEGACY start flow takes over: dialog, mesh, purge, L1/L2 — just press PRINT'],
   ['File calling its own START_PRINT','double start risk','real legacy start: homing, heat, purge — then your decision rules'],
   ['Pure movement data (no heaters, no macros)','would run cold','net probe: home + heat + purge first, then 1:1'],
   ],[44*mm,52*mm,64*mm]),
  P("The file info line 'sliced by &lt;slicer&gt; for &lt;firmware&gt;' tells you upfront what you are holding. The "
    "reverse case (direct-drive file on a Bowden machine) needs no file fix — just your retraction values."),
  H2('Slicing for this system — the settings that unlock everything'),
  P("Why does G-code for other firmware or machines print here at all? Because the system does not "
    "trust the file — it READS it: 12 slicer families' dialects are normalized (layer comments to "
    "LAYER_MARK, feature names to the 16 codes, header to file info), the interceptors translate "
    "Marlin habits on the fly, PRINT_START/PRINT_END wrap every file in the same choreography. What "
    "cannot be translated is DETECTED and offered a fix (volumetric E, Bowden retracts)."),
  TBL(['Slice it like this','What it unlocks'],[
   [';TYPE: feature comments (slicer default)','the 16 feature overrides + Live Tuning showing the feature printing NOW'],
   ['layer comments (LAYER_CHANGE / LAYER: / CHANGE_LAYER)','layer counting, L1/L2 temps, fan from layer 2, Pause@, Stop@, the Range generator'],
   ['Klipper flavor (absolute or relative E — both fine)','clean values everywhere; Marlin-volumetric works after the Vol-&gt;mm fix'],
   ['start gcode calls PRINT_START with the file values','full start choreography: dialog, mesh, purge, first-layer rules'],
   ['end gcode calls PRINT_END','park, stats, fanfare, cooldown — never a parked hot nozzle'],
   ['\"label objects\" enabled','KAMP adaptive mesh, object skip, smart park'],
   ['no M220/M221 spam from custom scripts','the clean-global system stays honest'],
  ],[64*mm,96*mm]),
  H2('3.7 The feature census — all 16 features in every slicer family'),
  P("Every modern slicer writes ;TYPE: comments into the G-code. The post-processor maps each spelling to one "
    "internal code, MEASURES speeds/accels per feature and injects an APPLY_TYPE marker after every ;TYPE: — that "
    "is what makes features live-tunable. Values without an own marker (e.g. small perimeters) come from the "
    "config header into the file info instead (R95, field log .74):"),
  TBL(['Feature (menu)','OrcaSlicer / Bambu','PrusaSlicer / SuperSlicer','Cura'],[
   ['OW Outer wall','Outer wall','External perimeter','WALL-OUTER'],
   ['IW Inner wall','Inner wall','Perimeter (Thin wall too)','WALL-INNER'],
   ['OH Overhang wall','Overhang perimeter','Overhang perimeter','— (in WALL-OUTER)'],
   ['SP Sparse infill','Sparse infill','Internal infill','FILL'],
   ['SO Solid infill','Internal solid infill','Solid infill','— (in FILL/SKIN)'],
   ['TP Top surface','Top surface / Top solid infill','Top solid infill','SKIN'],
   ['BT Bottom surface','Bottom surface / Bottom solid infill','Bottom solid infill','SKIN (bottom)'],
   ['BR Bridge','Bridge','Bridge infill','BRIDGE'],
   ['IB Internal bridge','Internal bridge','Internal bridge infill','—'],
   ['GP Gap fill','Gap fill / Gap infill','Gap fill','—'],
   ['SU Support','Support (+ interface/transition)','Support material (+interface)','SUPPORT (+SUPPORT-INTERFACE)'],
   ['IR Ironing','Ironing','Ironing','—'],
   ['SK Skirt','Skirt / Ooze shield','Skirt','SKIRT'],
   ['BM Brim','Brim','Brim','BRIM'],
   ['PT Prime tower','Prime tower','Wipe tower','PRIME-TOWER'],
   ['CU Custom code','custom (custom G-code)','custom','—'],
   ],[30*mm,42*mm,48*mm,40*mm]),
  P("Small perimeters are a pure SPEED setting (Orca default 50% of the wall speed) — the slicer decides per loop "
    "which wall counts as small, there is no own ;TYPE: marker: small_perimeter_speed/acceleration is read from "
    "the config header and shown in the file info (Speed/Accel small) so you can see why short loops run slower. "
    "Types without an own menu entry map honestly: Raft to BT, Support interface/transition to SU, Ooze shield to "
    "SK, plain Infill to SP. The 'mystery feature' from the field log (low accel values, no menu owned it) were "
    "custom G-code sections with their own M204 — they are now the editable feature CU Custom code."),
  CODE('PRINT_START MATERIAL=[filament_type] BED=[first_layer_bed_temperature]\n'
       'HOTEND_FIRST=[first_layer_temperature] HOTEND_AFTER=[temperature]\n'
       'LAYER_HEIGHT=[layer_height] TOTAL_LAYERS=[num_layers]\n'
       'OUTER_WALL_SPEED=[outer_wall_speed] SUPPORT_SPEED=[support_speed]\n'
       'IRONING_SPEED=[ironing_speed]   ... PRINT_END at the end\n'
       '(Orca/Prusa/SuperSlicer/Bambu/Elegoo placeholders — Cura: {material_type} etc.;\n'
       'step by step: slicer/ORCA.md + slicer/CURA.md)'),
  TBL(['Slicer','Watch out for'],[
   ['OrcaSlicer (reference), PrusaSlicer, SuperSlicer','works out of the box — enable label objects'],
   ['Bambu Studio','export without Bambu header macros; keep type comments on'],
   ['Elegoo Slicer, SliceBeam','Orca relatives — behave like Orca'],
   ['Cura','CURA.md start gcode; Marlin (Volumetric) files: Vol-&gt;mm fix once'],
   ['Kiri:Moto, AstroPrint','layer comments by default; PRINT_START/PRINT_END into the boxes'],
   ['ideaMaker, Simplify3D, FlashPrint','set flavor to Klipper; old profiles bake in long retracts — RetFix file'],
  ],[64*mm,96*mm]),
  P("<b>Limits no translation can fix:</b> the machine is still this machine (bigger bed / Delta / "
    "15 mm/s² files run clamped to YOUR limits); M-codes the firmware does not know stop the print "
    "(move exotic Marlin logic to macros); arcs G2/G3 are fine; AS SLICED = 1:1 with first-layer rules "
    "per your switch."))


chapter('4','Scenario library — every file type walked through',
  CENT(d_start_stages()),CAP("Start choreography — sound + LED at every stage, identical for every start mode"),
  H2('The core scenarios'),
  *B('<b>A — sliced, print by layer (normal case):</b> upload, start dialog, AS LEGACY. Purge + layer 1 with L1 '
     'temps + first-layer brake; layer 2: L2 temps, file fan, 100 percent speed',
     '<b>B — sliced, print by object:</b> at every object change L1 temps + L1 speed (pause only if a heater must '
     'move); the next object switches back to L2 at its layer 2',
     '<b>C — legacy file, by layer:</b> LEGACY dialog, AS LEGACY = takeover (mesh, purge, gapless continue, Z '
     'layer counting); AS SLICED = the file rules 1:1',
     '<b>D — legacy file, by object:</b> C plus per-object restarts (choose AS LEGACY — AS SLICED never injects '
     'object handling)',
     '<b>E — sliced file, started AS LEGACY:</b> takeover on a good file — overrides ON, markers still fire',
     '<b>F — same file, different material:</b> Pre-Print > Material LOAD NOW the PETG preset, start AS LEGACY. '
     'Temps/fan/PA/retraction/flow from the preset, geometry stays the file',
     '<b>G — printing a RANGE:</b> Pre-Print > Range/Stop: From/To/Floor/Brim, Create — the excerpt auto-selects, '
     'start AS LEGACY (ch. 5.1)',
     '<b>H — printing LABELS:</b> Tools > Labels > Text, Settings, Job > Add, Create — start like any file; M600 pause '
     'for color 2 (ch. 5.2)',
     '<b>I — plotting an image:</b> upload name.png.gcode (converted in place), start (AS SLICED = pure pen), M0 '
     'pauses at pen changes (ch. 5.3)',
     '<b>J — test the critical middle:</b> range with Floor 0 / Top 2 — the section prints on the bed with a '
     'solid cap: the fastest overhang/clearance test'),
  H2('Filament change mid-print (M600)'),
  P("Live Tuning > Pause &amp; Control > Change (M600): parks hot, unloads, waits with LED + sound. Load until "
    "the sensor clicks, RESUME purges (PURGE_MORE for 15 mm more), the print continues."),
  H2('Typical console session (Mainsail)'),
  CODE('SET_MATERIAL MATERIAL=PETG                      # load preset\n'
       'SET_OVERRIDE_VALUE NAME=hotend_first VALUE=235  # + ON automatically\n'
       'SHOW_STATUS                                    # mode + file type + parameters\n'
       '# during the print (every mode):\n'
       'SET_GLOBAL_SPEED PERCENT=80\n'
       'SET_LIVE_RETRACTION LENGTH=1.0                  # one parameter, others stay\n'
       'PAUSE_AT_LAYER LAYER=17\n'
       'CANCEL_PRINT                                    # twice within 60 s'))


chapter('5','The generators: Range, Labels, Plotter, Cable ties, Angles, Lithophanes, ColorPic, Gaskets, Frames, Bricks, Kits &amp; Figures',
  P("One quality rule applies to every generator (field-log rule): the nozzle never travels over an "
    "open hole or slot without retracting, no matter how short the hop. Every opening is a registered "
    "keep-out: label and screw holes, the cable-tie head channel and loop slot, the gasket groove, the "
    "backplate keyhole and stud holes, the frame view opening and the bridge-test spans. FLAT gaskets "
    "and lithophanes have no openings at all — one continuous bead per layer, nothing to cross."),
  H2('5.0 After generating: QUEUE or PREVIEW only (.84)'),
  P("Every generator (range, labels, plotter, cable ties, angles, lithophane, gasket, frame, texture, "
    "bridging test, resonance plots) finishes by asking what should happen with the new file. "
    "<b>Tools > After gen</b> holds the sticky answer - QUEUE (default): the new file is selected for "
    "printing right away and, when the generator worked ON a selected file (range excerpt, texture), "
    "REPLACES that selection - or PREVIEW: the file is written and selected for the 3-D preview only, "
    "nothing queued. Every generator also takes a per-run OUT= (example below). The setting survives a "
    "reboot; QUEUE is the pre-.84 behavior."),
  CODE('_GEN_OUT_SET OUT=PREVIEW\n'
       'GEN_CABLE_TIES COUNT=8 OUT=PREVIEW    (this run only)'),
  H2('5.1 Range — print a section of an existing file'),
  P("Re-print a broken section, test the critical middle of a long print, or make a part from a few layers. "
    "Pre-Print > Range/Stop: From/To (capped to the real layer count), Floor, Top, Brim + their shapes and fills, "
    "Create. The watcher builds name_Lfrom-to.gcode and the file AUTO-SELECTS itself. Start AS LEGACY "
    "(recommended) or AS SLICED (source temps 1:1)."),
  *B('layer FROM prints as the FIRST layer at Z 0.2 on the bed (global shift, original spacing kept)',
     'PRINT_START header means the NORMAL start flow: dialog, mesh, purge, first-layer rules',
     'own _FILE_INFO at the top — Live > File shows the excerpt values from layer 1',
     'the source fan returns from layer 2 — layer 1 prints without fan',
     'real PRINT_END at the end: park, stats, fanfare — never parked ON the part',
     'EXCLUDE_OBJECT_DEFINE blocks carried over; E and Z shifted to the file extrusion mode'),
  CENT(d_range_variants()),CAP("The same L-shaped layer with the four floor/brim variants — FOOTPRINT bridges concavities, OUTLINE follows the wall"),
  TBL(['Parameter','Values','Meaning'],[
   ['F.Shape / T.Shape','FOOTPRINT, OUTLINE','FOOTPRINT = convex hull (compact base); OUTLINE = true outline (concavities and holes stay open)'],
   ['F.Fill / T.Fill','GRID, SOLID','GRID = 45/135-degree hatch lattice (fast); SOLID = dense overlapping lines (solid surface, E-compensated)'],
   ['Floor / Top','0–10 layers','generated raft under the section (welds flush, zero gap) / solid cap over the last layer'],
   ['Brim','0–10 loops','zero-gap loops around the outline, printed on the FIRST layer (at the start of raft layer 1) — the first loop touches the model wall'],
   ['Fl.hole (floor hole)','0–80 mm, 0 = off','centered hole in the base with a THICK boss ring, printed as ONE continuous spiral from the hole edge outwards; travels over the hole retract; auto-clamps to the REAL outline + 2mm margin (never sticks out of L/round sections)'],
   ['Top hole','0–80 mm, 0 = off','centered hole in the cap, BRIDGE-FIRST: layer 1 anchors the edge (no sagging), layers 2+ open'],
  ],[34*mm,34*mm,92*mm]),
  CENT(d_range_hole()),CAP('Floor hole: cable feed or lampholder — E14 thread 15.0, E27 28.0, socket body: measure + 0.3 mm · top hole prints bridge-first'),
  TBL(['Preset','Diameter','Fits'],[
   ['cable feed','3–12 mm','zip ties, sensor cables, mains cable with gland'],
   ['E14','15.0 mm','E14 thread passes through (14 mm + tolerance)'],
   ['E27','28.0 mm','E27 thread passes through (27 mm + tolerance)'],
   ['socket body','measure + 0.3','whole lampholder body: typical E14 ~24, E27 ~33 mm — measure YOURS'],
  ],[40*mm,34*mm,86*mm]),
  P("Lamp parts: PETG, and for a press-fit thread start 0.2–0.3 mm under the measured diameter. A top "
    "hole auto-raises Top to 3 layers (bridge + 2 solid)."),
  P("The raft counts as INFILL-SOLID, the brim as BRIM — feature overrides work on the generated geometry. "
    "The excerpt OPENS with the feature that was active at the cut (a vase-style source states its ;TYPE: once in "
    "layer 1 - the excerpt re-asserts it, so the section never prints as the raft's solid infill), and the file info "
    "describes what the EXCERPT really contains: features from layers outside the range show as n/a, per-feature "
    "speeds are measured from the excerpt's own layers. ;TYPE: names from Orca/Bambu (gap fill), PrusaSlicer "
    "(External perimeter, top solid infill, ...) and Cura (WALL-OUTER) all map. "
    "Console: SET_LAYER_RANGE FROM=125 TO=225 FLOOR=5 FLOOR_SHAPE=OUTLINE TOP=3 BRIM=4 FLOOR_HOLE=15 TOP_HOLE=28 CREATE=1. <b>Stop@ N</b> "
    "in the same menu ends a print NORMALLY at layer N (stats, fanfare — not a cancel)."),
  H2('5.2 Labels — the built-in label maker'),
  P("Name tags, key fobs, drawer labels — engraved text without a slicer, entirely from the LCD: Tools > Labels > Text "
    "(up to 5 lines, character editor), Settings, Job > Add (queue n/24), Create. The watcher builds "
    "00_text_V01.gcode (00_ = top of the file list, V = your version number) and beeps. The same text at the same "
    "version REPLACES its own generated file — tweaks never pile up, and the uploaded original is never touched. "
    "Printing by layer: all bases in color 1, M600 pause, RESUME purges into the purge tower (15 mm clear, on the "
    "side the probe does not sweep), text on top. Every label is an exclude object. Between glyphs the head "
    "retracts — discrete letters, no ghost lines; the stroke never exceeds 1/5 of the cap height (anti-merge)."),
  CENT(d_font_specimen()),CAP("The five fonts at the same cap height — COND, NARROW and CAPS are the small-text specialists (narrow glyphs, tall x-height)"),
  CENT(d_label_anatomy()),CAP("Hole positions, the ~94 percent auto-fit with safe margins — and the grown fallback: text is NEVER shortened"),
  TBL(['Setting','Values','Meaning'],[
   ['W x H','default 50 x 15 mm','the plate — keychain tags up to near-bed signs (220 x 220)'],
   ['Font','SMOOTH, MONO, COND, NARROW, CAPS','CAPS prints everything as capitals'],
   ['Lines','1-5','text lines per label'],
   ['Size','0 = auto, or cap height in mm','0: font fills ~94 percent of the label; explicit size is a TARGET — the label GROWS so it fits'],
   ['Stroke','0 = auto, or mm','letter LINE WIDTH — 0.6 = nozzle width = single-line letters; capped at cap/5 (anti-merge)'],
   ['Vers','V01-V09','version in every generated file name — same text + same version replaces its own file, a new version keeps the old one'],
   ['Hole','NONE/LEFT/RIGHT/TOP/BOTTOM + diameter','2 mm from the edge — key rings clip through'],
   ['Base/Text layers, LH, Ironing, Brim, 2 colors, Gap','—','plate thickness, text relief, surface, adhesion, two-color mode, grid spacing'],
  ],[34*mm,44*mm,82*mm]),
  P("Auto-fit / auto-grow: if the letters would drop below ~2.8 mm caps — or an explicit size does not fit — the "
    "label grows (width first, then height, up to bed size) instead of erroring. Preview fit? (Tools > Labels > Settings) "
    "answers with the REAL numbers before you generate anything: final label size including growth, cap height, "
    "effective stroke, ~characters per line, the MINIMUM size a fixed font needs, plus warnings (stroke capped, "
    "tower does not fit). Console one-liner: "
    "GEN_LABELS TEXT=Werkstatt~Keller|Vase W=60 H=30 FONT=COND SIZE=8 HOLE=LEFT HOLE_D=5 (~ = line break)."),
  H2('5.3 Plotter — images, photos and text with a pen'),
  P("Mount a pen instead of (or next to) the nozzle. The name is the switch: name.png.gcode (PNG), "
    "foto.jpg.gcode (baseline JPEG), drawing.svg.gcode (SVG), plan.pdf.gcode (vector PDF), notes.txt (text page). "
    "Options in the name: bild.c3.s035.png.gcode = 3 shades, 0.35 mm hatch (defaults c2/s040). The converter "
    "replaces the file in place."),
  *B('auto-contrast (Otsu) finds the ink on any paper tint — photos of hand sketches just work',
     'dark backgrounds just work: the converter samples the image border; dark border + brighter interior = '
     'INVERT (Invert AUTO/ON/OFF in the menu, logged in the file header)',
     'text auto-wraps and auto-shrinks to fit ONE page (letters 7 mm down to 1.8 mm), umlauts correct',
     'Plot status draws the SHOW_STATUS report on paper — mode, material, temps, PA, flow, shaper, overrides',
     'menu: DRAW vs DOTS stipple, dot gap, pen offset X/Y/Z, scale X/Y percent (auto-capped at the bed), bed '
     'corner limits, extruder ON/OFF (draw with filament), speeds, Drive frame test — everything centered automatically',
     'start: AS SLICED = pure pen (no purge); AS LEGACY heats when the extruder is ON. Multi-color plots pause '
     '(M0) at every pen change; live tuning while plotting: pen speed percent, pen Z +-0.05, X/Y +-0.5',
     'the resonance diagrams of the calibration chapter are plotted or printed the same way (ch. 10.5)'),
  H2('5.4 Cable ties — the built-in cable-tie maker'),
  P("Printable cable ties in ONE file, straight from the LCD (menu Tools > Cable ties) — no slicer, no modeling. "
    "Each tie is a flat strap with a NORMAL small closure head like a shop-bought tie: thread the chamfered tip "
    "in, pull tight, cut off the excess. Head size, slot clearance, tooth pitch and bead spacing ALL auto-scale "
    "with the strap width — you never tune the mechanism. Two closures: CLASSIC (the normal one-way pawl — locks "
    "at every tooth, cut to remove) and LOOP (a frame loop with an open slot plus beads along the strap — catches "
    "at every bead, lifts back out: adjustable and reusable). Settings: Count 1-24, Len 50-300 mm, Width 2-12 mm, "
    "Layers 3-6 (strap thickness), LH 0.12-0.32 (finer layers = smoother teeth), Closure, Brim, Vers. Create "
    "(beeps) builds the file in the background (~1-3 s, niced), it auto-selects as 00_Ties_lenxwid_CLA|LOO_Vxx.gcode "
    "and the ready-message lists everything that was auto-adapted. Every tie is an exclude object (TIE_1..n)."),
  CENT(d_tie_anatomy()),CAP("Anatomy of a generated tie: top view with teeth and chamfered tip, the head "
    "cross-section (channel, pawl strip at the entry), the two closures CLASSIC vs LOOP — and how width 2/8/12 auto-scales the head"),
  TBL(['Setting','Range','Meaning'],[
   ['Count','1-24','ties in ONE project file — the grid fits them or errors clearly'],
   ['Len','50-300 mm','strap length: bundle circumference + head + pull-in reserve'],
   ['Width','2-12 mm','strap width — the closure AUTO-SCALES: head (w+4.5)x(w+2.6), slot w+0.5, pitch 0.45x; under 3.6 mm a 0.4 nozzle prints crisper'],
   ['Layers','3-6','strap thickness: 3 = flexible, 6 = stiff strong band'],
   ['LH','0.12-0.32 mm','layer height — 0.12-0.16 prints smoother teeth'],
   ['Closure','CLASSIC / LOOP','normal one-way pawl vs adjustable bead loop (reusable)'],
   ['Brim','ON/OFF','loops around each head on layer 1 (thin-part adhesion)'],
   ['Vers','V01-V09','same settings + same version = the file replaces itself'],
  ],[26*mm,32*mm,102*mm]),
  P("Material matters (thin flexing parts): PETG or TPU bend best and hold tight loops; PLA works for gentle "
    "curves only. The file sets fan from layer 2 itself; the standard first-layer brake applies. Console: "
    "GEN_CABLE_TIES COUNT=6 LENGTH=120 WIDTH=8 LAYERS=3 VARIANT=LOOP (everything optional)."),
  H2('5.5 Angles & flat connectors — structural plates'),
  P("Angle plates (L-brackets in ANY angle 30-170, equal or unequal legs) and flat connectors (two boards joined "
    "side by side) — screw-on structural parts, menu Tools > Angles+Flat. Mode switches between Angle (L) and "
    "Flat splice (the Angle input and the Rib submenu hide themselves in Flat mode; the legs rename to "
    "Left/Right). THE HOLE SYSTEM: holes sit on each leg's centerline, evenly spaced between the corner zone "
    "and the leg end; the diameter is CLAMPED to width - 6 mm (never too big for the leg); the count "
    "auto-reduces if the leg is too short; in FLAT mode both halves share the SAME pattern. Countersink ON "
    "adds a two-step cone so flat-head screws sit flush. Stiffener: None / Gusset rib (triangle over the "
    "corner) / Stepped rib (gusset + smaller one on top — strongest). Create (beeps) -> "
    "00_Angle_90deg_60x60_Vxx.gcode or 00_Flat_80x25_Vxx.gcode, auto-selected, each plate an exclude object."),
  CENT(d_angle_anatomy()),CAP("The auto hole layout (corner zone shaded, holes on the centerline, clamped "
    "diameter), the countersink cross-section (flat-head screw flush), and what Angle 45/135 + Flat splice look like"),
  TBL(['Setting','Range','Meaning'],[
   ['Mode','Angle / Flat','bracket vs straight splice — Flat hides Angle and Rib, renames legs to Left/Right'],
   ['Angle','30-170 deg','only in Angle mode'],
   ['Leg A / B (Left/Right)','20-150 mm','the two legs (from the corner) or the two halves of a flat splice'],
   ['Width','8-60 mm','leg width (plate depth)'],
   ['Layers','4-12','plate thickness'],
   ['Holes + Hole D','0-6 per leg, 2-10 mm','auto-arranged, diameter clamped to width-6 (max 10), count auto-reduced'],
   ['Countersink','ON/OFF','two-step cone on the top layers (flush flat-head screws) vs straight hole'],
   ['Rib','None / Gusset / Stepped','corner stiffening (angle mode only)'],
   ['Count + Vers','1-12, V01-V09','plates per project file; version in the name'],
  ],[30*mm,34*mm,96*mm]),
  P("Sizing rule of thumb: an angle's corner zone is as wide as the leg (the legs overlap there) — the first "
    "hole sits about width + hole/2 + 1.5 mm from the corner; a 90/40/40 bracket with 4 mm screws fits 1-2 "
    "holes per leg. The ready-message lists EVERY automatic adjustment — nothing clamps silently. Console: "
    "GEN_ANGLES COUNT=2 ANGLE=90 LEG_A=60 LEG_B=60 WIDTH=25 LAYERS=6 HOLES=2 HOLE_D=4 CS=1 STIFFENER=1 FLAT=0 "
    "(CS=1 countersunk; FLAT=1 = flat connector)."),
  H2('5.6 Lithophanes — photos that glow'),
  P("Turn any picture into a back-lit relief print: dark areas print thick, light areas thin — held against a "
    "lamp or window the photo appears. No slicer, no modeling, no manual image editing: upload a .png/.jpg into "
    "the gcodes folder (drag + drop in Mainsail), the Images list of Tools > Lithophane refreshes on its own "
    "(newest first, 10 slots — pictures uploaded for PEN PLOTTING are in the same list, the original stays "
    "untouched). Slot press = Create: the watcher generates in its own background thread (big pictures ~a "
    "minute), the file auto-selects as 00_Litho_name_Vxx.gcode. The picture prints STANDING (layer lines run "
    "with the image — that is what keeps the detail), 100% solid, thickness 0.7-3.0 mm, the file sets speeds "
    "and fan itself. White or natural PLA glows best; the effect unfolds with back-light 20-50 mm behind the "
    "plate. Delete image = 2-press confirm — only the image goes away, its plotter .gcode stays. Console: "
    "LITHO_CREATE INDEX=0 / LITHO_DEL_SLOT INDEX=2."),
  CENT(d_litho_anatomy()),CAP("How brightness becomes thickness (0.7 mm light - 3.0 mm dark, standing plate "
    "with brim) and what Levels does: 0 = continuous photo grey, 4 = chunky posterized, 12 = subtle terraces"),
  TBL(['Setting','Range','Meaning'],[
   ['Orient','STANDING / FLAT','STANDING (default): on edge, the classic recipe - most detail. FLAT (.83, step print since .90): lying on the bed - back glass-flat, the top carries the image as clean gray STEPS (full layers, no wavy relief)'],
   ['Height / Size','30-200 mm','STANDING: picture height = print height in Z. FLAT: the picture size in XY (the bed plane) - Z is only the relief = layer count x layer height'],
   ['Layer','0.08-0.2 mm','0.12 default; 0.08 = maximum detail (double the print time)'],
   ['Levels','0-12','STANDING: 0 = continuous grey (photo), 2-12 posterized. FLAT: the gray STEP count (0 = auto 4)'],
   ['StepL','1-30','FLAT: layers per gray step - step 0 = the whole light background as full layers, every darker step its region on top, the darkest = the contour lines'],
   ['Color swap','OFF / LAST / EACH','FLAT only: OFF = one filament. LAST = M600 right before the darkest step (white body + black contours). EACH = M600 at every step. A purge tower (12x12, 15mm probe clearance) prints along whenever swaps are on'],
   ['Border / Corner','0-10 / 0-20 mm','FLAT: picture frame at full height around the plate; Corner = rounded corners (0 = square)'],
   ['Contrast','ON/OFF','extra boost after the stretch - level edges stand out (sketches, logos, text)'],
   ['Frame','ON/OFF','border frame that holds the thin plate straight (recommended)'],
   ['Brim','0-10 loops','the plate prints STANDING — the brim anchors it'],
   ['Ironing','ON/OFF','slow smoothing pass over the light side (FLAT: every step cap)'],
   ['Vers','V01-V09','same settings + same version = the file replaces itself'],
  ],[26*mm,32*mm,102*mm]),
  P("How FLAT prints (step print, rebuilt after the .90 field log - the old terraced "
    "relief printed wavy, the nozzle dove into the picture and the probe caught on it): "
    "the picture is contrast-stretched (percentiles) + optionally boosted, quantized "
    "into Levels gray steps and printed ONE STEP AFTER ANOTHER as full layers. Step 0 = "
    "the whole light background (one clean surface - iron it), every darker step its "
    "nested region on top, the darkest = the black contour lines. Nothing ever prints "
    "over air, the nozzle never dives, the probe never catches. The classic sketch "
    "recipe: white background image + Levels 3 + Color swap LAST = white body with "
    "black lines. File: 00_LithoF_name_Vxx.gcode."),
  H2('5.7 Gaskets — the built-in seal maker'),
  P("Sealing rings straight from the LCD (menu Tools > Gaskets): outer/inner diameter and height, flat face "
    "or groove. One continuous spiral per band — no seam, no start-stop blob where a seal would leak, and no "
    "string ever dragged across the open groove (crossings retract, even the short band-to-band hop between "
    "the lips). Settings: "
    "OD 12-200, ID 6-190 (band >= 2.4 mm), Height 0.4-6 mm, Face FLAT/NUT, Ironing, LH, Vers. NUT mills a "
    "groove into the face: two raised sealing lips = higher contact pressure = seals better on uneven flanges "
    "(needs 2 mm+ height, falls back to FLAT with a note if the band is too narrow). Create (beeps) -> "
    "00_Seal_odxidxh_Vxx.gcode, auto-selected. Measure the sealing surface of the flange, not the pipe. TPU "
    "seals best (the file already prints at 15 mm/s), PETG works — and DRY the filament: moisture bubbles are "
    "the #1 seal killer. Console: GEN_SEAL OD=40 ID=20 HEIGHT=1.2 PROFILE=FLAT IRONING=0."),
  CENT(d_seal_anatomy()),CAP("The ring (OD/ID, one continuous spiral — no seam) and the two faces in "
    "cross-section: FLAT = full contact, NUT = groove with two raised sealing lips"),
  H2('5.8 Frames — picture frames & display cases'),
  P("A frame for a photo or a deep display case, printed in one piece with its backplate, stand and "
    "hidden hanging options (menu Tools > Frames). Main design goal: a uniform, smooth FRONT face — the "
    "frame prints lying on its back, the visible face points up and gets the ironing pass. Settings: "
    "Preset (9x13 · 10x15 · 13x18 · A6 — sized for the real 220mm bed) or custom W/H 40-230, Depth 3-60 "
    "(under 15 = flat frame, 15+ = display case), Border 4-30, Corner r 0-30, Shape RECT/OVAL, Closure "
    "BACK/SIDE, Hang TOP/BOTTOM/LEFT/RIGHT/OFF, Stand, Ironing, Infill 5-100 (sparse body below "
    "100 - its own feature tag), Top layers (front face, auto/1-15), Bottom layers (back skin, "
    "default 2), Vers. The profile is "
    "zero-overhang: solid back band, photo groove with the closure nubs, bridge shelf, ironed front."),
  P("Placement & first layer (field log .74): every plate — one-piece, multi Part A/B, split kit — "
    "sits centered on the usable bed, never crammed into the x0/y0 corner. The first layer of every "
    "part prints in a fixed discipline: brim → inner wall → outer wall → ONE continuous zigzag fill "
    "(back-and-forth with extruded connectors — singly printed lines curled up at their starts/ends "
    "and frayed the borders); the only travels inside that fill cross open holes (keyhole, stud "
    "holes, cable slot) and those retract."),
  P("Bed fit is checked while generating (real bed from [r2_postproc]): frame + backplate side by side "
    "fit = one file; they don't but the frame alone fits = TWO PLATES (R90.1a): Part A = frame, Part B = "
    "backplate + stand — Part A auto-selects (never auto-starts), the generation beeps once per plate, "
    "and the end of Part A says on console + LCD which file is next; even the frame alone too big and "
    "RECT = 4-strip glue kit (strips on plate A, plate on B, every part an exclude object, glue the "
    "butt joints with wood glue); still too big or OVAL = a clear message with the border limit — the "
    "guard beeps and shows on the LCD, nothing is written. Assembly BACK (.91 field fix): the photo "
    "drops onto the shelf with 0.8mm play per side (real photos run up to ~1mm over the nominal cut - "
    "no trimming), the backplate is 0.3mm smaller than the photo shaft per side - press it in, the 4 "
    "wall nubs (left/right/top/bottom) click over its edge with a 0.2mm overlap. No sanding, no "
    "sliding. SIDE: photo + cover plate slide together through the slot in the left wall. The hang keyhole hides in the plate (invisible from the front); "
    "the easel stand plugs into two D2.7 plate holes. Console: GEN_FRAME PRESET=10x15 DEPTH=8 BORDER=12 "
    "SHAPE=RECT CLOSURE=BACK HANG=TOP STAND=1."),
  P("R90.1b surface & extras (each its own submenu): SURF picks the visible face — Ironed (classic), "
    "Bed texture (FLIP: the front prints against the bed, the plate texture is the face, no ironing), "
    "or a structured border: Lines / Waves / Honeycomb with depth 0.4-2.4, spacing 2-15, angle 0-90, "
    "wave amplitude 0.3-3, cell 4-20mm, direction IN (grooves) or OUT (ridges) — RECT only, replaces "
    "ironing. DISC adds a glass/plexi/foil/litho insert: FRONT = in front of the photo, captured by a "
    "1.2mm lip; BACK = behind the photo on the back band (backlit) — the groove grows by the disc "
    "thickness. CABLE (display case only) = a hidden 6mm duct through the bottom bar, opening 2.5mm "
    "behind the back face straight into the interior — LED wiring without a visible hole. Console: "
    "GEN_FRAME PRESET=10x15 DEPTH=20 CABLE=1 DISC=PLEXI DISC_T=1 DISC_SIDE=BACK."),
  CENT(d_frame_anatomy()),CAP("Cross-section through the wall (front up: ironed front band, bridge "
    "shelf, groove with photo + plate + nubs, back band) and the two closures: BACK = snap-in plate "
    "(press in - 4 wall nubs click over it), SIDE = slide-in slot in the left wall"),

  H2('5.10 Building bricks — the exact system geometry (R121)'),
  P("The printer becomes a brick factory: bricks, plates and tiles with the EXACT geometry of the "
    "building-block system - printed parts clamp to each other AND to original bricks. The three "
    "numbers that matter: body = n*8-0.2mm (the 0.2mm play IS the clamp), stud = O4.8x1.8mm hollow "
    "(1.2mm wall - prints without a solid blob), underside tube = O6.31 at every inner grid crossing "
    "(the tubes spread over the stud below - the clutch comes out right). Brick 9.6 / plate 3.2mm, "
    "tiles = smooth plates; layer heights that do not divide evenly snap to whole layers (noted in "
    "the header). Layer 1 prints solid + brim, the tubes open from layer 2 up. Catalog: 45 codes - "
    "B=brick, P=plate, T=tile, each 1x1..8x8 (width x length in studs). LCD: Tools > Bricks > "
    "Catalog bumps the count per code (same codes merge, max 120 parts), CREATE builds "
    "00_Bricks_V01.gcode - one color, every part its own exclude object. Console: "
    "GEN_BRICKS CODES=\"B2x4:3|P2x2:2\"."),
  H2('5.11 Brick kit — a sliced file becomes a building kit (R125)'),
  P("The kit generator reads ANY sliced print file and rebuilds it as a stylized brick kit: the "
    "object is rasterized onto the stud grid (0.8mm sampling) and decomposed into 2-wide bricks - "
    "the kit look. ONLY the object flows in: support, brim, skirt and prime-tower moves are filtered "
    "out before the geometry is built (foreign slicer files work too). Closed bodies fill solid; "
    "hollow bodies (vases, sparse infill under 15%) become RING WALLS - the silhouette stays, print "
    "time drops. Detail AUTO picks the band size by model size (up to 10 studs MICRO, up to 26 "
    "SMALL, else BIG - brick bands 9.6mm vs plate bands 3.2mm). Colors 1-8 with two strategies: "
    "BY_LAYER = one color per plate, the plate change IS the color change (zero M600); BY_OBJECT = "
    "parts print sequentially, M600 only at color boundaries. Up to 800 parts, ~110 per plate "
    "(A, B, C...), every part its own exclude object. LCD: Tools > Bricks > Kit from file (Source "
    "picks the 5 newest sliced jobs, Detail, Mode, Colors). Console: GEN_BRICKKIT SRC=box.gcode "
    "DETAIL=AUTO MODE=BY_LAYER COLORS=3."),
  H2('5.12 Figures — assemble-it-yourself (R126)'),
  P("Stylized figures in the classic caliper proportions mapped onto the building system: 5 parts "
    "per figure - legs, torso, two arms, head. Assembly without glue: the torso presses onto the "
    "hip tenon, the arms slide onto the shoulder pins (they swing), the head presses onto the neck "
    "post (it turns). 100% = original size AND system-true: the hands grip O4.8 studs and axes, "
    "hats sit on the head stud, the feet click onto studs (anti-studs underneath). Other scales "
    "(25-300%) are display figures. Count 1-24, one color, every part its own exclude object, "
    "~39mm tall at 100%. LCD: Tools > Bricks > Figures (Scale, Count, CREATE). Console: "
    "GEN_FIGURES SCALE=100 COUNT=2."),
  H2('5.13 ColorPic — photos in full color, no backlight (R120)'),
  P("The color sibling of the lithophane: the photo prints FLAT as stacked color bands, lightest "
    "first - every darker band prints only its (nested) region on top, so the picture needs NO "
    "backlight and works from every angle. Same image list as the lithophane; the pipeline "
    "stretches the contrast (percentiles + optional boost) and quantizes into 2-8 luminance bands. "
    "At every band boundary the file calls M600 - the nozzle LED BLINKS from the old to the new "
    "color while you swap, and a purge tower (12x12mm, 15mm probe clearance) takes prime + wipe "
    "after every change. Swap can be switched OFF (every band prints in one color) and Contrast "
    "toggles the boost. Settings: Width 25-230, Bands 2-8, Band height 0.4-3mm (total height = "
    "bands x band height), Colors = per-band palette light->dark (14 codes, auto ramps when "
    "empty), Ironing per band cap. LCD: Tools > ColorPic. Console: GEN_COLORPIC SRC=photo.png "
    "WIDTH=120 BANDS=4 COLORS=WHT,GRY,BLK BANDH=0.8 SWAP=1."),
  )

chapter('5.9','Texture: fuzzy skin & shaped bumps (any g-code file)',
  P("The only generator that does not create a part - it rewrites the OUTER WALL of a file you "
    "already have. FUZZY scatters every outer-wall vertex (seeded - same file + same settings = same "
    "result): matte, grippy, the classic fuzzy skin. BUMPS follows a pattern: Grid (egg-crate "
    "dimples), Waves (diagonal ripples WITH a z-phase - the pattern crawls layer to layer and "
    "visually swallows layer lines), Honeycomb (hex dimples) or Mandelbrot (a fractal landscape, "
    "unique per bed position). Everything else stays byte-identical: ;TYPE: tags, EXCLUDE_OBJECT, "
    "markers, E, Z and F values - inner walls, infill, ironing and supports print exactly as sliced."),
  TBL(['Parameter','Range','Meaning'],[
   ['Mode','OFF / FUZZY / BUMPS','OFF = Apply refuses with a hint'],
   ['Fuz thick','0.1-0.6 mm','scatter radius (fuzzy)'],
   ['Fuz dens','10-100 %','share of scattered vertices'],
   ['Pattern','Grid / Waves / Honeycomb / Mandelbrot','bump shape (bumps)'],
   ['Scale','3-60 mm','cell size - fine orange peel .. bold dimples'],
   ['Amp','0.1-0.8 mm','bump depth'],
   ['Dir','OUT / IN','grows away from / cuts into the part'],
  ],[34*mm,52*mm,78*mm]),
  P("Workflow: select the file as always, Pre-Print > Texture, pick mode + values, > Apply (beeps) - "
    "the watcher writes a NEW <name>_TX_V01.gcode in the background (V02, V03 ... on repeat, the "
    "source is never touched), then CHECK IT IN THE 3D VIEWER - nothing auto-starts, by design. "
    "(.84) After gen applies (ch. 5.0): QUEUE selects the _TX result and replaces the source's "
    "selection (the source file itself stays untouched); PREVIEW leaves the selection alone. "
    "Special cases (tested): files without outer walls get zero shifts, no crash; the first outer "
    "vertex and zero-length restarts stay untextured (no approach direction); M82 absolute E, E-only "
    "retracts, G0 travels and CRLF endings pass untouched; OrcaSlicer/Bambu spellings are recognized."),
  CODE('TEXTURE_APPLY FILE=myfile.gcode MODE=FUZZY THICK=0.3 DENSITY=100\n'
       'TEXTURE_APPLY FILE=myfile.gcode MODE=BUMPS PATTERN=WAVES SCALE=10 AMP=0.35 DIR=OUT'),
  P("FILE may be omitted - the SELECTED file is the target (same as the LCD). Done = r2_done beeps "
    "+ console summary; an error sounds the alarm and the LCD says what to fix."),
  )


chapter('6','During the print: tuning, pauses, objects',
  H2('6.1 Live tuning reference'),
  P("Works in EVERY start mode — including AS SLICED and while plotting. The LCD shows Klipper REAL values: flow "
    "reads the actual extrude factor, PA reads pressure_advance, accel reads max_accel — what you see is what runs."),
  CODE('Speeds:  SET_GLOBAL_SPEED PERCENT=20..300 — ONE global factor (running feature re-applies on top)\n'
       'Feature: SET_OVERRIDE_VALUE NAME=feat_spd_<code> VALUE= · feat_acc_<code> · feat_on_<code> (16 codes)\n'
       'Accel:   SET_GLOBAL_ACCEL ACCEL= — features with their own accel keep it\n'
       'FeatAcc: SET_GLOBAL_ACCEL_PERCENT PERCENT=10..300 — scales ALL feature accel limits in the same ratio\n'
       'Limits:  SET_LIVE_VELOCITY · SET_LIVE_MINIMUM_CRUISE_RATIO · SET_LIVE_SQUARE_CORNER\n'
       'Extrusion: SET_FLOW_RATE PERCENT=1..300 · SET_LIVE_PRESSURE_ADVANCE · SET_LIVE_PA_SMOOTH\n'
       '          SET_LIVE_RETRACTION LENGTH= SPEED= UNRETRACT_SPEED= EXTRA=\n'
       'Temps:   SET_LIVE_HOTEND_TEMP T= · SET_LIVE_BED_TEMP T=\n'
       'Fan:     SET_FAN_SCALE PERCENT=        Babystep: BABYSTEP_UP/DOWN[_FINE]\n'
       'Objects: SKIP_OBJECT OBJECT=name (2x) · SKIP_CURRENT_OBJECT · SHOW_OBJECTS\n'
       'Z-Hop:   SET_Z_HOP ENABLE=1|0 HEIGHT=0.1..3 (lifts over every firmware retract)\n'
       'FeatPA:  SET_FEAT_PA FEATURE=<code> PA=0..0.3 — PA for ONE feature, global returns after (.85)\n'
       'Shaper:  SET_FEAT_SHAPER_OFF FEATURE=<code> STATE=1|0 — shaper off while that feature prints (.85)\n'
       'FanClmp: SET_FAN_CLAMP ON= MIN= MAX= BRIDGE= — every M106 runs inside the curve (.85)\n'
       'UnretX:  SET_UNRETRACT_EXTRA EXTRA=-1..3 — seals the dot after a travel (0 = off)'),
  P("<b>Where does a value come from?</b> PARAM_SOURCES (Live Tuning > Sources) prints the provenance of every "
    "parameter: file, your pre-print override, or LIVE in Klipper now. FeatSpd/FeatOn/FeatAcc edit the feature "
    "CURRENTLY printing (the Now: line); feature overrides the file cannot use are parked at start and listed in "
    "the console."),
  H2('6.2 All pauses explained'),
  CENT(d_l1l2()),CAP("L1/L2 temps (red) + speed (blue dashed) — every object starts from scratch"),
  TBL(['Pause','Trigger / condition','After'],[
   ['User pause','LCD PAUSE NOW, PAUSE, QUICK_PAUSE, M0/M1','parked, waits for RESUME'],
   ['Start dialog hold','file calls PRINT_START','AS SLICED / AS LEGACY / CANCEL'],
   ['Planned','PAUSE_NEXT_LAYER, PAUSE_AT_LAYER LAYER=n','one-shot at the next boundary / at layer n'],
   ['Runout','sensor empty, next layer boundary, filament mode','load, RESUME purges'],
   ['Filament change','M600 / CHANGE_FILAMENT','filament mode; RESUME purges'],
   ['Legacy dialog','old file detected, start_confirm ON','decision within seconds; heaters only preheat in the background'],
   ['Legacy prep','AS LEGACY + Old files ON','homes, heats, meshes, purges, GAPLESS continue (position restored, anti-ooze standby at 170 C)'],
   ['Sequential object','Z falling edge >=1.6 to <0.75 mm, layer >=2 (z-hops filtered)','L1 temps + L1 speed; pauses only if a heater must move'],
   ['Cancel 1st press','CANCEL_PRINT once','arms; 2nd press within 60 s cancels; the arm expires'],
  ],[32*mm,66*mm,62*mm]),
  CENT(d_seq()),CAP("Sequential object detection: Z falls clearly at the object change and re-anchors — z-hops and parking never fake a change"),
  P("While paused: heaters KEEP targets, idle timeout infinite, sensor disabled, the LCD shows the reason. "
    "Self-healing: if our mode disagrees with Klipper, the watcher re-syncs after ~5 s."),
  H2('6.3 Resume &amp; cancel'),
  *B('RESUME: disarms confirmations, returns XY, refills the park retract ON THE WAY (net -0.5mm de-ooze, never a positive extrusion at the print position - after a filament change the strip already settled the pressure), then Z slowly, re-applies the current '
     'feature type, re-applies the L1 speed brake while layer 1 runs (the brake always has the last word)',
     'CANCEL_PRINT (2x): 1st press arms, 2nd within 60 s: lift, park, heaters off, stats — override switches stay as set',
     'after EVERY end: _PRINT_CLEANUP resets per-print state (live tuning to 100 percent, layer tracking, planned '
     'pauses) — pre-print settings, material and mesh deliberately KEPT'),
  H2('6.4 Parking &amp; safe movement'),
  CENT(d_park()),CAP("Park anatomy — lift, farthest corner, anti-ooze, slow resume"),
  *B('lift +5 mm capped below Z max; XY to the corner FARTHEST from the objects; anti-ooze retract -3 mm only if >=170 C',
     'every move checks homed_axes — unhomed axes never move; PAUSE, M600, M0/M1 inherit the same guard',
     'Z high-water re-anchored at PAUSE and every object start — parking can never fake an object change',
     'every start path homes first (G28); babystepping is runtime-only, the saved offset never changes'),
  H2('6.5 Skipping objects &amp; ending early'),
  P("<b>Skip a single object</b> (multi-object prints): Live Tuning > Objects — SKIP_OBJECT OBJECT=name (2x "
    "confirm), SKIP_CURRENT_OBJECT for the one printing now, SHOW_OBJECTS lists all. Works for sliced "
    "multi-object files AND generated files (labels, ranges, towers — every generated part is an exclude object). "
    "KAMP mesh and smart parking know the remaining objects."),
  P("<b>End normally at a planned layer:</b> Stop@ N — when layer N begins, the print ends like a FINISHED print "
    "(park, stats, fanfare, cooldown). With the range generator this covers printing only part of it in both "
    "directions: up to N from the file start, or a standalone section From-To."))


chapter('7','Filament: load / unload / change / runout / cold pull',
  CENT(d_runout()),CAP('Runout: alarm → pause at the next boundary → load → RESUME purges'),
  *B('temperatures always right: print temp kept during prints; idle heats to ≥ 200 °C (or preset)',
     'load_length 60 mm (LCD 20-150) feeds LOAD_FILAMENT · unload_length 90 mm (LCD 40-150) feeds unload AND change',
     'PURGE_MORE purges another 15 mm during a change (until the old color is gone)',
     '<b>R92 color-change purge:</b> the flush lands as a FLAT 0.3 mm strip beside the objects (front edge, '
     'probe-safe window) - never a blob at the park corner where the micro probe would catch it while meshing',
     'repeat runout events while armed are ignored (no spam)',
     '<b>BTT SFS V2.0:</b> switch part = filament end (planned pause at the boundary); encoder part = clog '
     '(immediate safe pause). SET_FILAMENT_SENSOR takes the SECTION name - the BTT example\'s switch_sensor '
     'was invalid (field log). Since then pause/resume/cancel switch the encoder too (guarded)',
     '<b>Cold pull</b> (Maintenance &gt; Filament): Heat-to (PLA ~240) / Pull-at (PLA ~100, PETG/ABS 120-140) → '
     '"1) Prep + PULL" heats, extrudes 25 mm, fan-cools → ALARM → pull in ONE firm motion → "2) Finish" verifies. Idle only.',
     '<b>Retraction test:</b> retract/unretract pairs at temperature to compare stringing live'))


chapter('8','Temperature system L1/L2',
  *B('<b>Two temperatures per heater:</b> Layer 1 (L1) and from-layer-2 (L2). Priority: override ON &gt; file &gt; preset.',
     'purge + layer 1 = L1 (the start paths heat the hotend to the L1 value for the purge)',
     'file M104/M109/M140/M190 redirected strictly BY LAYER — layer 1 → L1, ≥ 2 → L2 (both takeover modes; '
     'AS SLICED passes 1:1)',
     'layer 2 = L2 — switched by LAYER_MARK (marked files) or the Z tracker (legacy / AS LEGACY), identical values',
     'sequential: every object restarts with L1','live temps: SET_LIVE_HOTEND_TEMP T= / SET_LIVE_BED_TEMP T=',
     'idle filament handling heats to ≥ 200 °C (or the preset value)'),
  H2('Temperature safety'),P('heaters off at print end + on shutdown/cancel paths; pauses keep targets ON purpose; '
    'hotend fan cools down (cooldown_fan_time, default 30 s); after errors: check the console, then TURN_OFF_HEATERS.'))


chapter('9','Speed, acceleration &amp; machine limits',
  H2('First-layer speed (default 75%, 0 = off)'),
  *B('global M220 brake during layer 1 — set at the start, re-applied after EVERY resume (Klipper restores the '
     'speed factor from pause time — that back door is now closed) and at every object change',
     'the file\'s own M220 commands are capped to the limit while layer 1 runs',
     'AS SLICED: not applied','restored at layer 2 (marker or Z-tracked, whichever counts)'),
  H2('Global = the ONE overall regulator '),
  *B('Global Speed % (LCD, L1 brake, file M220) scales EVERY speed in relation — stored CLEAN as g_speed_clean, '
     'never multiplied by anything else',
     'per-feature values sit ON TOP of the clean global: Feature speed = % × global (global 80 + wall 80 = 64 for '
     'wall segments; the next feature is back at 80 — no decay). Example: feature base 60 mm/s at 200% = 120; '
     'global 150% = 180 mm/s — the feature percentage itself never moves',
     'FLOW — same shape (R92.1): the global flow is the ONE regulator; a feature flow % always REFERS to it: '
     'global 98% × feature 110% = 107.8% effective (it used to REPLACE the global — fixed)',
     'ACCEL — feature values are HARD LIMITS; the global accel never overrides them (it rules travel + features '
     'without their own). ON TOP: one global percent scaler (Feat x% / SET_GLOBAL_ACCEL_PERCENT) scales ALL '
     'feature limits in the same ratio — Live > Accel shows the current value live (Eff: 1500mm/s2)',
     'BOTH SET (field rule): every global speed change re-applies the running feature ON THE SPOT — global 100 -> 150 '
     'with wall at 200% moves the wall from 200 to 300%, not back to 150. And a feature with its own accel KEEPS it; '
     'the global accel rules everything that prints without one',
     'WHY (field log: "19% although 75% was set"): the old APPLY_TYPE ran through the M220 interceptor and '
     'multiplied on the ALREADY scaled factor, feature by feature (75×80 = 60 = 48 = ... = 19%). Now features '
     'talk to Klipper directly via the BASE commands M99220/M99221/M99204 — the global value is never touched',
     '16 features: outer/inner wall, overhang wall, sparse/solid infill, top/bottom surface, bridge, internal '
     'bridge, gap fill, support, ironing (+flow), skirt, brim, prime tower, custom code — own ON switch each '
     '(Pre-Print > Features); Live Tuning shows the CURRENTLY printing feature as Cur:/CurOv:/CurAcc: and has '
     'ALL 16 as Live > Features (edits re-apply on the spot)',
     'ORIGINALS & OFF : post-processor v4 MEASURES the real speed (most frequent F per feature segment) and '
     'accel (M204 in effect) straight from the g-code — shown everywhere (File: rows) and used as the reset target: '
     'switching a feature OFF restores speed 100% / the file\'s accel / the slicer ironing flow. Only features the '
     'file really contains are editable (TYPES= guard; unprocessed files stay fully editable)',
     'SET_GLOBAL_SPEED is never capped; without overrides the file rules 1:1'),
  H2('Machine limits (Klipper toolhead limits)'),
  TBL(['Parameter','Override (Pre-Print &gt; Motion)','Live command (Live &gt; Velocity)','Klipper setting'],[
   ['Max acceleration','accel (ON + value)','SET_GLOBAL_ACCEL','max_accel'],
   ['Max velocity','velocity (ON + value)','SET_LIVE_VELOCITY','max_velocity'],
   ['Minimum cruise ratio','min_cruise (ON + value)','SET_LIVE_MINIMUM_CRUISE_RATIO','minimum_cruise_ratio (replaced accel_to_decel/a2d)'],
   ['Square corner velocity','square_corner (ON + value)','SET_LIVE_SQUARE_CORNER','square_corner_velocity'],
  ],[36*mm,40*mm,52*mm,34*mm]),
  P('Overrides apply at print start ONLY when ON + value &gt; 0 — everything OFF means Klipper\'s [printer] limits and '
    'the file\'s own commands rule untouched (no forced 4000 anywhere).'))


chapter('10','Calibration — the ladder to good prints',
  CENT(d_calib_ladder()),CAP("Every step builds on the ones before it — the Maintenance menu follows this ladder top to bottom"),
  P("Calibration only works in the right order: flow measured with a wrong E-step or unshaped motion is simply "
    "wrong. The Maintenance menu on the LCD is ordered exactly like this ladder — walk it in menu order and you "
    "walk it correctly."),
  H2('10.1 PID tuning (Maintenance > PID Tuning)'),
  P("First — everything temperature-dependent needs stable heaters. Hotend at print temp WITH the part fan "
    "percent it will actually run (own submenu), then bed. PID_TUNE_HOTEND FAN=... / PID_TUNE_BED."),
  H2('10.2 Leveling (Maintenance > Leveling)'),
  P("Probe Z offset by the paper method: TESTZ +-0.04/+-0.12, accept, SAVE_CONFIG. Bed screws: turn per the "
    "console report. This is what makes layer 1 look right — before any material calibration."),
  H2('10.3 Bed mesh (Maintenance > Bed Mesh)'),
  P("A fresh adaptive mesh runs at EVERY print start (at bed temp, over the real objects — details in ch. 11). "
    "Here: profiles, adaptive, travel cap, Level old files."),
  H2('10.4 Extruder steps (Maintenance > Extruder Cal.)'),
  P("Mark 120 mm, extrude 100, enter the rest — the calculator sets the rotation distance. Before flow and PA: "
    "both assume the extruder moves exactly what it is told."),
  H2('10.5 Input shaper (Maintenance > Vibration Cal.)'),
  P("The motion foundation. Calibrate X / Y / X+Y (frequency range and max smoothing editable), then close the "
    "loop as easily as PA calibration: <b>Diagram (print)</b> or <b>(plot)</b> builds a plate per axis with the "
    "PSD curve, all 5 shaper response curves and the SHAPER TABLE (recommended shaper boxed, marked OK) — read "
    "the table on the paper, <b>Apply result > X/Y > shaper</b> (the stored frequency is applied and saved as "
    "boot override — printer.cfg untouched). Console: SHAPER_RESULT, SHAPER_RESULT AXIS=X TYPE=MZV, "
    "TYPE=EI FREQ=58. Recalibrate after mechanical changes; the status line shows the active shapers."),
  H2('10.6 Temperature tower (Maintenance > Temp Tower)'),
  P("Per material, FIRST. Band control on a sliced tower (Start/End/Step/Band, Plan = calculate, works with "
    "marked AND legacy files) or the GENERATED standalone tower (blocks x BLOCK_HEIGHT, one temperature per "
    "block via SET_HEATER_TEMPERATURE, fan percent, mesh + prime included). Best block = that temperature "
    "becomes the hotend override (L1+L2, ON)."),
  H2('10.7 Pressure advance (Maintenance > PA Cal.)'),
  P("The Orca-style line test, generated on the printer — all parameters editable (temp/bed/start/step/lines/"
    "len/slow/fast/accel/layer/spacing + velocity, cruise ratio, corner, retraction, flow — synced with "
    "Pre-Print/Live). Mesh first; Best line = the PA override. <b>PA Smooth Cal.</b> (own submenu): smooth time "
    "0.020–0.200 s in 0.010 steps, PA prefilled + editable — Best line = smooth override ON."),
  H2('10.8 Flow (Maintenance > Flow Cal.)'),
  P("Print cube GENERATES the single-wall cube — SIZE/HEIGHT/LAYER/FLOW percent (FLOW percent baked into E, "
    "independent of the flow override), mesh + prime + your motion values included. Measure the wall, Wall: "
    "value GO = suggested flow percent, Apply flow (override ON)."),
  H2('10.9 Retraction (Maintenance > Retract Tower)'),
  P("GENERATED two-mast tower, the retract length rises block by block with slicer-style G1 E- retracts. Params: "
    "START/STEP/BLOCK/BLOCKS/DIST/TOWER/RETRACT_SPEED/LAYER/SPEED/TRAVEL_SPEED + temps. Best = retract override ON."),
  H2('10.10 Bridging (Maintenance > Bridging)'),
  P("GENERATED test: LEN (default 160 mm) + a SHORT span at 10–50 percent of it hanging clearly BELOW the long "
    "bridge on its own lower tower — inspect both sags from the side. Every parameter live: Live Tuning > "
    "Features > BRIDGE (speed percent), fan, flow. Every tower and bridge is an exclude object."),
  H2('10.11 Ironing card (Maintenance > Ironing Cal.)'),
  P("CARDS cards (1–6, sizes auto-fit), each on BASE base layers — ironing starts on layer BASE+1 (like a real "
    "top surface). Each card = one flow/speed pair (F10/S20 to F20/S40; cards 4–6 via console F4/S4 to F6/S6). "
    "Best = ironing speed + flow overrides ON."),
  H2('10.12 The per-material recipe'),
  P("1) temperature tower, 2) pressure advance, 3) PA smooth time, 4) flow, 5) retraction, 6) bridging, "
    "7) ironing card, <b>Save as preset</b> (a preset stores pa_smooth + unretract speed too). Print a small "
    "model of the material real use case between steps — the generators make that cheap."))


chapter('11','Bed mesh &amp; KAMP',
  CENT(d_mesh()),CAP('Dispatch: KAMP → native adaptive → full bed — always saved as profile r2'),
  *B('one profile r2 for everything; adaptive when the file has labeled objects (margin 5)',
     'Mesh mode (tri-state): ON (default) = fresh mesh at every start, at bed temperature · AUTO = keep whatever is loaded (calibrate only if none) · OFF = no meshing at all — the loaded mesh simply stays',
     '"Level old files" ON (default): legacy files also get mesh + purge at their start (OFF = only home + purge)',
     'Unload mesh: clear + re-level next time (nothing deleted) · Save as 60C: name = bed temperature',
     'Load…/Delete… (2×): live profile list · "Save after print" ON = auto SAVE_CONFIG after the print',
     'KAMP toggles (Maintenance &gt; KAMP): mesh · purge LINE/VORON · smart park — politely say "not installed" otherwise',
     '<b>Adaptive BEFORE the print :</b> the start flow holds the file at position 0 — its object definitions have not run yet, so the watcher replays them at selection: KAMP meshes the real object area, not the full bed',
     '<b>Travel cap :</b> mesh moves are capped (default 120 mm/s, Pre-Print &gt; Bed Mesh &gt; Travel cap) and the limit is restored afterwards — the mesh phase used to be the fastest continuous motion of the whole print (Timer-too-close hardening)',
     '<b>Host check :</b> System &gt; Host check shows undervoltage/throttle flags, CPU temp, load, RAM, disk'))


chapter('12','Purge / prime line',
  CENT(d_prime()),CAP('Only X — starts right, drawn toward x=0; nozzle AND probe stay on the bed'),
  *B('<b>Nozzle wipe first (since then):</b> every purge chain heats (180C if cold) + zigzag-wipes the pad '
     'X0-13/Y0-13 at max Z4, then parks HIGH before the line/logo is drawn',
     '<b>1) Flush 6 mm</b> (E F150) after a 3 s heat soak — refills the molten pocket, presses debris out',
     '<b>2) Fat line</b> up to 110 mm, 1.2 mm wide (E from layer height) at F1200 — visible, wipes the nozzle',
     '<b>3) De-ooze handover</b> (field log): retract −3.5 mm + slow push-back +3.0 mm = net −0.5 mm held back — nothing drips on the way to the part, the file\'s first extrusion fills the rest invisibly',
     'part fan OFF after every purge — a cool-down fan from the PREVIOUS print (100% for 30 s) can no longer bleed into the new first layer',
     'placement : LONGEST option wins — front strip 10 mm below the objects, left or right of them,',
     'never over them (field log: 56 mm beside vs 110 mm in front)',
     'runs in EVERY start path — marked files, legacy prep (Old files ON), legacy home (OFF), AS LEGACY',
     'KAMP purge (LINE/VORON) replaces it when installed + enabled — but the LINE purge is NOT probe-offset aware: '
     'skipped automatically with a side offset &gt; 10 mm (our probe-safe line runs instead)',
     'edit spots: 08 _PRIME_LINE (flush, width, length, margin) + _PROBE_STOW (dock hook)'),
  P('<b>Probe-safe geometry (since then, after a field crash):</b> the line runs along X, STARTS at the RIGHT end and '
    'is drawn toward x=0; Y only ever increases. The [probe] x_offset/y_offset is respected — nozzle AND probe stay '
    'inside the bed with a 5 mm margin, so a side-mounted probe can no longer slam into the bed frame at the line '
    'start. _PROBE_STOW runs before every purge: BLTouch/CR-Touch need nothing (Klipper stows the pin itself), '
    'Klicky/Euclid users simply uncomment their DOCK_PROBE in that hook.'))


chapter('13','Maintenance &amp; care',
  P("The care side of the Maintenance menu — after the calibration ladder follow the care entries."),
  *B('<b>Clean Nozzle</b> — heats to 180 C, zigzag wipe on the silicone pad, parks high. Runs in every purge '
     'chain automatically',
     '<b>Filament</b> — load/unload/change + <b>cold pull</b>: heat, advance fresh filament, cool below the '
     'softening point, pull — the classic fix for partial clogs and stringing after a material change',
     '<b>Z Gantry Sync</b> — re-syncs both Z motors to a common zero; after mechanical work or a visibly tilted gantry',
     '<b>KAMP</b> — mesh/purge/smart-park settings (ch. 11)',
     '<b>Tests</b> — LED demo, sound demo, self test, status: verify actuators without heating anything'),
  H2('Regular checks (recommended rhythm)'),
  TBL(['When','What'],[
   ['every print','glance at layer 1 — the purge line + first perimeter tell the whole story'],
   ['weekly / ~1 kg filament','clean the nozzle, cold pull if stringing increases, check the bed for residue'],
   ['monthly','belt tension (ping test), V-roller play, PTFE tube seat at the hotend, gantry screws'],
   ['after mechanical changes','re-run the ladder from step 5 (shaper) — steps 1–2 if hotend/bed moved'],
   ['after a heater/fan change','PID tuning again'],
  ],[46*mm,114*mm]))


chapter('14','LCD menu reference',
  CENT(d_menu()),CAP('Seven top groups in LCD order — Start Print? (waiting), Live Tuning (printing), then Pre-Print, Quick Macros, Tools (the part generators: Cable ties · Angles+Flat · Lithophane · ColorPic · Gaskets · Frames · Labels · Bricks (catalog, kit, figures) · Plotter), Maintenance, System'),
  P('Every line fits the 16 characters of the 12864 display — the value you edit is always visible '
    '(test-enforced). Pattern: first line = ON/OFF toggle (value stays stored), then the values.'),
  TBL(['Live Tuning (during print)','Contents'],[
   ['Z +0.04 / +0.12 / −0.04 / −0.12','babystepping right at the top'],
   ['Hot / Bed / Fan / Zoff','cockpit: temperatures, fan %, Z-offset display — one click deep'],
   ['Speeds','Global % (THE overall regulator,) + Cur: currently printing feature % + CurOv: its ON switch + Src info'],
   ['Accels','Global mm/s² + CurAcc: the currently printing feature\'s accel '],
   ['Features','16 submenus = Pre-Print > Features LIVE: edits re-apply immediately when that feature prints'],
   ['File (G-code)','FULL mirror of the Pre-Print file info : measured originals per feature, 16 activators, temps, PA, retraction, fan, flow'],
   ['Extrusion','Flow 1–300, PA, PA smooth, RetLen/RetSpd/Unret, Ironing flow — every input shows what Klipper REALLY runs + Src info '],
   ['Velocity','max velocity · minimum cruise ratio · square corner — live, like Mainsail'],
   ['File (G-code)','what the file asks for: type, material, layers, L1/L2 temps, PA, retract, fan F, flow Fl, accel A'],
   ['Pause &amp; Control','pause now / next layer / at layer / Stop@ (planned NORMAL end) / M600 / cancel (2×)'],
   ['Objects','skip single objects (2× confirm)'],
  ],[56*mm,108*mm]),
  TBL(['Pre-Print','Contents'],[
   ['File (G-code)','full slicer summary + MEASURED per-feature originals (post-processor v4): speeds/accels straight from the g-code, temps, PA, retraction, sliced-by slicer + firmware flavor (volumetric warning) — PLUS 16 activator rows (OW..BM + OH/IB/PT/CU): real file speed + o:ON; CLICK toggles (absent features: n/a, refuse)'],
   ['Material','LOAD NOW + 11 values + Save as preset — edits of the ACTIVE material apply LIVE too '],
   ['Features','16 submenus : each shows the file\'s ORIGINAL (File:) + own ON switch + speed % (× global) + accel; only features in the file are editable (n/a guard); OFF resets to the original — never touches the global values'],
   ['Temperatures','Bed L1/L2, Hotend L1/L2, Fan L2 (ON/OFF each) + File H:215/210C / File B:60/55C = the file\'s own values'],
   ['Motion','PA (+smooth), retraction len/spd/unretract, Accel + Vel + MCR + Corner (ON/OFF each) + File R:len/speed'],
   ['Flow / 1st layer','global flow (1–300 %) · first-layer speed % (0 = off, default 75)'],
   ['Bed Mesh','Level old files ON/OFF · Mesh ON/AUTO/OFF · Save after · Adaptive · Travel cap (mm/s while meshing, 0 = off) · Calibrate now · Load… / Delete… (2×)'],
   ['Range/Stop','Stop@ + From/To (capped to the file) + Floor/Top (FOOTPRINT or OUTLINE, GRID or SOLID) + Brim + Vers (shared V01-V09) + Create - builds 00_src_La-b_V01.gcode, same name overwrites, ends with a proper PRINT_END '],
   ['Defaults','Save the current settings as Default 1-8 (lowest free slot, never overwrites) + Load + Delete '],
   ['Preheat','ON/OFF + nozzle/bed standby levels - preheats the moment you select a file '],
  ],[42*mm,122*mm]),
  TBL(['Labels (in Tools)','Contents'],[
   ['Text','L1-L5 pickers (up to 5 lines per label) · Show text · Pos 1-N (N = character limit of the label size) · Chr (A-Z a-z 0-9 space ÄÖÜäöüß + symbols) · Delete char · Clear text'],
   ['Settings','W/H · Font SMOOTH/MONO/COND/NARROW/CAPS · Lines 1-5 · Size (cap mm, 0=auto) · Spc · Stroke · Vers V01-V09 · Preview fit? (real numbers incl. growth) · Base/Text layers · LH · 1st · Ironing · Hole · Brim · 2 colors · Gap'],
   ['Job','Queue n/24 · Add label · Del last · Clear all (2×) · Create (beeps, watcher builds the file) · Fit (how many fit the bed)'],
  ],[42*mm,122*mm]),
  TBL(['Cable ties (in Tools — ch. 5.4)','Contents'],[
   ['Info','every setting in one console listing + material tip'],
   ['Settings','Count 1-24 · Len 50-300 mm · Width 2-12 mm · Layers 3-6 · LH 0.12-0.32 · Closure CLASSIC/LOOP (the * marks the active) · Brim · Vers V01-V09'],
   ['Info | Images (Create) | Delete image | Settings | How it works','LITHOPHANE (ch. 5.6): the gcodes folder\'s .png/.jpg list (newest first, 10 slots; plotter uploads included) — slot press = Create; Delete = 2-press confirm (plotter .gcode stays); Height 30-200 · Layer 0.08-0.2 · Levels 0-12 (0 = photo) · Frame · Brim 0-10 · Ironing · Vers'],
   ['Info | Settings | Create (beeps) | How it works','GASKETS (ch. 5.7): OD 12-200 · ID 6-190 · Height 0.4-6 · Face FLAT/NUT (groove + two sealing lips) · Ironing · LH · Vers'],
   ['Info | Settings | Create (beeps) | How it works','FRAMES (ch. 5.8): Preset or W/H 40-230 · Depth 3-60 · Border 4-30 · Corner r · RECT/OVAL · Closure BACK/SIDE · Hang 4 sides/OFF · Stand · Ironing · Infill'],
   ['Create (beeps)','validates, bumps the job counter — the watcher builds the file in the background, beeps + auto-selects'],
   ['How it works','the flow + PETG/TPU tip + the Mainsail one-liner on the LCD'],
  ],[42*mm,122*mm]),
  TBL(['Angles+Flat (in Tools — ch. 5.5)','Contents'],[
   ['Info','every setting + the auto-hole rules'],
   ['Mode','Angle (L) / Flat splice — the * marks the active mode'],
   ['Settings','Angle 30-170° (HIDDEN in Flat mode) · Leg A/B 20-150 (Left/Right in Flat mode) · Width 8-60 · Layers 4-12 · LH · Holes 0-6 · Hole D 2-10 (auto-clamped) · Countersunk/Normal · Rib None/Gusset/Stepped (hidden in Flat) · Walls 1-6 · Infill 20-100% · Ironing on/off · Count 1-12 · Vers'],
   ['Create (beeps)','validates, bumps the job counter — ready in ~1-2 s with the full adjustment report'],
  ],[42*mm,122*mm]),
  TBL(['Maintenance (calibration order!)','Contents'],[
   ['Clean Nozzle','heat 180C + zigzag pad wipe X0-13/Y0-13, Z<=4, parks high; in every purge '],
   ['Vibration Cal.','input shaper measurement (ISHAPER.md) + Diagram (print/plot) + Apply result '],
   ['Bridging','long diagonal bridge + short one below, all parameters '],
   ['Leveling','bed screws + Z-offset (TESTZ ±0.04/±0) + probe offset'],
   ['Bed Mesh','status, calibrate now, save as 60C, unload, load…/delete…'],
   ['Extruder Cal.','rotation distance via 120 mm mark method'],
   ['PID Tuning','Hotend PID (with own fan %) + Bed PID as submenus'],
   ['PA Cal.','line test, mesh FIRST, all parameters editable, "Best line" → PA override (ch. 10)'],
   ['PA Smooth Cal.','smooth-time line test 0.004–0.020 with YOUR PA, "Best sm. ln" → override ON '],
   ['Flow Cal.','Print cube (generated,) + measure + calculator + Apply (ch. 10)'],
   ['Temp Tower','band plan for real files + GENERATED standalone tower + Best '],
   ['Ironing Cal.','CARDS cards x (flow%/speed) on BASE base layers, sizes auto-fit, Best → overrides '],
   ['Retract Tower','two masts, retract rises per block, Best → retract override '],
   ['Plotter (in Tools)','DRAW/DOTS, dot gap, pen offset X/Y/Z, scale X/Y% (bed-capped), corners, frame test, extruder on/off, Fil Z , auto-contrast, Z/speeds '],
   ['Filament','load 60 / unload 90 mm (LCD-settable), M600 change, retraction test - ALSO in Pre-Print and while paused ; cold pull = Maintenance only (wizard: material presets, beep countdown, extruder assist)'],
   ['Z Gantry Sync','run now + boot/print toggles'],['KAMP','mesh/purge/smart-park toggles (when installed)'],
   ['Tests','sound demo, LED demo, self test'],
  ],[52*mm,112*mm]),
  P('<b>Macros:</b> load/unload, gantry sync / z tilt, status, sounds on/off, LEDs on/off, Nozzle LED (AUTO/ON/OFF + live brightness/color). <b>System:</b> LED Setup (areas, ch. 17 - only with LED hardware), restarts (2×), '
    'Pi shutdown (2×), Force end print, save config (2×, dark-LCD warning), status.'))


chapter('15','Overrides reference',
  P('Every override = value + OWN ON switch. SET_OVERRIDE_VALUE sets + switches ON · TOGGLE_OVERRIDE flips · '
    'CLEAR_OVERRIDES switches all off (values stay stored). Only ON applies — SHOW_STATUS lists exactly the active ones.'),
  TBL(['Group','Keys','Defaults','Applied'],[
   ['Temps','bed, bed_after, hotend_first, hotend_after','60/55 · 225/210 e.g.','start + intercepted M104/109/140/190 (by layer)'],
   ['PA','pa, pa_smooth','0.05 · 0.04','from purge on; SET_PRESSURE_ADVANCE redirected'],
   ['Retraction','retract_len, retract_speed, unretract_speed','0.75 · 35 · 35','from purge on; per-key redirect'],
   ['Machine limits','accel, velocity, min_cruise, square_corner','4000 · 300 · 0.5 · 5 (all OFF)','start, ONLY when ON + value > 0'],
   ['Flow / Fan','flow, fan','100 · 100','flow global (M221) · fan scaled from the START : the file\'s M106 S0 stays 0, everything else scales by your %'],
  ],[24*mm,58*mm,28*mm,54*mm]),
  P('The interceptors remember what the FILE asked for — file_hotend_first/after, file_bed/after, '
    'file_retract_len/speed, file_fan, file_flow, file_accel, file_speed — shown as "File H:215/210C", '
    '"File B:60/55C", "File R:0.8/35", "File F/Fl/A" hints in the menus (0 = not seen yet). M221 (flow), '
    'M204 (accel) and M220 (speed) are intercepted too: your overwrites win when ON, otherwise the file '
    'value passes 1:1 (since then).'))


chapter('16','Sound reference',
  P('20 tunes, played as frequency:ms:volume triples (M300-based, pwm beeper). PLAY_SOUND NAME=… · TOGGLE_SOUNDS '
    'on/off · TEST_SOUNDS plays them all (Maintenance &gt; Tests).'),
  TBL(['Group','Tunes'],[
   ['UI / dialogs','r2_click (menu ticks) · r2_confirm · r2_notice · r2_question (start dialog, repeats) · r2_pause · r2_resume'],
   ['Start stages','r2_start · r2_leveling · r2_heating · r2_hot (reached) · r2_printing (go!) · r2_leveled'],
   ['Tuning','r2_pid · r2_leveling'],
   ['Filament','r2_filament (change/runout, repeats) · r2_alarm'],
   ['Endings','r2_done (fanfare) · r2_sad (cancel) · r2_error (siren) · r2_happy'],
  ],[30*mm,134*mm]),
  P('Volume lives inside the tune triples (0.05-0.5 duty): soft ticks ~0, mid ~0, alarms/fanfares 0.45-0.5. '
    'Edit or add tunes in 02_sounds.cfg — 0 Hz = a pure pause.'))


chapter('17','LED reference',
  CENT(d_led()),CAP('12 states + the volume scale — full demo: Maintenance &gt; Tests &gt; LED demo'),
  TBL(['State','Pattern','When'],[
   ['idle','calm blue breathing','ready, heaters cold'],['boot','blue/white scanner','system start'],
   ['waiting','blue/white blink','start dialog waits for you'],['heating','red/orange chase','heaters ramping'],
   ['homing','fast cyan scanner','G28 running'],['leveling','magenta scanner eye','mesh/screws/offset'],
   ['pid','blue/white blink','PID tuning'],['printing','moving blue wave + nozzle light','file running'],
   ['paused','yellow breathing','any pause'],['filament','cyan/white chase','load/change/runout'],
   ['alarm','red/white strobe','errors, cold pull PULL NOW'],['finished','green/white twinkle','print done'],
  ],[30*mm,66*mm,68*mm]),
  P('Effects come from the klipper-led_effect extension; frame chain = [neopixel printer_leds] 1-4, nozzle light = LED 5. '
    'TOGGLE_LEDS switches the FRAME off/on (sounds keep playing). After a finished print the celebration runs for '
    'led_finish_time seconds (default 10) and returns to idle BY ITSELF — it used to twinkle forever.'),
  H2('Nozzle LED — its own switch'),
  TBL(['Mode','Meaning'],[
   ['AUTO (default)','work light while printing / filament change (r2_nozzle_on)'],
   ['ON','always on with YOUR color + brightness — tool light, stays available even with the frame LEDs OFF'],
   ['OFF','never'],
  ],[35*mm,129*mm]),
  *B('LCD: Quick Macros &gt; Nozzle LED — &gt; AUTO (print) / &gt; ON / &gt; OFF (active mode gets the &gt; marker),',
     'live inputs Bright 5-100% · Red/Green/Blue 0-100% · presets White + Warm — applies IMMEDIATELY, mid-print too',
     'Console/Mainsail: NOZZLE_LED (status) · MODE=on|off|auto · BRIGHT=0.4 · R=1 G=0.85 B=0.6 · SHOW_STATUS lists all',
     'POWER RULE: color × brightness is hard-capped at 0.5 per channel — the neopixel port stays safe'),
  H2('LED areas — status / bed light / nozzle (R108)'),
  P('One chain, three jobs — the split is YOUR choice (e.g. 3 status + 4 bed lighting + 1 nozzle). It lives in the '
    'hardware profile r2_hardware.cfg (ch. 19b) — the second variables file that survives deleting variables.cfg.'),
  TBL(['Area','LEDs','What it does'],[
   ['Status','1 … led_status_n','the animated effects above (frame lighting)'],
   ['Bed light','next led_bed_n','steady WHITE work light, own ON/OFF + brightness 0-0.5'],
   ['Nozzle','last of the chain — or own chain (led_nozzle_split=1, e.g. EBB42 over CAN)','work light at the toolhead'],
  ],[24*mm,52*mm,88*mm]),
  *B('LCD: System &gt; LED Setup — info (LED_INFO: pin, chain, areas) · master on/off · Status/Bed LEDs count inputs '
     '(hard-clamped to the real chain_count) · bed light on/off + brightness % · nozzle main/own chain · nozzle mode · hardware info',
     'Console: LED_INFO · SET_LED_LAYOUT STATUS=3 BED=4 · SET_BED_LIGHT STATE=1|0 TOGGLE=1 BRIGHT=0..0.5',
     'LCD edits apply IMMEDIATELY and persist into r2_hardware.cfg ([gcode_shell_command R2_PERSIST] — setup.sh adds it '
     'when the shell-command extension is installed; without it the edit holds for the session)',
     'The animated [led_effect] ranges are static Klipper config — changing the status count regenerates them '
     '(tools/r2_persist.sh), one FIRMWARE_RESTART applies; bed light + nozzle index are live right away',
     'Other SET_LED-compatible chains work too: the wizard writes [neopixel] or [dotstar] (data + clock pin) sections'))


chapter('18','Console messages',
  CODE('[OK] success [i] info [!] warning !! error'),
  *B('RESPOND lines carry these prefixes in Mainsail; M117 mirrors the essence onto the LCD',
     'temperature redirects log BOTH values: M104: 215C -&gt; OVERWRITE -&gt; 225C (layer 1)',
     'M220 S100% capped to 65% (layer 1) — the file\'s preamble hit the L1 brake',
     'Layer 1: speed brake re-applied (65% after resume) — the resume fix at work',
     'Sequential print: next object (NAME) - back to LAYER-1 temperatures',
     'Temp tower: layer 21 -&gt; 215C — band control at work',
     'Print running (legacy file) - live tuning and overrides ACTIVE',
     'state changes, planned pauses, skips, runout — everything announces itself'))


chapter('19','System: Klipper &amp; Pi',
  TBL(['Command','Effect'],[
   ['SYS_FIRMWARE_RESTART CONFIRM=1','Klipper restart (macros reload) — 2× press'],
   ['SYS_HOST_RESTART CONFIRM=1','Klipper host service restart — 2× press'],
   ['SYS_SHUTDOWN CONFIRM=1','heaters/fans/LEDs off → Pi shutdown via moonraker (shutdown_machine)'],
   ['SYS_SAVE_CONFIG (2×)','guarded SAVE_CONFIG : refuses during a print, restarts anyway when nothing is pending (R2 settings save instantly), warns that the LCD goes DARK up to 2 min before restarting'],
   ['EMERGENCY_STOP','immediate halt (LCD System / console)'],
   ['HOST_CHECK','Pi health report: throttle/undervoltage flags (now + since boot), CPU temp, load vs. core count, RAM + swap, iowait, TOP CPU/RAM processes (top 5), swap residents BY NAME (VmSwap per process) + service states (avahi/crowsnest/sonar/OE/pigpiod) — honest verdict THROTTLED/SWAPPING/OVERLOADED/OK. LCD: System > Host check'],
   ['SET_MESH_TRAVEL SPEED=120','cap the mesh travel speed , 0 = off — the mesh phase is the fastest continuous motion of the whole print'],
   ['FILE_CHECK','g-code inventory: scans every file\'s tag version - current / old (upgradeable) / untouched (never processed) / plotter - each listed on the console with age + size. RETAG=1 (2x / CONFIRM=1) upgrades old + untouched files to the current markers: .r2bak backup first, never while printing, max 20 per run. LCD: System > File check'],
  ],[58*mm,106*mm]),
  P('All destructive paths need TWO presses (arm + confirm, 60 s window). Serial link to the Pi: UART — see ch. B.5.'),
  P("Why FILE_CHECK exists: markers (APPLY_TYPE, extended _FILE_INFO, measured per-feature speeds) grew over the "
    "versions - a file uploaded long ago prints, but the newer features (feature overrides, live preview, measured "
    "originals) stay blind to it. FILE_CHECK shows exactly which files those are, RETAG brings them up to date "
    "without a re-upload. Direct SSH variant (no Klipper needed): "
    "python3 tools/r2_postproc.py --file-check ~/printer_data/gcodes"),
  H2('19b. setup.sh / update.sh — wizards, backups, change modes (R108)'),
  P('<b>The hardware profile — a second variables file.</b> r2_hardware.cfg (next to printer.cfg, included by one line) '
    'carries everything that makes THIS printer tick: build volume (bed min/max X/Y, Z height), probe offsets, '
    'nozzle-clean (wipe) + part-presentation positions and the LED layout (ch. 17). Deliberately separate from '
    'variables.cfg: resetting your print settings can never lose machine compatibility — LCD-editable hardware values '
    '(LED areas) persist into it. HW_INFO (console / System &gt; LED Setup &gt; Hardware info) shows it at any time.'),
  *B('<b>The wizards.</b> bash klipper-e3-r2d2/setup.sh asks every hardware value in English — each entry validated '
     'AND confirmed a second time (mistakes correctable before takeover), summary + final confirmation before the '
     'profile is written. The LED wizard: LEDs at all? neopixel or dotstar · section name · pin (SKR mini E3: PA8, '
     'EBB42 CAN: EBB:PD3) · chain length · COLOR ORDER (.84: the byte order of the chip - GRB = WS2812 Neopixel, '
     'RGB = WS2811 12V, BGR = APA102 dotstar, RGBW = SK6812-with-white; asked with a plain-English explanation + '
     'validation, for the main chain AND the EBB nozzle chain; a wrong order swaps colors, it breaks nothing) · '
     'status/bed/nozzle areas · EBB split chain · bed brightness. '
     'update.sh asks FIRST whether to KEEP the current settings (default) or re-run the wizards — and re-applies the '
     'LED layout to the freshly unpacked 03_leds.cfg either way',
     '<b>Backup before anything.</b> Both scripts copy every file the run might change (printer.cfg, moonraker.conf, '
     'KAMP_Settings.cfg, r2_hardware.cfg, macros/03_leds.cfg, service unit) into r2_backups/&lt;ts&gt;-setup|-update/ '
     'and VERIFY each copy byte-identical (cmp) BEFORE a single modification — a failed verify aborts the run',
     '<b>Every change is shown first — four ways:</b> [1] automatic (lines inserted before the #*# block; your own '
     'conflicting lines only COMMENTED OUT — never deleted) · [2] commented only (# R2&gt; marker, you activate) · '
     '[3] separate txt r2_manual_changes.txt with target + position — SAFEST, your files are not touched · [4] skip',
     '<b>Object processing (moonraker):</b> current state shown + explained — ON = moonraker analyses every upload '
     'itself (files without slicer object data still get adaptive KAMP meshes + Skip Objects; fine on a strong host) · '
     'OFF = recommended on Pi Zero 2 W / Pi 3 (analysis costs RAM per upload; KAMP meshes full-bed, purge falls back '
     'to our own line). Keep / on / off — through the four modes above'))


chapter('20','Variables &amp; editing',
  H2('Hints from the macro comments (user adjustments)'),
  TBL(['Where','Hint (from the code comments)'],[
   ['01 INIT','runs 5 s after boot and fills only MISSING keys — your saved values are never overwritten'],
   ['05 presets','variable_presets are shipped defaults; your saved mat_&lt;material&gt;_&lt;key&gt; values always win — “Save as preset” makes yours permanent'],
   ['06 overrides','override ON → the temperature is redirected to YOUR value; OFF → the file value passes unchanged'],
   ['08 purge','purge ALWAYS (user rule) — the hotend heats to the LAYER-1 temperature first'],
   ['08 probe','_PROBE_STOW hook runs before every purge — dock your Klicky/Euclid probe there (uncomment DOCK_PROBE)'],
   ['08 dialog','AS LEGACY uses your selected material · AS SLICED takes the material from the file'],
   ['09 pause','idle timeout = “infinite” during a pause — Klipper must never turn heaters off mid-pause'],
   ['10 PA','with the PA override ON, a sliced-in SET_PRESSURE_ADVANCE cannot override your value'],
   ['11 gantry','your Z motors are wired in parallel on ONE driver — SYNC_GANTRY does the mechanical sync; watch the first run'],
   ['12 screws','screw positions live in [screws_tilt_adjust] in printer.cfg → ADJUST TO YOUR PRINTER'],
   ['15 objects','console users can always use Klipper’s native EXCLUDE_OBJECT as well'],
  ],[24*mm,140*mm]),
  P('Persistent settings live in ~/printer_data/variables.cfg — change them via LCD/console while Klipper runs; '
    'never edit the file while Klipper is running. Runtime state lives in _STATE (fast, not persisted).'),
  TBL(['Group (save_variables)','Keys'],[
   ['Material','material, mat_* (per-material presets)'],
   ['Mesh','mesh_always, mesh_adaptive, mesh_auto_save, mesh_last_profile, legacy_level'],
   ['Print behavior','first_layer_speed (75), unload_length (90), pid_fan_percent'],
   ['Overrides','all ov_* keys + ov_*_on switches (ch. 15)'],
   ['PA calibration','pa_cal_* (temp, bed, start, step, lines, len, slow, fast, accel, layer, spacing)'],
   ['Flow / tower / ironing','flow_cal_meas/result/target · tt_start/end/step/band/active · iron_cal_temp'],
   ['Cold pull / misc','cold_pull_hot, cold_pull_pull, cooldown_fan_time, heaters_off_at_end, motors_off_at_end'],
   ['System','sound_on, leds_on, start_confirm, gantry_sync_boot/print, kamp_*, ishaper_*'],
   ['Nozzle LED','nozzle_mode (auto) · nozzle_bright (1.0) · nozzle_r/g/b (0.9/0.9/0) · led_finish_time (10 s)'],
  ],[42*mm,122*mm]),
  TBL(['File','Nice edit spots'],[
   ['05_materials.cfg','variable_presets — the shipped material defaults'],
   ['08_print_start_stop.cfg','_PRIME_LINE (flush 6 · width 1.2 · length 110 · margin 5 · direction right→x0) · _PROBE_STOW (dock hook) · waiting heights Z10/Z40'],
   ['09_pause_filament.cfg','_PARK_HEAD (corner logic · lift 5 mm · anti-ooze −3 mm)'],
   ['12_maintenance.cfg','CALIBRATE_PA + CALIBRATE_PA_SMOOTH defaults · IRONING_CAL zones (F1..F3/S1..S3) · TEMP_TOWER defaults'],
   ['02_sounds.cfg','tunes — triples freq:ms:volume (0 Hz = pause)'],
   ['03_leds.cfg','colors · patterns (breathe/blink/chase/scanner/strobe/twinkle/wave)'],
   ['01_state.cfg','variable_version · INIT defaults (fresh installs)'],
  ],[42*mm,122*mm]),
  CODE('Golden rules: single braces {…} (NEVER {{ }}) · {% … %} for logic · no {# #} inline comments\n'
       'in gcode · SAVE_VARIABLE names lowercase · True/False capitalized · keep rename_existing: lines\n'
       '(the M99xxx base commands live behind them!)'))


chapter('21','What happens when a macro executes',
  P("<b>The idea in one sentence: the printer understands its files.</b> Four building blocks: (1) a service on "
    "the Pi READS every file that lands in the gcodes folder — layer comments, ;TYPE: feature comments, slicer "
    "header, object definitions, temperatures, speeds; (2) it TAGS the file — ; R2-POSTPROC v4, a _FILE_INFO "
    "parameter block, LAYER_MARK before every layer, APPLY_TYPE after every ;TYPE:; (3) the markers carry "
    "FEATURE knowledge — selecting the file replays _FILE_INFO into the preview, volumetric Marlin files get "
    "flagged; (4) during the print the markers TRIGGER macros: LAYER_MARK counts layers (layer 2 = L2 temps, "
    "fan back, full speed), APPLY_TYPE switches the live overrides to the feature printing right now, "
    "PRINT_START/PRINT_END run the choreography. File NAMES are triggers too (photo.png.gcode → pen plot) and "
    "the nonce counters trigger the five generators of chapter 5. Nothing is baked in: AS SLICED runs the file "
    "1:1, every automatic rule is a switch."),
  H2('21.1 Execution mechanics'),
  *B('<b>1 Render before execute:</b> Klipper evaluates the whole template FIRST, then runs plain gcode — a macro '
     'cannot see values it just set. Verification phases run as delayed_gcode (_LEGACY_PREP2 1.5 s, _OBJECT_PREP 2 s) '
     'and render FRESH.',
     '<b>2 rename_existing interception:</b> M104/M106/M140/M190/M204/M220/SET_PRESSURE_ADVANCE/SET_RETRACTION are '
     'OUR macros; the real commands live on as M99104 … M99220 and receive the redirected values.',
     '<b>3 delayed_gcode</b> = "run once in N seconds". _STATE_WATCHER re-schedules every second; LED frames '
     'come from the led_effect extension.',
     '<b>4 State lives twice:</b> fast runtime state in _STATE variables · persistent settings in save_variables.',
     '<b>5 {action_…} calls</b> become host actions — the Pi shutdown is literally moonraker\'s method.',
     '<b>6 Errors abort the chain</b> — risky sequences are split into phases: a hard error in phase 1 cannot kill '
     'phase 2; it just never runs. Look ABOVE in the console for the first real error.'))


chapter('22','Troubleshooting',
  P('Diagnostics: SHOW_STATUS · SELF_TEST · HOST_CHECK (Pi health) · _CHECK_INSTALL (boot) · Maintenance &gt; Tests.'),
  TBL(['Symptom','Cause → fix'],[
   ['Must home axis first','real error is ABOVE in the console'],
   ['L1 speed off (legacy)','file M220 S100 — capped, re-asserted after resume'],
   ['L2 never after obj change','frozen layer counter — fixed (Z re-anchors)'],
   ['Purge line came out empty','heat soak + wait since then; check tension/clog'],
   ['Values "not applied"','override OFF or 0 — or AS SLICED (SHOW_STATUS)'],
   ['LCD value invisible','fixed — labels ≤ 16 characters (test-enforced)'],
   ['Retraction LCD stale','live mirror since then'],
   ['Accel changed unasked','old forced 4000 — now only ON + value > 0'],
   ['Probe samples > tol.','dirty point → clean bed; samples_tolerance 0.15'],
   ['Unknown profile r2','mesh was session-only → "Save after print" ON'],
   ['VARIABLE upper case','ancient version → upload the complete package'],
   ['LCD entries missing/mixed','old lcd_menues.cfg → upload the complete folder'],
   ['No sounds','[pwm_cycle_time beeper] missing · TOGGLE_SOUNDS off?'],
   ['Pi shutdown does nothing','moonraker not reachable — SYS_SHUTDOWN logs clearly'],
   ['Probe hit the bed edge','probe-safe line since then; KAMP LINE skipped (offset &gt; 10 mm)'],
   ['"Cruise ratio not applied"','it IS passed (SET_VELOCITY_LIMIT) — console confirms since then'],
   ['SYNC_GANTRY: force_move','[force_move] enable_force_move: True in printer.cfg'],
   ['MCU "Timer too close"','ALWAYS a host problem. Host check names it: THROTTLED = PSU/USB cable or heat · OVERLOADED = load >= cores (Top-CPU list shows who: crowsnest/sonar/OctoEverywhere/moonraker object processing are the usual Pi-Zero eaters) · SWAPPING = RAM full · after boot wait ~2 min before printing (boot-time folder re-scan). hardening: mesh travels capped, preview pushes = zero disk writes, adaptive meshes'],
   ['Mesh is full bed although "adaptive"',' says so honestly ("no object data"). Since then the mesh before a held file is adaptive: the watcher replays the file\'s EXCLUDE_OBJECT_DEFINE at selection; Orca files carry them ("Label objects" on); plot/label/bridge files bring their own polygon'],
   ['KAMP meshes the whole bed','check KAMP_Settings.cfg margin — AND the file needs object data (row above)'],
   ['Dialog/menus "did nothing"','fixed (waiter); dead watcher: WATCHDOG'],

   ['Pause + L1 mid-object','z-hops ≤1 mm ignored, zone &lt;0.75 mm '],
   ['Hotend oozing during mesh','AS LEGACY standby 170C, re-heats '],
   ['Movement file / ran early','fixed: M25 hold at 0; probe -> home+heat+purge'],
   ['switch_sensor not valid','SET_FILAMENT_SENSOR takes the SECTION name (ch. 7,)'],
   ['"Save config froze the printer"','NOT a crash by design: SAVE_CONFIG restarts Klipper, the LCD keeps its last image until the MCU reconnects (up to ~2 min on the Pi Zero 2).: System &gt; Save config warns first, boot beep + R2 ready confirm success. Still dark + Mainsail error after 2 min -> FIRMWARE_RESTART via Mainsail or sudo service klipper restart, then send klippy.log (never power-cycle the Pi!)'],
  ],[58*mm,106*mm]))


chapter('23','Limits &amp; known behavior',
  *B('nozzle diameter = printer.cfg truth: every generator reads [extruder] nozzle_diameter - line widths, E-per-mm and hatch spacing derive from it (fallback 0.6)',
     'sequential detection needs the previous object ≥ 1.6 mm tall (protects by-layer prints from z-hop false alarms)',
     'by-feature factors are gone : the old SET_* commands are compatibility stubs — SET_GLOBAL_SPEED / SET_GLOBAL_ACCEL / SET_FLOW_RATE are the real controls',
     '"State re-synced" after object-change resumes: cosmetic self-healing (double resume through _OBJECT_PREP)',
     'AS SLICED = no injections, but homing/mesh/prime still run BEFORE the file (start choreography, not a file change)',
     'temperature tower holds the last temperature at the end — stop it or set the preset afterwards',
     'a2d/accel_to_decel no longer exists — minimum_cruise_ratio replaced it everywhere (LCD + overrides + live)',
     '<b>R92: the real bed is NOT position_max</b> - the steppers are lifted on purpose (micro probe + mesh rides '
     'beyond the plate). Generators, prime line and park corners read [r2_postproc] in printer.cfg '
     '(bed_min_x/bed_max_x/bed_min_y/bed_max_y); without it the Ender-3 default 220x220 applies (console note)',
     'color-change purge = flat strip beside the objects (never a park-corner blob the probe could catch)'))


chapter('24','Cheat sheet: LCD paths &amp; Mainsail commands',
  H2('LCD quick paths'),
  TBL(['I want to…','LCD path'],[
   ['print with my overrides','Start Print? &gt; AS LEGACY'],['print exactly as sliced','Start Print? &gt; PRINT AS SLICED'],
   ['system takeover of a sliced file','Start Print? &gt; PRINT AS LEGACY'],['adjust Z live','Live Tuning &gt; Z +0.04/−0.04'],
   ['hotend/bed/fan/Z-offset fast','Live Tuning &gt; Hot / Bed / Fan / Zoff'],['slow everything down','Live Tuning &gt; Speeds &gt; Global'],
   ['machine limits live','Live Tuning &gt; Velocity'],['change flow/PA/retraction live','Live Tuning &gt; Extrusion'],
   ['pause at layer 17','Live Tuning &gt; Pause &amp; Control &gt; Pause@: 17'],['skip an object','Live Tuning &gt; Objects (2× confirm)'],
   ['change material preset','Pre-Print &gt; Material &gt; LOAD NOW'],['see ALL file parameters','Pre-Print / Live Tuning &gt; File (G-code)'],['compare with the file values','Pre-Print &gt; Temps &gt; File H:/File B:'],
   ['first layer slower/faster','Pre-Print &gt; 1st layer %'],['calibrate flow','Maintenance &gt; Flow Cal.'],
   ['run a temperature tower','Maintenance &gt; Temp Tower'],['test ironing','Maintenance &gt; Ironing Cal.'],
   ['print cable ties','Tools &gt; Cable ties &gt; Create (beeps)'],
   ['print building bricks','Tools &gt; Bricks &gt; Catalog (count parts) &gt; Create'],
   ['sliced file -> brick kit','Tools &gt; Bricks &gt; Kit from file &gt; CREATE kit'],
   ['print figures','Tools &gt; Bricks &gt; Figures &gt; Scale/Count &gt; CREATE figure'],
   ['print a color picture','Tools &gt; ColorPic &gt; Images - slot press, swap at every beep'],['cable/lamp hole in a range part','Pre-Print &gt; Range/Stop &gt; Fl.hole / Top hole'],
   ['printer off, Pi stays on','PRINTER_POWER_OFF (console — relay, ch. 26)'],
   ['print an angle bracket','Tools &gt; Angles+Flat &gt; Mode &gt; Angle, Settings, Create'],
   ['join two boards flush','Tools &gt; Angles+Flat &gt; Mode &gt; Flat splice, Left/Right, Create'],
   ['purge manual / cold pull','Macros &gt; Purge · Maintenance &gt; Filament'],['shutdown the Pi','System &gt; Shutdown (2×)'],
  ],[64*mm,100*mm]),
  H2('Mainsail console — the 20 you will actually use'),
  CODE('SHOW_STATUS · SET_MATERIAL MATERIAL=PLA · SET_OVERRIDE_VALUE NAME=… VALUE=… · TOGGLE_OVERRIDE NAME=…\n'
       'CLEAR_OVERRIDES · PRINT_AS_SLICED / PRINT_WITH_OVERRIDES / PRINT_AS_LEGACY\n'
       'SET_GLOBAL_SPEED · SET_GLOBAL_ACCEL · SET_LIVE_VELOCITY · SET_LIVE_MINIMUM_CRUISE_RATIO\n'
       'SET_LIVE_PRESSURE_ADVANCE · SET_LIVE_RETRACTION · SET_FLOW_RATE · SET_GLOBAL_ACCEL_PERCENT PERCENT=150\n'
       'PAUSE · RESUME · CANCEL_PRINT (2×) · PAUSE_AT_LAYER LAYER=n · SKIP_OBJECT OBJECT=name\n'
       'GEN_LABELS TEXT=\"A|B\" W=60 H=30 · GEN_CABLE_TIES COUNT=6 LENGTH=120 VARIANT=LOOP ·\n'
       'GEN_ANGLES ANGLE=90 WIDTH=25 WALLS=4 INFILL=60 IRONING=1 ·\n'
       'GEN_FRAME PRESET=10x15 DEPTH=8 CLOSURE=BACK HANG=TOP STAND=1 ·\n'
       'TEXTURE_APPLY FILE=part.gcode MODE=BUMPS PATTERN=WAVES SCALE=10 AMP=0.35 ·\n'
       'FILE_CHECK · FILE_CHECK RETAG=1 CONFIRM=1 ·\n'       'SET_LAYER_RANGE FLOOR=3 FLOOR_HOLE=15 TOP_HOLE=28 · SET_NOZZLE_SPLIT STATE=1\n'
       'CALIBRATE_PA · CALIBRATE_PA_SMOOTH · PA_SMOOTH_RESULT SEG=n · FLOW_CAL MEASURE=0.46 ·\nTEMP_TOWER_START START=200 END=230 STEP=5 BAND=10'),
  H2('Abbreviation decoder — the short codes the console, M117 and the LCD use'),
  TBL(['Code','Means','Code','Means'],[
   ['L1 / L2','layer 1 / layer 2 (temp + fan system)','PA','pressure advance'],
   ['OW / IW','outer wall / inner wall','SP / SO','sparse infill / solid infill'],
   ['TP / BT','top surface / bottom surface','BR / GP','bridge / gap fill'],
   ['SU / IR','support / ironing','SK / BM','skirt / brim'],
   ["FS_* / FA_*","file's measured speed / accel per feature",'o:ON',"that feature's override is ON"],
   ['Src:','value source: file / overwrite / live','Now:','the feature printing right now'],
   ['LH','layer height','CS','countersink (generator holes)'],
   ['Vers / V01..','generated file version','CLA / LOO','CLASSIC / LOOP closure (cable ties)'],
   ['Boss','thick wall ring around a generated hole','Bridge-first','cap layer 1 anchors the top hole edge'],
   ['Zoff','Z offset (babystepping total)','RetLen / RetSpd / Unret','retract length / speed / unretract'],
   ['MCR','minimum cruise ratio','SCV','square corner velocity'],
  ],[30*mm,54*mm,26*mm,54*mm]),
  Spacer(1,12*mm),Paragraph('Built and tested for one purpose: printing happily — with R2-D2 keeping watch. Have fun!',S['end']),
  Spacer(1,4*mm),Paragraph('R2-D2 Macro System · R2-2026-10-13.102',S['cap']))

import json as _json
_MIDX=_json.loads(r'''[["Sounds \u2014 02_sounds.cfg", [["M300", "P=100, S=1000", "single beep \u2014 wrapper; the real beep lives on as M99300"], ["PLAY_SOUND", "NAME='r2_click'", "play a tune by name (ch. 16)"], ["TOGGLE_SOUNDS", "\u2014", "sounds on/off (persisted: sound_on)"], ["TEST_SOUNDS", "\u2014", "play all 20 tunes in sequence"]]], ["LEDs \u2014 03_leds.cfg", [["SET_LED_STATE", "STATE='idle'", "switch the LED pattern (12 states, ch. 17) - applies the nozzle mode too"], ["NOZZLE_LED", "MODE, BRIGHT, R, G, B", "nozzle light: on/off/auto + live dimming + live color (ch. 17)"], ["TOGGLE_LEDS", "\u2014", "frame LEDs off/on (persisted: leds_on)"], ["TEST_LEDS", "\u2014", "LED test animation"], ["_NOZZLE_SET", "ON", "internal: writes LED 5 (color x brightness, capped 0.5)"]]], ["Notifications \u2014 04_notify.cfg", [["NOTIFY", "TEXT, LEVEL='info', LED, SOUND", "notification helper: text + sound + LED in one call"], ["SHOW_STATUS", "\u2014", "full status: mode, material, overrides, live values"]]], ["Materials \u2014 05_materials.cfg", [["SET_MATERIAL", "MATERIAL=&lt;current>, APPLY_PRESET=1", "select material; APPLY_PRESET=1 also loads its preset"], ["SAVE_MATERIAL_TEMPS", "MATERIAL=&lt;current>", "save current values as this material's preset"], ["SHOW_MATERIAL", "\u2014", "show the current material + its stored preset"]]], ["Temperatures & marks \u2014 06_temp_controls.cfg", [["M104", "S=-1, T", "hotend temp \u2014 interceptor, redirects by layer (real: M99104)"], ["M109", "S=-1, T", "like M104, but waits"], ["M140", "S=-1", "bed temp \u2014 interceptor (real: M99140)"], ["M190", "S=-1", "like M140, but waits"], ["M106", "S=255", "part fan \u2014 scaling + from-layer-2 rule"], ["M204", "P, S, T", "acceleration \u2014 interceptor (M99204): feature accel , else global overwrite ON \u2192 your accel, else file 1:1"], ["LAYER_MARK", "\u2014", "layer marker (inserted by the post-processor)"], ["M220", "S=100", "speed \u2014 interceptor (M99220): L1 cap + stores the clean global % as g_speed_clean "], ["PAUSE_NEXT_LAYER", "REASON='next layer'", "one-shot pause at the next layer boundary"], ["PAUSE_AT_LAYER", "LAYER=0", "one-shot pause at layer n (n greater than 1)"], ["SET_LIVE_HOTEND_TEMP", "T=-1", "change the hotend target live"], ["SET_LIVE_BED_TEMP", "T=-1", "change the bed target live"]]], ["Start dialog & overrides \u2014 07_start_confirm.cfg", [["PRINT_AS_SLICED", "\u2014", "start dialog: answer AS SLICED"], ["PRINT_WITH_OVERRIDES", "\u2014", "alias for AS LEGACY since then (merged mode)"], ["PRINT_AS_LEGACY", "\u2014", "start dialog: AS LEGACY"], ["CANCEL_PENDING_PRINT", "\u2014", "start dialog: cancel (nothing is hot yet)"], ["SET_OVERRIDE_VALUE", "NAME, VALUE", "set one override + switch it ON; feat_on=0 resets the values to the file original "], ["TOGGLE_OVERRIDE", "NAME=''", "flip one override switch"], ["CLEAR_OVERRIDES", "\u2014", "all switches OFF (values stay stored)"], ["TOGGLE_START_CONFIRMATION", "\u2014", "start dialog on/off (persisted: start_confirm)"]]], ["Print start & end \u2014 08_print_start_stop.cfg", [["PRINT_START", "BED, HOTEND_FIRST, HOTEND_AFTER, BED_AFTER, MATERIAL='PLA', LAYER_HEIGHT=0.2, TOTAL_LAYERS=0, OUTER_WALL_SPEED=0, SUPPORT_SPEED=0, IRONING_SPEED=0", "start choreography \u2014 called by the sliced file"], ["START_PRINT", "\u2014", "old macro name: marked = no-op / legacy = real legacy start (dialog or auto-prep,)"], ["PRINT_END", "\u2014", "end choreography: heaters/fans, stats, sound, LED -> idle, _PRINT_CLEANUP"]]], ["Pause & filament \u2014 09_pause_filament.cfg", [["PAUSE", "REASON='User'", "pause + park (mode-aware)"], ["QUICK_PAUSE", "\u2014", "alias for PAUSE"], ["RESUME", "\u2014", "the full resume sequence (ch. 6)"], ["CANCEL_PRINT", "\u2014", "1st press arms (expires 60 s, also while paused), 2nd press cancels + cleanup"], ["M600", "\u2014", "filament change (park, unload, wait for load)"], ["CHANGE_FILAMENT", "\u2014", "M600 for humans \u2014 works from idle too (heats)"], ["CHANGE_FILAMENT_RESUME", "\u2014", "internal continuation after the load"], ["PURGE_MORE", "\u2014", "purge 15 mm more (after change/resume)"], ["M0", "\u2014", "slicer pause \u2014 mapped to PAUSE"], ["M1", "\u2014", "slicer pause \u2014 mapped to PAUSE"], ["_PRINT_CLEANUP", "\u2014", "resets ALL per-print state (PRINT_END/CANCEL/watcher - settings + mesh stay)"]]], ["Live tuning \u2014 10_live_tuning.cfg", [["APPLY_TYPE", "TYPE=''", "feature switch : sets current_type + applies THIS feature\u2019s overrides (speed % × clean global, absolute accel, ironing flow)"], ["SET_OUTER_WALL_SPEED + 11 more per-feature macros", "\u2014", "per-feature setters : forward to feat_spd/feat_acc + ON \u2014 % on top of the CLEAN global"], ["SET_GLOBAL_SPEED", "PERCENT=100", "global speed % (M220 style, never capped); the running feature stays on top — re-applied immediately"], ["SET_GLOBAL_ACCEL", "ACCEL=4000", "global acceleration, mm/s\u00b2; a feature with its own accel keeps it"],
    ["SET_GLOBAL_ACCEL_PERCENT", "PERCENT=100", "scales ALL per-feature accel limits by % (10-300) in the same ratio - the global accel stays absolute"], ["SET_LIVE_VELOCITY", "VELOCITY=300", "max velocity, live"], ["SET_LIVE_MINIMUM_CRUISE_RATIO", "VALUE=0.5", "minimum cruise ratio, live"], ["SET_LIVE_SQUARE_CORNER", "VALUE=5", "square corner velocity, live"], ["SET_FLOW_RATE", "PERCENT=100", "global flow % (M221)"], ["SET_LIVE_PRESSURE_ADVANCE", "VALUE=0.045", "pressure advance, live"], ["SET_LIVE_PA_SMOOTH", "TIME=0", "PA smooth time, live"], ["SET_LIVE_RETRACTION", "LENGTH, SPEED, UNRETRACT_SPEED, EXTRA", "live retraction \u2014 one parameter, the others stay"], ["SET_RETRACTION", "RETRACT_LENGTH=0, RETRACT_SPEED=35, UNRETRACT_SPEED", "firmware retraction \u2014 interceptor, override-aware"], ["SET_PRESSURE_ADVANCE", "ADVANCE, SMOOTH_TIME", "interceptor \u2014 with the PA override ON your value wins"], ["SET_FAN_SCALE", "PERCENT=100", "fan scaling %"], ["SET_FAN_CLAMP", "ON=-1, MIN=-1, MAX=-1, BRIDGE=-1", "fan curve clamp (.85): every M106 between MIN/MAX %, BRIDGE lifts on bridges (0=off)"], ["SET_FEAT_PA", "FEATURE, PA=-1", "pressure advance for ONE feature (.85), 0=off - global PA returns after"], ["SET_FEAT_SHAPER_OFF", "FEATURE, STATE=-1", "input shaper OFF while one feature prints (.85) - freqs restored, safety net at end/cancel"], ["SET_UNRETRACT_EXTRA", "EXTRA=-1", "every unretract adds EXTRA mm (.85) - seals the dot after a travel"], ["SET_IRONING_FLOW", "PERCENT=100", "ironing-only flow override \u2014 separate from the global flow"], ["PARAM_SOURCES", "\u2014", "value provenance : file | your override | LIVE now, for every parameter \u2014 LCD: Live > Sources"], ["TOGGLE_FIRST_LAYER_RULES", "\u2014", "first-layer rules (L1/L2 temps + fan off) also in AS SLICED on/off "], ["SET_IRONING_TEMP", "T=0", "compat stub \u2014 use the temp overrides"], ["BABYSTEP_UP", "\u2014", "Z +0.04 mm live (SET_GCODE_OFFSET MOVE=1)"], ["BABYSTEP_DOWN", "\u2014", "Z --0.04 mm live"], ["BABYSTEP_UP_FINE", "\u2014", "Z +0.12 mm \u2014 quick rescue step"], ["BABYSTEP_DOWN_FINE", "\u2014", "Z --0.12 mm \u2014 quick rescue step"]]], ["Gantry \u2014 11_gantry_sync.cfg", [["SYNC_GANTRY", "FORCE=0, QUIET=0", "mechanical Z gantry sync (needs [force_move])"], ["TOGGLE_GANTRY_SYNC_BOOT", "\u2014", "sync at every boot on/off"], ["TOGGLE_GANTRY_SYNC_PRINT", "\u2014", "sync at every print start on/off"]]], ["Maintenance & calibration \u2014 12_maintenance.cfg", [["TUNE_PID", "HEATER='extruder', TARGET=210, FAN=-1, AUTOSAVE=1", "PID tune; FAN=% runs with the fan on (like printing)"], ["CALIBRATE_MESH", "\u2014", "full bed mesh now (at bed temperature)"], ["SET_MESH_TRAVEL", "SPEED=120", "cap the mesh travel speed, 0 = off "], ["HOST_CHECK", "\u2014", "Pi health report: throttle, temp, load, RAM/swap, top processes, swap residents + services "], ["LOAD_BED_MESH", "PROFILE=''", "load a mesh profile (menu list)"], ["DELETE_MESH", "PROFILE=''", "delete a profile (2x confirm)"], ["LEVEL_BED_SCREWS", "\u2014", "screw leveling with console report"], ["CALIBRATE_PROBE_OFFSET", "\u2014", "probe Z offset \u2014 paper method, TESTZ, SAVE_CONFIG"], ["CALIBRATE_EXTRUDER", "TEMP=210, MEASURED=0, STEP=''", "extruder steps: mark 120 mm, extrude 100, enter the rest"], ["TEST_RETRACTION", "\u2014", "retract/unretract pairs at temperature"], ["LOAD_FILAMENT", "LENGTH via load_length", "heat if cold + feed load_length mm (default 60, LCD 20-150;)"], ["UNLOAD_FILAMENT", "\u2014", "heat + reverse (unload_length, LCD 40-150)"], ["CALIBRATE_PA", "TEMP, BED, START, STEP, LINES, LEN, SLOW, FAST, ACCEL, LAYER, SPACING, WIDTH \u2014 all from menu/preset", "PA pattern print"], ["PA_RESULT", "SEG=0, VALUE=-1", "SEG=best line: PA computed + set live \u00b7 VALUE=... skips the math"], ["CALIBRATE_PA_SMOOTH", "START=0.004, STEP=0.001, LINES", "smooth-time pattern with YOUR PA fixed ; mesh + prime first; babystepping works"], ["PA_SMOOTH_RESULT", "SEG=n", "line n \u2192 smooth = start+(n-1)\u00b7step, set live + override ON"], ["COLD_PULL", "MATERIAL, CYCLES, HOT, PULL, RLEN, RSPD, BEEP, STEP=finish", "cold pull WIZARD : material presets, flush+mold, beep countdown, assisted pull, verify"], ["SET_COLD_PULL_MATERIAL", "MATERIAL=PLA|PETG|ABS|TPU", "cold pull preset temperatures"], ["CALIBRATE_SHAPER", "AXIS='BOTH', FREQ_START, FREQ_END, MAX_SMOOTHING, AUTOSAVE", "input shaper measurement (ADXL; ISHAPER.md)"], ["DUMP_RESONANCES", "AXIS='BOTH'", "export raw shaper data"], ["SAVE_MESH_AT_TEMP", "\u2014", "save the mesh as a bed-temp profile (e.g. r2_60C)"], ["MESH_BY_INDEX", "INDEX=-1", "load a mesh by menu index"], ["UNLOAD_MESH", "\u2014", "clear the mesh + level again next time"], ["SELF_TEST", "\u2014", "system self test \u2014 run before long prints"], ["FLOW_CAL", "MEASURE=&lt;menu>, TARGET", "wall measurement -> suggested flow %"], ["FLOW_CAL_APPLY", "\u2014", "apply the suggested flow (override ON, 50-150 % guard)"], ["TEMP_TOWER_START", "START=200, END=230, STEP=5, BAND=10", "temperature tower (marker + legacy files)"], ["TEMP_TOWER_STOP", "\u2014", "stop early (otherwise the last temperature holds)"], ["IRONING_CAL", "F1=10, F2=15, F3=20, S1=20, S2=30, S3=40, TEMP=200, BED=60, LAYER=0.2, LEN=40, WID=24, ACCEL=3000", "3-zone ironing test card"]]], ["System \u2014 13_system.cfg", [["SYS_FIRMWARE_RESTART", "CONFIRM=0", "Klipper restart (2x)"], ["SYS_HOST_RESTART", "CONFIRM=0", "host services restart (2x)"], ["SYS_SHUTDOWN", "CONFIRM=0", "heaters/fans/LEDs off, then Pi shutdown (2x)"], ["HOST_RESTART_INFO", "\u2014", "explains what a host restart does"], ["EMERGENCY_STOP", "\u2014", "immediate full halt"],
    ["FILE_CHECK", "RETAG=0, CONFIRM=0", "g-code inventory: tag version census (current/old/untouched/plotter) on console + LCD; RETAG=1 CONFIRM=1 upgrades old files (.r2bak backup, never while printing)"]]], ["KAMP \u2014 14_kamp.cfg", [["TOGGLE_KAMP_MESH", "\u2014", "KAMP adaptive mesh on/off"], ["TOGGLE_KAMP_PURGE", "\u2014", "KAMP purge on/off"], ["SET_KAMP_PURGE_TYPE", "TYPE='LINE'", "KAMP purge style: LINE or VORON"], ["TOGGLE_KAMP_SMART_PARK", "\u2014", "KAMP smart parking on/off"], ["KAMP_STATUS", "\u2014", "KAMP configuration report"]]], ["Objects \u2014 15_objects.cfg", [["SKIP_OBJECT", "NAME=''", "arm a skip for one object (2x confirm)"], ["SKIP_CURRENT_OBJECT", "\u2014", "skip the object currently printing (2x)"], ["SKIP_DISARM", "\u2014", "disarm a pending skip"], ["SHOW_OBJECTS", "\u2014", "list objects + skip state"]]]]''')
# R63: extend the index programmatically (no JSON escaping games)
for _g in _MIDX:
    if _g[0].startswith('System'):
        _g[1].insert(3, ["SYS_SAVE_CONFIG", "CONFIRM=0", "guarded SAVE_CONFIG : print guard + pending guard + dark-LCD warning (2x)"])
        _g[1].insert(4, ["FORCE_END_PRINT", "CONFIRM=0", "emergency: ALWAYS ends the print cleanly, even from a wedged state "])
_MIDX.append(["Labels — 16_labels.cfg ", [
    ["GEN_LABELS", "TEXT, W, H, FONT, BASE_LAYERS, TEXT_LAYERS, LAYER_H, FIRST_H, IRONING, HOLE, HOLE_D, BRIM, GAP, COLOR2", 'console/Mainsail label job: TEXT="A|B" W=60 H=30 HOLE=LEFT - sets everything + creates the file'],
    ["LABEL_GENERATE", "—", "create the file for the queued labels (watcher builds it)"],
    ["LABEL_ADD", "—", "append the edited text to the queue (max 24)"],
    ["LABEL_DEL_LAST", "—", "remove the last label from the queue"],
    ["LABEL_CLEAR_ALL", "CONFIRM=0", "clear the whole queue (2x)"],
    ["LABEL_SHOW_TEXT", "—", "show the edit buffer (LCD + console)"],
    ["LABEL_DEL_CHAR", "—", "delete the character at the cursor position"],
    ["LABEL_CLEAR_TEXT", "—", "clear the edit buffer"],
    ["LABEL_INFO", "—", "queue + size + font + bed-fit info"]]])
# R86.2: SET_LAYER_RANGE (08 group) + SET_NOZZLE_SPLIT (LEDs group)
for _g in _MIDX:
    if _g[0].startswith('Print start & end'):
        _g[1].append(["SET_LAYER_RANGE", "FROM, TO, FLOOR, FLOOR_SHAPE, FLOOR_FILL, TOP, TOP_SHAPE, TOP_FILL, FLOOR_HOLE, TOP_HOLE, BRIM",
                      "layer-range excerpt: raft + cap + centered floor/top holes (E14 15 / E27 28 mm presets, ch. 5.1)"])
    if _g[0].startswith('LEDs'):
        _g[1].append(["SET_NOZZLE_SPLIT", "STATE=0/1",
                      "nozzle LEDs on their own EBB42 chain (1) or LED 5 of the main chain (0) - persisted (ch. 26)"])
# R86: part generators in the index
_MIDX.append(["Part generators — 17_generator.cfg", [
    ["GEN_CABLE_TIES", "COUNT=6, LENGTH=120, WIDTH=8, LAYERS=3, VARIANT='CLASSIC', LAYER_H=0.2, BRIM=1",
     "console/Mainsail cable-tie job: COUNT=6 LENGTH=120 VARIANT=LOOP - sets everything + creates the file (CLASSIC one-way pawl, LOOP adjustable bead loop)"],
    ["LITHO_CREATE", "INDEX=0",
     "lithophane from image slot INDEX (0 = newest picture in Tools > Lithophane; big jobs run in a background thread)"],
    ["LITHO_DEL_SLOT", "INDEX=0",
     "delete image slot INDEX - 2-press logic: first call arms, the second deletes (plotter .gcode stays)"],
    ["GEN_SEAL", "OD=40, ID=20, HEIGHT=1.2, PROFILE='FLAT', IRONING=0, LAYER_H=0.2",
     "console/Mainsail gasket job: GEN_SEAL OD=30 ID=15 HEIGHT=2 PROFILE=NUT - groove + two sealing lips"],
    ["CABLE_TIE_GENERATE", "—", "create the tie file from the stored settings (watcher builds it, beeps + selects)"],
    ["CABLE_TIE_INFO", "—", "every tie setting in one listing + material tip"],
    ["LITHO_INFO", "—", "lithophane settings + how many images are ready"],
    ["SEAL_INFO", "—", "gasket settings + NUT/material tips"],
    ["SEAL_GENERATE", "—", "create the seal file from the stored settings (bumps seal_nonce)"],
    ["GEN_FRAME", "PRESET='', W=102, H=152, DEPTH=8, BORDER=12, CORNER=6, SHAPE='RECT', CLOSURE='BACK', HANG='TOP', STAND=0, IRONING=1, INFILL=60",
     "console/Mainsail frame job: bed fit checked, kit fallback, guard errors beep + show on the LCD"],
    ["FRAME_GENERATE", "—", "create the frame file from the stored settings (bumps frame_nonce)"],
    ["FRAME_INFO", "—", "every frame setting in one listing + closure explanation"],
    ["GEN_ANGLES", "COUNT=2, ANGLE=90, LEG_A=60, LEG_B=60, WIDTH=25, LAYERS=6, HOLES=2, HOLE_D=4, CS=1, STIFFENER=1, WALLS=2, INFILL=100, IRONING=0, FLAT=0, LAYER_H=0.2",
     "console/Mainsail angle/flat job: CS=1 countersunk, FLAT=1 flat connector - holes auto-arrange and auto-clamp"],
    ["ANGLE_GENERATE", "—", "create the plate file from the stored settings (watcher builds it)"],
    ["ANGLE_INFO", "—", "every angle/flat setting + the auto-hole rules"],
    ["TEXTURE_APPLY", "FILE='', MODE='OFF', THICK, DENSITY, PATTERN, SCALE, AMP, DIR='OUT'",
     "fuzzy skin / shaped bumps for the SELECTED (or FILE) g-code - new _TX_V01 file in the background, never auto-started (ch. 5.9)"]]])
# R131: building bricks / kits / figures + colorpic in the index
_MIDX.append(["Building bricks & figures — 19_bricks.cfg", [
    ["GEN_BRICKS", "CODES='B2x4:3|P2x2:2'",
     "console/Mainsail brick job: sets the queue (code:count, | separated, max 120 parts) and creates 00_Bricks_V01.gcode"],
    ["BRICK_ADD", "CODE='B2x4', COUNT=2",
     "add COUNT x CODE to the queue (same codes merge; unknown code or count outside 1-99 rejected)"],
    ["BRICK_DEL_LAST", "—", "drop the last queue entry"],
    ["BRICK_CLEAR", "CONFIRM=1", "empty the queue (2-press: first call arms)"],
    ["BRICK_SHOW", "—", "list the queue"],
    ["BRICK_INFO", "—", "settings + geometry summary"],
    ["BRICK_CREATE", "OUT=QUEUE/PREVIEW", "build the file from the queue (bumps bricks_nonce; the watcher builds, beeps + selects)"],
    ["GEN_BRICKKIT", "SRC='box.gcode', INDEX=0-4, DETAIL=AUTO/MICRO/SMALL/BIG, MODE=BY_LAYER/BY_OBJECT, COLORS=1-8",
     "sliced file -> stylized kit (SRC=LAST or empty + INDEX pick the newest jobs; without params the saved menu values win)"],
    ["GEN_FIGURES", "SCALE=25-300, COUNT=1-24",
     "figures at % scale - 5 parts each, assembly without glue; only 100% mates with the system"]]])
_MIDX.append(["Color picture — 18_colorpic.cfg", [
    ["GEN_COLORPIC", "SRC='photo.png', WIDTH=25-230, BANDS=2-8, BANDH=0.4-3, COLORS='WHT,GRY,BLK', LAYER_H, IRONING=0/1, BRIM=0-8, SWAP=0/1, CONTRAST=0/1",
     "console/Mainsail color picture: sets everything + creates (SWAP=0 prints every band without a filament change)"],
    ["COLORPIC_CREATE", "INDEX=0-9, SRC='photo.png', OUT=",
     "create from image slot INDEX / explicit SRC / the last picked lithophane image (bumps colorpic_nonce; the watcher builds, beeps + selects)"]]])
# R64: resonance diagram + bridging + plotter text/status in the index
for _g in _MIDX:
    if _g[0].startswith('Maintenance'):
        _g[1].insert(17, ["RESONANCE_DIAGRAM", "AXIS='BOTH', MODE='PRINT'", "CSV -> printed/plotted diagram: PSD + 5 shaper curves + the shaper table, winner boxed "])
        _g[1].insert(18, ["SHAPER_RESULT", "AXIS, TYPE, FREQ", "shaper calculator: show the table / apply the picked shaper live + boot override "])
        _g[1].insert(19, ["BRIDGE_TEST", "—", "build the bridging test file: long diagonal bridge + short one below on its own lower tower "])
        _g[1].insert(20, ["PLOT_TEXT", "FILE='notes.txt'", "plotter: draw a text file from the gcodes folder, one auto-fitted page "])
        _g[1].insert(21, ["PLOT_STATUS", "—", "plotter: SHOW_STATUS report on paper "])
        _g[1].insert(22, ["SET_PLOT_SPEED", "PCT=100", "live while plotting: pen speed % (M220,)"])
        _g[1].insert(23, ["SET_PLOT_PENZ", "DZ=0.05", "live: pen pressure fine tune = Z babystep "])
        _g[1].insert(24, ["SET_PLOT_SHIFT", "X=, Y=", "live: shift the whole drawing X/Y "])
        _g[1].insert(25, ["PLOT_TUNE_RESET", "—", "reset the plot start overrides (speed/Z/X/Y) to neutral "])
        _g[1].insert(26, ["_PLOT_NAME_SET_CHAR", "POS, CH", "plot text file editor: set a character (internal,)"])
        _g[1].insert(27, ["PLOT_NAME_DEL_CHAR", "—", "plot text file editor: delete a character "])
_flow29=[]
for _t,_rows in _MIDX:
    _flow29.append(H2(_t))
    _flow29.append(TBL(['Macro','Parameters (default)','What it does'],[[_n,_p,_d] for _n,_p,_d in _rows],[48*mm,56*mm,60*mm]))

chapter('25','Complete macro index — all macros with parameters', *_flow29)

chapter('26','Electronics &amp; expansion — U2C + EBB42 + Relay V1.2',
  P("One four-wire harness to the toolhead instead of a thick bundle, the printer switchable off while "
    "the Pi stays on, nozzle LEDs at the print head. All OPTIONAL — the system runs unchanged on a bare "
    "SKR Mini E3 V3. Pin data from BigTreeTech's GitHub (EBB repo, Relay V1.2 manual) and Klipper's "
    "sample-bigtreetech-ebb-canbus-v1.2.cfg."),
  CENT(d_wiring()),CAP('The whole architecture: relay in the 230V phase, Pi on its own PSU, U2C as the CAN bridge, one 4-wire harness to the EBB42'),
  H2('26.1 The architecture — and why'),
  *B('<b>Pi Zero 2 on its OWN 5V USB PSU</b> (2.5A+ headroom) — the relay kills the printer, the Pi stays. '
     'Remove the old 5V-from-SKR line (never two sources!).',
     '<b>U2C V2.1</b> on the Pi USB (powered by the Pi, stays alive) — USB to CAN, 120R jumper ON (one end of the bus).',
     '<b>EBB42 CAN V1.2.1 at the extruder stepper</b> — one 4-wire harness replaces heater + 2 fans + probe + '
     'stepper + LED cables. 120R ON (the other end) — exactly TWO terminators total.',
     '<b>Relay V1.2 in the 230V phase</b> — 10A/250VAC vs ~1.5A printer load. Control input (3.3–5V logic) from '
     'a free SKR pin held HIGH by Klipper: Klipper dead = printer OFF (fail-safe). Your DC-DC 5V module is '
     'not needed here — keep it as a spare.',
     '<b>UART stays</b> (the Pi Zero\'s only USB data port is used by the U2C) — add 10k in series with each '
     'UART line so the always-on Pi cannot phantom-power the unpowered SKR through its RX pin.'),
  H2('26.2 The cable list — EBB at the extruder stepper'),
  P("Measure along the real route (carriage, X extrusion, chain, electronics bay); proven starting points "
    "for an Ender-3 class frame:"),
  TBL(['#','Cable','From → To','Type / gauge','Length','EBB connector'],[
   ['1','24V + GND','PSU out (switched) → EBB','2× silicone 0.5mm² (20AWG)','~1.4 m','VIN terminal (polarity + fuse)'],
   ['2','CAN-H / CAN-L','U2C → EBB','twisted pair 0.14–0.25mm²','~1.4 m','4-pin CAN (H, L, GND — check BOTH silkscreens)'],
   ['3','Extruder stepper','motor → EBB','existing 4-pin, shortened','10–15 cm','motor header (TMC2209 onboard)'],
   ['4','Hotend heater','cartridge → EBB','existing silicone, shortened','15–20 cm','HE (40W = 1.7A; EBB allows 5A)'],
   ['5','Thermistor','→ EBB','existing, shortened','15–20 cm','TH0 (PA3)'],
   ['6','Hotend fan','→ EBB','existing, shortened','~15 cm','FAN (PA1), max 1A'],
   ['7','Part fan','→ EBB','existing, shortened','~20 cm','FAN (PA0), max 1A'],
   ['8','MicroProbe','→ EBB','BLTouch-style, shortened','20–25 cm','probe: PB8 signal, PB9 control/power'],
   ['9','Nozzle LEDs','strip → EBB','3-pin 5V/GND/DATA','15–20 cm','RGB (PD3), max ~15 LEDs full white'],
   ['10','Filament sensor (opt.)','→ EBB','2-pin','~20 cm','PB4 (switch) / PB3 (motion)'],
  ],[8*mm,34*mm,38*mm,38*mm,16*mm,32*mm]),
  P("Stays where it is: X endstop (stationary on the gantry — SKR), frame LEDs 1–4 (SKR neopixel port, "
    "chain_count 4 after the split), bed + Z + Y. Reuse existing cables by SHORTENING them at the toolhead "
    "end — the long run to the bay is only the 4-wire harness."),
  H2('26.3 Firmware: flashing the EBB42 (once)'),
  CODE('cd ~/klipper && make menuconfig\n'
       '  STM32 / STM32G0B1 / 8MHz crystal / CAN bus (PB0/PB1) / 1000000 baud\n'
       '  8KiB bootloader (katapult)\n'
       'make            # then DFU: USB-power jumper, RESET+BOOT, lsusb, make flash\n'
       '/etc/network/interfaces.d/can0:  bitrate 1000000   (must match the firmware!)\n'
       '~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0\n'
       'Found canbus_uuid=...   -> [mcu EBB] in printer.cfg (template: printer.cfg.example)'),
  H2('26.4 printer.cfg changes'),
  P("Move to the EBB: extruder (PD0 / !PD1 / !PD2, TMC2209 UART PA15), heater PB13, thermistor PA3, part "
    "fan PA0, hotend fan PA1, MicroProbe PB8/PB9, optional filament sensor PB4, nozzle LEDs PD3. Then: "
    "[neopixel printer_leds] chain_count 5→4, [neopixel nozzle_led] on EBB:PD3, uncomment "
    "[led_effect r2_nozzle_on_split] in 03_leds.cfg, SET_NOZZLE_SPLIT STATE=1 (once — persisted)."),
  H2('26.5 Relay V1.2 — printer OFF, Pi stays on'),
  P("Mains L through the relay to the PSU (N + PE direct). 5V_IN + GND from the SKR\'s [output_pin "
    "power_hold] (value: 1, shutdown_value: 0). The relay button = manual power-on. PRINTER_POWER_OFF "
    "(template in printer.cfg.example): refuses while printing, heaters off, pin drops. After a relay-off: "
    "button, then FIRMWARE_RESTART — the MCUs were completely off."),
  P('<b>SAFETY:</b> 230V is lethal — plug pulled, or an electrician. Never switch or interrupt PE; only L '
    'goes through the relay. Ferrules + strain relief on the mains side. Do NOT use the 10A relay on the '
    '24V side — the bed alone draws ~10A DC (arcing). The relay PCB carries live power on open pads — '
    'enclosed bay only. Termination check with everything off: CAN-H to CAN-L = ~60 ohm (two 120R).'),
  H2('26.6 NeoPixel limits at the EBB'),
  P("The EBB42 RGB port shares the board 5V rail — budget 1A total: ~15 WS2812 at full white is the hard "
    "ceiling. The system caps every channel at 0.5 anyway, so 15 LEDs run cool. More LEDs: feed the strip "
    "from its own 5V supply (common GND!), keep only DATA from the EBB."))

chapter('A','Appendix A: Installation (detailed)',
  H2('3.1 Requirements'),
  *B('Klipper + Moonraker + Mainsail (or Fluidd), path ~/printer_data/','the 15 macro modules + menus/lcd_menues.cfg',
     '[save_variables] — the memory (survives restarts)'),
  H2('3.2 printer.cfg checklist (see printer.cfg.example)'),
  TBL(['Section','Why / Notes'],[
   ['[save_variables]','ALL settings/presets live here — exact path matters'],
   ['[virtual_sdcard] [pause_resume] [display_status] [respond] [exclude_object]','infrastructure; exclude_object unlocks adaptive mesh + object skip + smart parking'],
   ['[idle_timeout] timeout: 3600','pause management saves/restores this'],
   ['[firmware_retraction]','live retraction + retraction overrides + test'],
   ['[filament_switch_sensor filament_sensor]','runout handling — NAME matters, pause_on_runout: False'],
   ['[pwm_cycle_time beeper] pin PB5','sounds — pwm_cycle_time NOT output_pin (runtime frequency!)'],
   ['[neopixel printer_leds] PA8, 5 LEDs','frame effects 1-4, nozzle light 5 — klipper-led_effect required'],
   ['[display] (st7920)','LCD menus (12864, 16 characters per line)'],
   ['[force_move] enable_force_move: True','SYNC_GANTRY needs SET_KINEMATIC_POSITION'],
   ['[screws_tilt_adjust] / [bed_mesh] + adaptive_margin: 5','leveling / meshing'],
   ['[probe] / [resonance_tester]+[adcx345]','see 3.3 / optional shaper calibration'],
  ],[62*mm,102*mm]),
  CODE('[include klipper-e3-r2d2/macros/01_state.cfg]\n... 02 .. 15 ...\n[include klipper-e3-r2d2/menus/lcd_menues.cfg]\n'
       '-- at the END of printer.cfg; macros first, menus last'),
  H2('3.3 Z-probe variants'),
  *B('Stock probe with offsets (MicroProbe !PC14, x/y offset): works 1:1',
     'BLTouch/3DTouch: [probe] with pin + offsets; samples_tolerance 0.15-0.2 against single dirty points',
     'Inductive/capacitive: same section; mind the sensing distance on PEI spring steel',
     'Klicky/Euclid: works — docking macros are yours; mesh runs via BED_MESH_CALIBRATE',
     'No probe: mesh + LEVEL_BED_SCREWS unavailable; level via [bed_screws], Z-offset by hand'),
  H2('3.4 Filament sensor variants'),
  CODE('[filament_switch_sensor filament_sensor]\nswitch_pin: !PC15 # YOUR pin\npause_on_runout: False\n'
       'runout_gcode: _FILAMENT_RUNOUT\ninsert_gcode: _FILAMENT_INSERTED'),
  *B('Motion sensors (BTT Smart) may add runout_distance: 3.0',
     'Without a sensor everything else runs fine — runout simply never triggers'),
  H2('3.5 LEDs'),P('5 LEDs on PA8 (GRBGR): 1-4 = frame effects, 5 = nozzle light. Effects come from the '
    'klipper-led_effect extension (12 states, r2_idle autostarts). The nozzle light has its OWN switch: AUTO '
    '(work light while printing) / ON (always on, your color — a tool light even with the frame LEDs OFF) / OFF, '
    'plus live dimming + color (Quick Macros &gt; Nozzle LED). More pixels / other chains: the setup LED wizard '
    'configures [neopixel]/[dotstar] + the areas for you (r2_hardware.cfg) - or edit [neopixel printer_leds] + the '
    'effects in 03_leds.cfg — POWER RULE ≤ 0.5/channel. See ch. B for the power side (external 5 V!).'))


chapter('B','Appendix B: Power &amp; electrics (SKR mini E3 v3.0, Pi, LEDs)',
  P('Voltage domains, safe supply for the Pi Zero 2 W and Neopixels, the UART serial link, multi-PSU ground rules '
    'and silent-fan mods. Based on the BTT wiring guide and BTT/community findings; verify every rail with a '
    'multimeter before connecting anything.'),
  H2('4.1 The voltage map'),
  CENT(d_power_tree()),CAP('Everything starts at one 24 V PSU. The question is only: who builds the 5 V rails?'),
  H2('4.2 What the onboard 5 V buck can (not) do'),
  *B('<b>Onboard buck of the SKR mini E3 v3.0: ~1 A max</b> (community consensus; BTT\'s wiring guide says the board '
     'is NOT capable of powering a Raspberry Pi — their UART diagram explicitly says "power it separately with 5 V").',
     'Pi Zero 2 W + 5 Neopixels from the board 5 V sits right at that limit — the instability you see matches a '
     'marginal 5 V rail (brown-out → SD corruption risk).',
     '<b>Official upgrade path:</b> the green <b>Neo-PWR1 jumper</b> selects the 5 V source — onboard buck OR the '
     'plug-in <b>BTT DCDC Mode V1.0 module</b> (MP1584, ~3 A ideal; BTT documents up to 30 Neopixel). Alternative: '
     'any good external 24V→5V buck ≥3 A from the 24 V rail.'),
  H2('4.3 Target wiring: one 24 V source, dedicated 5 V rails, one ground star'),
  CENT(d_supply_target()),CAP('Recommended: DCDC/buck from the 24 V PSU for Pi and LEDs — no second mains device, star ground stays simple'),
  CODE('MULTI-SUPPLY GOLDEN RULES\n'
       '1 Tie ALL V- (GND) of every supply/buck to ONE star point — common reference for UART + LED data\n'
       '2 NEVER parallel the +5 V (or +24 V) of two different sources — undefined currents, dead regulators\n'
       '3 SW_USB jumper on the SKR: REMOVE — stops USB-5 V fighting the board 5 V (backfeed)\n'
       '4 Fuse each 5 V rail; Pi wiring >= 24 AWG, LED wiring short + thick\n'
       '5 Measure every rail BEFORE first connect: 5.0-5.2 V, correct polarity, no shorts to GND\n'
       '6 External 5 V PSU instead of a buck? Same rules — and its housing must not bridge the DC rails'),
  H2('4.4 Powering the Pi Zero 2 W — the three options'),
  TBL(['Option','How','Verdict'],[
   ['from the SKR 5 V','5 V + GND from the board','✗ ~1 A limit is already spent — NOT recommended (that is your instability)'],
   ['USB PWR-IN (micro-USB)','5 V >= 2.5 A from the buck/PSU','✓ cleanest: own cable, keeps the Pi-side polyfuse path, no GPIO pins loaded'],
   ['GPIO pins 2 (5V) + 6 (GND)','direct into the header','✓ ok from a measured, well-regulated rail — bypasses the Pi polyfuse: only with a fused/steady source'],
  ],[44*mm,52*mm,68*mm]),
  H2('4.5 UART instead of USB (TX/RX link)'),
  CENT(d_uart()),CAP('Pi GPIO14/15 cross over to the TFT port of the SKR mini E3 v3.0 — 3 wires, no flaky USB cable'),
  CODE('# Pi: /boot/config.txt -> enable_uart=1\n'
       '# dtoverlay=disable-bt (PL011 UART on GPIO 14/15)\n'
       '# /boot/cmdline.txt -> remove: console=serial0,115200\n'
       '# (or: sudo raspi-config -> Interface -> Serial -> hardware YES, login shell NO)\n'
       '\n'
       '# Klipper MCU firmware (make menuconfig):\n'
       '# STM32 -> STM32G0B1 -> Serial (on USART2 PA3/PA2) -> bootloader 28 KiB\n'
       '\n'
       '[mcu]\nserial: /dev/ttyAMA0\nbaud: 250000\nrestart_method: command'),
  P('Flash the UART firmware once via SD card (BTT GitHub ships prebuilt images). Afterwards the USB-C port is only '
    'needed for recovery. Pin numbers: verify against the BTT pinout PDF of your board revision.'),
  H2('4.6 Neopixels safely on external 5 V'),
  CENT(d_neopixel()),CAP('The three life-insurances: 1000 µF at the first pixel, 330-470 Ω in the data line, common ground'),
  *B('<b>1000 µF electrolytic</b> across +5 V/GND at the first pixel — eats the inrush when the strip lights up',
     '<b>330-470 Ω series resistor</b> right before DIN — protects pixel 1 from data ringing',
     '<b>common ground with the SKR is mandatory</b> — otherwise the 3.3 V data has no reference and pixels glitch',
     'long wires or ghost pixels → add a 74AHCT125 level shifter (3.3 → 5 V data)',
     'your 5 pixels: worst case 5 × 60 mA = 0.3 A (full white) — a ≥3 A buck has plenty of headroom for more'),
  H2('4.7 Silent fan mods'),
  TBL(['Mod','Wiring','Notes'],[
   ['24 V silent fans','plug &amp; play into FAN0/1/2','simplest — FAN ports run at the 24 V input rail'],
   ['12 V fans (Noctua…) via buck','buck 24V→12V; fan+ from the buck, fan− into the board FAN port (low-side switched)','common ground comes free (same PSU) — verify polarity with a multimeter first'],
   ['electronics-bay fan','small fan on the electronics housing','keeps drivers + buck cool — cheap insurance for long prints'],
  ],[44*mm,66*mm,54*mm]),
  P('Hotend heatsink fan: keep it at 100% whenever the hotend is hot (the macro system already enforces this) — a '
    'slowed silent fan there buys heat-creep jams.'),
  H2('4.8 First-power-on checklist'),
  *B('buck output measured: 5.0-5.2 V BEFORE the Pi or any pixel is connected',
     'continuity: every V− lands on the star point (GND-Pi ↔ GND-SKR beeps)',
     'NO continuity between separate +5 V rails','SW_USB jumper removed, Neo-PWR1 set to your 5 V source',
     'all joints soldered + heat-shrunk; no stray strands; wires not pinched in the frame',
     'boot order: 24 V PSU → SKR → buck rails stable → Pi → LEDs'),
  H2('4.9 Where do I connect what? (quick reference)'),
  TBL(['Signal / Load','Comes from','Goes to','Watch out'],[
   ['Pi Zero 2 W, 5 V','DCDC/buck 5 V (>=2.5 A)','micro-USB PWR (best) or GPIO 2+6','GPIO path bypasses the Pi polyfuse'],
   ['Neopixels, 5 V','same buck (LED rail) or own buck','pixel 1 +5 V','1000 uF + common ground with the SKR'],
   ['Neopixel data','SKR pin PA8 (3.3 V)','330-470 Ohm -> DIN of pixel 1','74AHCT125 for long wires'],
   ['UART serial','Pi GPIO 14/15','TFT port RX/TX (crossover)','GND mandatory - verify BTT pinout'],
   ['Filament sensor','5 V + GND (SKR)','signal -> !PC15','pause_on_runout: False'],
   ['Silent fans 12 V','buck 24V->12V','fan+ from buck, fan- to FAN port','low-side switching - polarity!'],
  ],[36*mm,38*mm,48*mm,42*mm]))


chapter('C','Appendix C: First start &amp; updates',
  *B('upload the folder → includes at the end of printer.cfg → RESTART',
     'console: "Macro system OK: all 17 modules loaded and current (build R2-2026-09-07)"',
     '~10 s later: boot sound + LED animation','SHOW_STATUS → mode, material, overrides',
     'Maintenance &gt; Tests &gt; Sound demo / LED demo / Self test'),
  H2('Updating to a new build'),
  *B('upload the UPDATE zip in Mainsail into the config folder (where printer.cfg lives)',
     'SSH: bash ~/printer_data/config/klipper-e3-r2d2/update.sh — unzips the newest uploaded zip over the old folder, checks, restarts',
     'from an older release (no update.sh on the Pi yet): cd ~/printer_data/config, unzip -o <zip>, bash klipper-e3-r2d2/update.sh',
     'mixed old/new files are detected by _CHECK_INSTALL at boot — it names the stale files',
     'all settings live in variables.cfg — they survive every update (new keys migrate automatically)'),
  H2('Daily health check'),P('SELF_TEST (LEDs, sound, sensor, probe) + SHOW_STATUS before long prints.'))


chapter('D','Appendix D: Version history',
  P("Only the milestones — the full reasoning lives in SESSION_STATE.md. The manual itself describes the CURRENT "
    "system; this table is just the record."),
  TBL(['Version','Core changes'],[
      ('.93','BRICKS ROUND 2 + HARDCORE STRESS TEST (R132) - catalog 45 -> 76 codes: 9 LCD catalog groups (bricks/plates/tiles + NEW slopes S, inverted slopes I, arches A, technic/axle H+C+J+RT, round R+RP). Figures: MODE=SINGLE (one fused piece, no clutch elements) or classic PARTS, arms printed LYING (real through-tubes), COLORS 1-4 (zone colors), BRIM 0-8, COLORMODE. Bricks: COLORS 1-8, MODE, BRIM. Centered layout = general rule for ALL generators. Fix-then-reload: RetractFix/FlowCap/Travel/Vol reload the file automatically - only Start needs confirming. New tools/r140_stress.py (~41k checks) - 7 real bugs found and fixed (unbalanced Jinja in GEN_BRICKS, split TUNE_PID call, open RESPOND quote, missing M83 in bricks/figures/kit, trailing ;TYPE:Custom, kit without LAYER_MARK + non-canonical APPLY_TYPE, figures SINGLE without BRIDGE header). Analyses: sound/display portability, Web-UI on Moonraker, LCD menus on other displays (docs/). Battery: render 1601/1601, megatest 163 files, stress 41k, systemtest 221/0.'),
      ('.92','DOCUMENTATION OVERHAUL (R131) - the handbook (MD + PDF) brought up to .91/.92: OUTDATED PASSAGES REPLACED - litho FLAT (old terraced-relief text -> the step print with StepL/color swap/border/corner/contrast/purge tower), frame closure (old bayonet slide-2.5mm -> snap-in backplate + photo play; the printer-side LCD texts too), the 5.0 generator list, the chapter-5 title (13 generators). NEW: four detailed generator chapters - 5.10 bricks (geometry table, 45-code catalog), 5.11 brick kits (voxelizer, support filter, detail bands, ring walls, BY_LAYER/BY_OBJECT), 5.12 figures (5 parts, no glue, 100% system mating), 5.13 ColorPic (band principle, M600 + LED blink, purge tower, swap/contrast); menu reference, cheat sheet (+5 paths), macro index (+11 entries) - mirrored in the PDF. Battery: render 1595/1595, validator clean, systemtest 221/0.'),
      ('.91','HOTFIX (.90 boot blocker): COLORPIC_CREATE checked the image extension with the NON-EXISTENT Jinja filter endswith (a Python method, not a filter - in the package since .82, only reached the printer with the .90 update). Fixed with slicing: _cpsrc[-4:] in (png, jpg) / _cpsrc[-5:] == jpeg. Why the tests missed it: Jinja >= 3.1 compiles unknown filters silently and a render pass short-circuits on params.X is defined and ... - the R67 gate was false green. Hardened: the gate now walks the Jinja AST of all 3663 boot templates checking every filter/test name against the real tables, and the config validator got the same static rule. Proof: an injected endswith is caught by both, the fixed pattern passes, a full package sweep finds no other zombie filter. Battery: render 1595/1595 (+5 R130), validator clean, systemtest 221/0.'),
      ('.90','R118-R129: BRICKS, KITS + FIGURES + FIELD LOG: LITHO FLAT STEP PRINT - (1) BUILDING BRICKS with the exact system geometry (45-part catalog, bodies n*8-0.2 so they clamp to each other AND to originals, hollow studs, underside tubes), queue like the labels, GEN_BRICKS. (2) KIT GENERATOR: a sliced print file becomes a stylized kit - support/brim/skirt never flow in, closed bodies fill, hollow bodies become ring walls, detail AUTO/MICRO/SMALL/BIG, BY_LAYER = one color per plate = zero M600, BY_OBJECT = M600 only at color boundaries. (3) FIGURES: 5 parts, assembly without glue (arms swing, head turns) - 100% = original size AND system-true (hands grip O4.8 studs, hats sit, feet click), 25-300%. (4) FIELD LOG LITHO FLAT: the terraced relief printed wavy (nozzle dove into the picture, probe caught) - rebuilt as a STEP print: percentile stretch + contrast boost, gray levels, step 0 = the whole light area as clean layers (ironed), darkest = the contours; StepL, color change OFF/LAST/EACH, optional picture frame (square/rounded). (5) PURGE TOWER 12x12 with 15mm probe clearance prints along EVERY filament change (litho + colorpic, swap now optional) - PRIME-TOWER tagged. (6) FIELD LOG FRAME: the backplate was 2.4mm OVER the photo opening (never insertable) - snap-in now (0.3mm play + 4 wall nubs), photo opening +1.6mm play; label gap 6 -> 12mm. (7) QUICK LISTS speed/flow/accel per feature in pre-print AND live; flow cap 0.5-50 mm3/s. (8) NEW tools/systemtest.py release gate: every generator x parameter combos x shared invariants + wiring sweep. Battery: render 1590/1590, audit 77/0, megatest 144/145/0, goldens 23/23, dialects 13/13, setup-sim 10/10, systemtest 221/0.'),
      ('.89','FIELD LOG .88 ROUND 2 (R116+R117): (1) CONTINUOUS FILLS - every '
      'generator fill (first layer, bottom, sparse/solid infill, top, ironing) '
      'prints as ONE connected zigzag chain instead of single scanlines: adjacent '
      'hatch lines link with an extruded connector bead along the border - the fill '
      'fuses with the walls and prints wet-in-a-row; hole crossings and long gaps '
      'keep their retracting travel (no strings over open holes). Sliver lines and '
      'degenerate links under 0.15 mm are skipped (they would flood the MCU with '
      '400+ moves/s). (2) IRONING ANGLE = TOP ANGLE: ironing ran 90 deg off the '
      'top fill - it now follows the top surface angle (45/135, alternating per '
      'layer), flattening WITH the grain. (3) LABEL QUEUE SNAPSHOT: the first job '
      'font leaked into later jobs of the same queue (global bias) - every job now '
      'carries its full 18-field snapshot. (4) FOUR NEW FONTS: SCRIPT (Dancing '
      'Script), HAND (Caveat), PLATE (D-DIN), PIXEL (Press Start 2P) - 9 stroke '
      'fonts total. (5) SHAPER-OFF LCD: without an [input_shaper] section the menu '
      'now says ShaperOff: n/a + a NOTIFY hint instead of silence. Tests: render '
      '1442/1442 (+9 R117 chain + angle), golden re-frozen (9 range cases), audit '
      '57/0, megatest 143/164/0, dialects 13/13, setup sim 10/10.'),
      ('.88','HOTFIX (.87 field log): (1) Malformed command - Klipper cuts every line at the first ; even inside quotes, 22 console strings rebuilt + the DERIVED confidence math 0.7 now shows 70 percent (validator rule R114 guards the class). (2) START DIALOG: idle_timeout counts from the last toolhead move only - TURN_OFF_HEATERS could fire MID-DIALOG while you made Pre-Print settings; the dialog re-arms the countdown (30min floor, config value restored on every exit) + a generator takeover no longer kills the preheat. (3) FAN HOLD (Live > Temps > Hold): the fan entry only SCALED the file M106 values - dynamic slicer fan curves always won; Hold replaces them at your percent (layer-1 fan-off still wins, resets per file). (4) FEATURE PA EVERYWHERE: 16 new PA inputs in Pre-Print > Features, the inputs show the effective value (own or your global), with a global PA active every boundary states the PA it runs at. (5) FRAME first layer see-through: loading a pre-R101 preset wrote bottom-layers 0 (sparse from layer 1); now defaults to 2 + FRAME_INFO shows it. (6) PAUSE NOW hardened: was the FIRST entry of Pause & Control (encoder double-click = instant pause) - harmless entries first + two-press confirm.'),
      ('.87','HOTFIX (.86 field log): the _R2_CONFIG migration could HALT THE BOOT - column-0 comments inside the .82-era block (our own old writer emitted them) stopped the comment-out pattern, the leftover gcode: line landed in the previous section: Option gcode is not valid in section board_pins. Fixed in setup.sh + r2_setup_lib.sh: in-block comments are consumed (lookahead-guarded), the trailing newline survives (the rstrip glue bug is fixed too). New setup-sim scenario r92-config-block reproduces the EXACT field layout - proof: the old code fails its checks, the new code passes all 10 printer scenarios. Recovery for hit machines: restore printer.cfg from the verified r2_backups snapshot OR comment the orphan lines (the Weg-B snippet) - after either, update.sh is safe again'),
      ('.86','RE-TAG THE STOCK + RETRACT VERDICT (R112): tag v5 - every file tagged before .86 counts as STALE (markers fully functional, info line predates the .85/.86 keys); System > File check > RETAG (2x) upgrades them in place: same LAYER_MARK/APPLY_TYPE counts, new _FILE_INFO with MAXRATE/SEAM/CFG replay/retract verdict, .r2bak backup, 20 files per run, never during a print - the proven v1-to-v4 upgrade machinery now armed for v4 · RETRACT VERDICT (fixed/fw/FIX!/can + longest retract mm): one Ret: line in Pre-Print > File, the RetFix offer appears only for fix/can, old files show -- honestly; _PREVIEW_SET resets the verdict per selection · IRONING_SPACING finally wired (cross-check find) · LED_INFO empty bed span reads no bed light LEDs (not 5-4) · tests: megatest 143 runs/164 files (+hardcore matrix + v5/retract invariants), setup sim 9 printers (+SV06 dual-Z, CoreXZ Switchwire, hybrid coreXY), render 1409/1409 (+parameter cross-checks), golden re-frozen'),
      ('.85','FEATURE-TAGGING ROADMAP 5+6 (R111): GEOMETRY CLASSIFIER for files without ;TYPE: tags - walls per closed-loop nesting, infill per hatch spacing (3 mm threshold), bottom/top per layer position; curved paths unclassified, bridges never guessed, tagged files never classified; honest keys DERIVED=1 CONF=0.7 COVER=% · MODAL-Z layer scan (Z on travels counts, hops never fake a layer) · new measured file keys MAXRATE (mm3/s) + SEAM/SEAMN + 14 slicer-config keys replayed (LW_*, ACCEL_SOLID/FIRST/TRAVEL, FIL_DIA, TIME_SLOW, SLOW_MIN, FAN_MIN/MAX) · TWO NEW FILE FIXES: Fix flow cap (F rewritten to stay under a mm3/s cap, idempotent) + Fix travel accel (M204 wraps travel blocks) - LCD Pre-Print > File · FEATURE PRESSURE ADVANCE (per feature, profiled) · FAN CLAMP (min/max + bridge boost, Live > Temps) · INPUT SHAPER OFF per feature (freqs saved/restored, PRINT_END + cancel safety net) · UNRETRACT EXTRA · profiles carry the new keys (5th element PA; old profiles load with PA=0) · tests: tools/r111_geom_test.py (found+fixed the hatch zigzag offset bug), dialect corpus 13 families 46/46, renders 1388/1388'),
      ('.84','GENERATOR OUTPUT + PER-FILE PROFILES (R109): every generator asks what to do with its file - Tools > After gen QUEUE (select for printing; built ON a file: range/texture = replaces the selection) or PREVIEW ONLY (3-D preview, nothing queued); sticky + OUT= per run; texture, bridge test, resonance plots, plot text/status now queue properly too · PER-FILE PROFILES: every legacy-printed file remembers its pre-print + live-tuning state - post saved automatically at a successful PRINT_END (cancelled = nothing), pre only manually, auto-load on selection picks the NEWER slot, auto-save never overwrites a manual pre · Pre-Print > Profiles: Material (save without loading first) / Defaults (8 slots) / This file (pre/post + auto toggles) · ONE apply path writes values AND ON switches (fixes the old LOAD_DEFAULT_PRESET bug) · R110: setup LED wizard asks the COLOR ORDER per chain (GRB/RGB/BGR/RGBW with chip table + validation, dotstar + EBB nozzle too; GRBG typo removed) · EOF safety (migration + service install default NO - unattended runs change nothing) · wizard infinite-loop fix (stored value outside min/max dead-ended the prompt) · default + file profile DELETES at the LCD with two-press confirm · setup/update SIMULATION across 6 printer types (tools/r110_setup_sim.py: Ender3 stock/reference, legacy migration, CoreXY 2Z dotstar, Voron Trident/V2 - install + update + check + EOF + idempotence, sudo-free) · slicer/firmware DIALECT CORPUS (tools/r110_gcode_dialects.py: 12 families, 43/43 tagged features = 100 percent, Simplify3D detection fixed) · feature-tagging research + roadmap (docs/FEATURE_TAGGING.md)'),
      ('.83', 'FIELD-LOG .82 ISSUE LIST (the whole R106 round): fan wake-up (0%% -> higher applies the scaled file value immediately; layer-1 hold wins) - honest velocity/corner hints (they are CAPS, the visible lever is the cruise ratio) - the USER TYPE MAP everywhere (visible top = Top surface, between = Internal solid, only true airwork = Bridge; the frame front used to tag Internal solid so top overrides never reached the visible face; siblings fixed in labels/ties/seal/angles/bridge + Cura SKIN on layer 1) - RULE LL: nothing prints unanchored (shelf + disc lips got radial anchor stubs, kit lips too, SIDE closure redesigned around the T/B wall anchors) - FEATURE FILTER: feature menus hide what the file does not contain (80 items), available-but-inactive stays visible - presets fill W/H - FRAME USER PRESETS (8 slots, save/load/delete at the LCD) - WALL LOOPS 1-4 - Z-HOP on firmware retracts (live + pre-print, absolute Z, layer-change-aware) - TRAVEL controls (SET_LIVE_ACCEL + Velcap relabeled: global caps govern travels too) - LITHOPHANE FLAT MODE (bed-clamped terraced relief, 1-4 color bands with pause/swap) - HARD BED CLAMPS (frame border clamps before splitting; W/H inputs never exceed the build volume) - R108: LED AREAS + SYSTEM&gt;LED SETUP (status/bed-light/nozzle freely configurable, neopixel or dotstar, mainboard pin or EBB CAN chain, hard-clamped to chain_count, persisted in the new HARDWARE PROFILE r2_hardware.cfg - a second variables file that survives deleting variables.cfg) - SETUP/UPDATE WIZARDS (every hardware value asked in English + double-confirmed: build volume, probe offsets, clean/present positions, LED layout; update asks keep-or-change first) - VERIFIED BACKUPS + 4 CHANGE MODES (backup of every file first, cmp-verified, abort on mismatch; every printer.cfg/moonraker.conf change shown first: automatic with user lines only commented / commented-only / separate txt=safest / skip) - OBJECT PROCESSING shown+explained+offered both directions - printer.cfg.example fixes (chain_cnt to chain_count, GRBGR color_order - both halted current Klipper)'),
      ('.82', 'CRITICAL CONFIG FIX (field log .81): the bed/position carrier was a raw [r2_postproc] section in printer.cfg - Klipper REFUSES unknown sections (halt loop: Section r2_postproc is not a valid config section) the first time the section was really written. The carrier is now a KAMP-style [gcode_macro _R2_CONFIG] settings macro (variable_bed_min_x ... + variable_present_x/y + variable_wipe_x/y) - valid for Klipper, native for macros, parsed by the watcher; setup.sh migrates legacy sections (backup + values kept). Also found: appending after the #*# save_config block made the autosave unreadable (modifications after header -> heater_bed control error) - inserts now always go before that block'),
      ('.81', 'honest host verdict + portability hardening (field log .80): HOST_CHECK swap verdict now measures swap ACTIVITY (vmstat in/out) - 109MB of quietly parked pages after boot were flagged SWAPPING with an error sound on every check although the Pi was healthy; quiet pages now read as OK with a calm explanation, only real swap traffic stays loud. Compatibility: PRINT_END part presentation had a fixed Y228 (crash on any bed under ~232mm) - now clamped + configurable ([r2_postproc] present_x/present_y), calibration-tower end parks (Y190) and PLT_FRAME park clamped, nozzle-wipe pad anchor configurable (wipe_x/wipe_y), megatest.py accepts --bed/--cfg for other printers (too-big combos = SKIP); setup.sh (environment wizard) and COMPATIBILITY.md (portability report) join the package'),
      ('.80', 'megatest hardening (field log .79): a 101-run sweep over every generator at its parameter extremes found and fixed two real bugs - the plotter DRAW mode scaled small images past the bed (48px drawing -> y up to +1500mm; big photos silently squashed to ~72mm) and every frame file tags the shelf bands as BRIDGE but TYPES never listed it on normal frames; plot output now carries a final bed guard too; tools/megatest.py joins the package (rerun any time: python3 tools/megatest.py)'),
      ('.79', 'frame shells, sparse infill & travel order (field log .78): Top/Bottom solid layers settable (independent of front effect and orientation; default bottom skin 2) · body infill down to 5% (was 20) with its own INFILL-SPARSE feature tag · ring fill travels stay INSIDE the band now - the scanline order used to cross the photo opening on every line (139 long retracted travels per body layer -> ~5, layer 1: 146 travels -> 6) · TYPES lists only features the file really tags'),
      ('.78', 'plain uploads convert ONCE (field log .77): a plain image/text in the gcodes folder (AxtBunny.png) was re-converted to pen-plotter g-code on EVERY watcher (re)start - 1 processed at every boot, the .gcode rewritten, its preview push racing the Klipper restart after an update (HTTP 404); the already-converted check now reads the OUTPUT file, and a 404 preview push says Klipper is probably still restarting'),
      ('.77', 'generator file info + label modes (field log .75): frame / cable-tie / angle files carry _FILE_INFO with TYPES now - the Pre-Print file info and the feature activators work for EVERY generated file (they were empty: generated files are TAGged, the scan never adds them); structured frame fronts tag SURFACE-TOP instead of CUSTOM; labels get two clear modes - GROW (the label grows to the text, W/H are minimums and Calc fit sets the needed size as the W/H lower limits) and FIXED (the label stays W/H, the font scales into it) - and the confusing "Preview fit?" item is now "Calc fit" with a plain explanation'),
      ('.76', 'watcher start-up (field log .75): the first scan after a boot/restart runs in time-boxed chunks now - it used to block the watch loop as ONE pass (12+ minutes on a swapping Pi Zero right after a reboot) and every file selected in that window showed an empty file info; selections are serviced within seconds while the start backlog drains in the background · a backlog preview push can never overwrite a fresher file selection anymore (preview nonce re-check before the push)'),
      ('.75', 'frame placement & first layer (field log .74): every frame plate (one-piece / multi Part A/B / kit) sits centered on the usable bed, nothing at the x0/y0 corner anymore (the multi-plate stand sat at the raw bed origin half off the bed, the one-piece stand overlapped the ring - both placement bugs fixed); first layer of every frame part: brim -> inner wall -> outer wall -> ONE continuous zigzag fill with extruded connectors (single hatch lines curled up at their ends and frayed the borders), open holes crossed only with a retraction · retract keep-outs completed (field log .74): cable-tie head channel + loop slot, gasket groove, backplate keyhole + stud holes and bridge spans are retract keep-outs too - no travel crosses an open hole without retracting anymore (was 74+22+17+1 unretracted crossings; zero-length travels never retract; FLAT gaskets and lithophanes have no openings at all)'),
      ('.74', 'range feature truth (vase opens with the cut feature, brim on the FIRST layer inside raft layer 1, TYPES/FS/FA describe the excerpt) · full slicer feature census 12 to 16: overhang wall, internal bridge, prime tower and custom G-code sections are editable features; small-perimeter speed/accel from the config header in the file info; every slicer family dialect mapped (census table ch. 3.7); old default presets keep loading (new features fall back to OFF) · range hole quality: cap holes print bridges around the opening first, ring on the bridges, hole stays open; all generators retract travels over open holes at any length · beep discipline while printing: confirmation/feedback beeps silent during an active print (no purge blobs from micro pauses), critical sounds always play · seamless texture on arc-fitted files (G2/G3 flattened into textured chords, E preserved; fuzzy presets sized after OrcaSlicer: ORCA/Hide layers/Subtle/Grip, thickness 0.05-1.5mm'),
      ('.73', 'frame & display-case generator (real-bed fit: one file / multi-plate Part A+B / 4-strip glue kit, RECT/OVAL, BACK bayonet - SIDE slide-in, hang keyhole + easel stand, surface Lines/Waves/Honeycomb/FLIP, disc insert glass/plexi/foil/litho, hidden cable duct), texture tool for ANY g-code file (fuzzy skin + GRID/WAVES/HEX/MANDELBROT bumps on outer walls only - tags/E/Z/F untouched, _TX result never auto-started), file check (tag version census on LCD/console/SSH + safe retag with .r2bak backup), seal + lithophane generators with LCD image browser, cable-tie redesign CLASSIC/LOOP, real-bed truth via [r2_postproc], probe-safe color-change purge strip, global x feature parameter model (flow multiplies, accel percent scaler), Tools menu English, live-tuning menu regrouped (audit), nozzle diameter from printer.cfg for every generator, prime-line de-ooze + resume without object purge (field log .73)'),
      ['.72','field-log .71 fixes: EXCLUDE_OBJECT POLYGON as valid json (cable ties + angles/plates start crash; all 5 generators verified), global speed/accel no longer eat feature overrides (feature rides ON TOP of the global, re-applied on every change; feature accel beats the global), range holes print as ONE spiral boss with retracting travels (no more strings over the hole), APPLY_TYPE re-derived from ;TYPE: when a source carries none (everything-printed-as-solid-infill mitigation), hole diameter clamps to the REAL section outline + 2mm margin (boss never sticks out of L/round sections)'],
      ['.71','LCD declutter: the four part generators (Kabelbinder, Winkel+Flach, Labels, Plotter) now live in ONE \'Tools\' top-level menu - the root drops from 10 to 7 entries; guards unchanged, console paths + manual follow'],
   ['.70','part generators (cable ties + angles/flat connectors, LCD top menus), centered layer-range holes: floor hole with boss ring (E14/E27 presets) + bridge-first top hole, angle walls/infill/ironing (+ inner-wall fix), nozzle LED split for the EBB42 (SET_NOZZLE_SPLIT), slicing guide for any slicer, electronics chapter: U2C V2.1 + EBB42 CAN + 230 V relay (wiring lists, firmware, safety)'],
   ['.69','file fixes IN PLACE (no re-upload): RetFix file rewrites the selected file\'s retracts to G10/G11 on disk (markers survive), Vol->mm fix converts Marlin-volumetric E to mm (idempotent), start dialog auto-released, micro-pauses between multi-value writes'],
   ['.68','file info: slicer + firmware flavor of every file (Orca/Prusa/Cura/Elegoo/Kiri:Moto/AstroPrint/SliceBeam for Klipper/Marlin), Marlin-volumetric warning (Klipper counts E in mm), RetFix rewrites old Bowden-era files\' retracts to G10/G11 on re-upload (current retraction applies, live-tunable)'],
   ['.67','label/preview/generator overhaul from the .65 field log: print-start killer fixed (quoted feature lists survive Klipper\'s parser), material preset load fixed, generated files sort to the top (00_..._V version suffix, same name overwrites instead of piling up), label text with discrete glyph retracts + anti-merge stroke cap + purge tower 15mm clear on the probe-safe side, real fit preview on the LCD (final size, cap height, minimum size for a fixed font), labels up to 5 lines and near-bed size, filament stat in meters, SAVE+RESTART restarts even when nothing is pending'],
   ['.66','user-handbook manual + PDF (scenarios, generators, calibration ladder); three small-text label fonts (COND/NARROW/CAPS); maintenance menu in calibration order'],
   ['.65','postproc streaming: range generation + upload tagging no longer load whole files into RAM (Pi-safe), byte-identical outputs (golden test)'],
   ['.64','start-killer fixed (list literals broke SET_GCODE_VARIABLE), labels auto-fit/auto-grow, All-OFF removed'],
   ['.63','generator files auto-select, range OUTLINE floor fills the enclosed area, L1/L2 rules in every mode, PARAM_SOURCES'],
   ['.58–.61','plotter top-level menu, 3 label lines, range clamping + PRINT_END, cold pull in Maintenance, filament before the print'],
   ['.53–.57','KAMP object data kept, label maker (editor, fonts, holes, two colors), range floor/brim/top with OUTLINE'],
   ['.45–.52','generated calibration files (temp tower, flow cube, retract tower), resonance diagram + shaper apply, dark-background plots, plot text/status, bridging test'],
   ['.40–.44','live tuning reads REAL Klipper values, per-feature speeds/accels MEASURED from the g-code, 12-feature system, one global factor'],
   ['.29–.39','universal print intercept, net probe, nozzle wipe, gapless legacy resume, probe-safe prime line, one takeover mode'],
   ['.10–.28','foundation: state machine, watcher, start dialog, materials, sounds, LEDs, LCD menus, KAMP, mesh strategy'],
  ],[24*mm,136*mm]))

doc=Doc(os.path.join(os.path.dirname(__file__),'..','MANUAL.pdf'))
doc.build(E)
print('MANUAL.pdf built (illustrated user handbook, .102)')
