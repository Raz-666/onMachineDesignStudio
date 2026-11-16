#!/usr/bin/env python3
"""Offline-Zusammensetzung einzelner Originalmenues/-Makros + gepinnter Parser.
In-memory SAVE_VARIABLE; alle sonstigen Befehle werden gestubbt. Kein Klipper,
keine Datei-, Netzwerk- oder Hardwareausfuehrung. UI-Timing wird angenommen.
"""
from pathlib import Path
from types import SimpleNamespace
import contextlib,io,runpy
root=Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):
    lib=runpy.run_path(str(root/'analyse/override_material_probe.py'))
Obj=lib['Obj'];template=lib['template'];env=lib['env'];printer=lib['printer']
Dispatcher=lib['Dispatcher'];setter=lib['setter'];render=lib['render']
def menu_body(name):
    text=(root/'menus/lcd_menues.cfg').read_text(encoding='utf8')
    sec=text.split('[menu '+name+']',1)[1].split('\n[',1)[0]
    return env.from_string(sec.split('\ngcode:\n',1)[1])
def simulate(sv,text):
    """Verarbeitet nur einfache SAVE_VARIABLE und 1 Ebene SET_OVERRIDE_VALUE.
    Alle anderen Ausgaben werden ignoriert; KEINE generische Makroausfuehrung.
    """
    d=Dispatcher(sv)
    for line in text.splitlines():
        line=line.strip()
        if line.startswith('SET_OVERRIDE_VALUE '):
            args=dict(token.split('=',1) for token in line.split()[1:])
            d.run_lines(render(setter,sv,args))
        elif line.startswith('SAVE_VARIABLE '):d.run_lines(line)
    return d.events
# 1. Original LCD-Flow-Wertzeile + optionaler separater Toggle.
gval=menu_body('__main __preprint __motion __ext __flfe __gval')
toggle=template('macros/07_start_confirm.cfg','TOGGLE_OVERRIDE')
for prior in (False,True):
    sv=Obj({'ov_flow':100,'ov_flow_on':prior})
    m=gval.render(printer=printer(sv),menu=SimpleNamespace(input=90))
    simulate(sv,m)
    assert sv['ov_flow']==90 and sv['ov_flow_on'] is prior
    print('LCD Flow-Wert 90, vorher on=',prior,'->',dict(sv))
    d=Dispatcher(sv);d.run_lines(render(toggle,sv,{'NAME':'flow'}))
    assert sv['ov_flow_on'] is (not prior)
    print('  danach ein gesonderter Toggle ->',dict(sv),'(Vorzustand bestimmt Richtung)')
# 2. FILE_AS_PRESET Originaltemplate, beobachtete Aufrufe ausklappen.
fap=template('macros/08_print_start_stop.cfg','FILE_AS_PRESET')
names=['bed','bed_after','hotend_first','hotend_after','fan','pa','flow']
for prior in (False,True):
    sv=Obj({'ov_'+n+'_on':prior for n in names})
    p=printer(sv);p['gcode_macro _PREVIEW']=SimpleNamespace(name='example.gcode',bed=60,hotend=215,fan=100,pa=.05,flow_ratio=.95)
    out=fap.render(printer=p,params=Obj())
    calls=[l.strip() for l in out.splitlines() if l.strip().startswith('SET_OVERRIDE_VALUE ')]
    events=simulate(sv,out)
    assert len(calls)==7 and all(sv['ov_'+n+'_on'] is prior for n in names)
    assert all('ov_'+n in sv for n in names)
    print('FILE_AS_PRESET, alle Flags vorher=',prior,'->',[(n,sv['ov_'+n],sv['ov_'+n+'_on']) for n in names])
    print('  Resultat:',len(calls),'Setteraufrufe,',len([e for e in events if e[0]=='save']),'Stub-Saves; Meldung/Beep nicht ausgefuehrt.')
# 3. Original-Material-Editor: eigener Materialwert + bedingter Setter.
medit=menu_body('__main __preprint __material __m0 __flow')
for selected in ('PLA','PETG'):
    sv=Obj({'material':selected,'ov_flow':100,'ov_flow_on':False})
    out=medit.render(printer=printer(sv),menu=SimpleNamespace(input=92))
    simulate(sv,out)
    assert sv['mat_pla_flow']==92 and sv['ov_flow_on'] is False
    assert sv['ov_flow']==(92 if selected=='PLA' else 100)
    print('PLA Material-Flow bearbeiten, ausgewaehlt=',selected,'-> mat_pla_flow=',sv['mat_pla_flow'],'ov_flow=',sv['ov_flow'],'on=',sv['ov_flow_on'])
# 4. Ironing-Karte 2: tatsaechlich vom Originaltemplate gerenderte F-Werte.
iron_cal=template('macros/12_maintenance.cfg','IRONING_CAL')
sv=Obj();p=printer(sv);p['gcode_macro _STATE']=SimpleNamespace(mode='idle')
p['toolhead']=SimpleNamespace(homed_axes='xyz',axis_maximum=SimpleNamespace(y=220))
p['bed_mesh']=SimpleNamespace(profiles={},profile_name='')
out=iron_cal.render(printer=p,params=Obj({'CARDS':'2','START_LAYER':'1','WID':'2'}))
card2=out.split('RESPOND MSG="Ironing card 2/2:',1)[1].split('G0 Z5 F600',1)[0]
assert 'speed 30mm/s' in card2 and ' F1800.0' in card2
print('IRONING_CAL Karte 2: meldet 30 mm/s und rendert Ironing-G1 mit F1800.0 mm/min')
# Explizite Kartenparameter gehoeren zum CAL-Aufruf; nur dessen SAVE_VARIABLE-
# Ausgaben werden angenommen, dann separat das originale RESULT gerendert.
iron_result=template('macros/12_maintenance.cfg','IRONING_RESULT')
for card in (2,4):
    sv=Obj();p=printer(sv);p['gcode_macro _STATE']=SimpleNamespace(mode='idle')
    p['toolhead']=SimpleNamespace(homed_axes='xyz',axis_maximum=SimpleNamespace(y=220))
    p['bed_mesh']=SimpleNamespace(profiles={},profile_name='')
    params=Obj({'CARDS':str(card),'START_LAYER':'1','WID':'2','F'+str(card):'17','S'+str(card):'37'})
    out=iron_cal.render(printer=p,params=params)
    announced=next(l.strip() for l in out.splitlines() if f'Ironing card {card}/{card}:' in l)
    assert 'flow 17%' in announced and 'speed 37mm/s' in announced
    simulate(sv,out)
    result=iron_result.render(printer=printer(sv),params=Obj({'CARD':str(card)}))
    calls=[l.strip() for l in result.splitlines() if l.strip().startswith('SET_OVERRIDE_VALUE ')]
    expected=('30.0','15.0') if card==2 else ('50','25')
    assert calls==[f'SET_OVERRIDE_VALUE NAME=feat_spd_ironing VALUE={expected[0]}',f'SET_OVERRIDE_VALUE NAME=ironing_flow VALUE={expected[1]}'],calls
    print(f'IRONING_CAL Karte {card} explizit F17/S37 ->',announced,'; nach modellierten Saves RESULT ->',calls)
# Ironing-Resultat als moeglicher Feature-Spiegel, Original APPLY_TYPE.
# Annahmen: Sync bereits erfolgt, Feature vorhanden/aktiv; keine echte Ereignisschleife.
apply_type=template('macros/10_live_tuning.cfg','APPLY_TYPE')
for flag in (False,True):
    state=Obj({'mode':'printing','ignore_overrides':False,'layer':2,'current_type':'',
               'fov_ironing':(1,30.0,0.0,100.0,0.0),'g_speed_clean':100.0,
               'fova_iron_flow':15.0,'fova_iron_flow_on':flag,'live_flow':0.0})
    p=Obj({'gcode_macro _STATE':state,'print_stats':SimpleNamespace(state='printing'),
           'extruder':SimpleNamespace(pressure_advance=0.0)})
    out=apply_type.render(printer=p,params=Obj({'TYPE':'IRONING'}))
    ops=[l.strip() for l in out.splitlines() if l.strip().startswith(('M99220 ','M99221 '))]
    assert 'M99220 S30.0' in ops
    assert ('M99221 S15.0' if flag else 'M99221 S100.0') in ops
    print('APPLY_TYPE IRONING, sync angenommen, iron_flow_on=',flag,'->',ops)
# 5. Einzelner Guard-Zweig hat nach ; keine separate M117-Ausfuehrung.
iron=template('macros/12_maintenance.cfg','IRONING_CAL')
sv=Obj();p=printer(sv);p['gcode_macro _STATE']=SimpleNamespace(mode='printing')
out=iron.render(printer=p,params=Obj());line=next(l.strip() for l in out.splitlines() if 'Ironing cal only when idle' in l)
d=Dispatcher(sv);d.run_lines(line)
assert ('stub','RESPOND') in d.events and ('stub','M117') not in d.events
print('IRONING_CAL Guard rendered:',line,'-> dispatchte Stub-Kommandos:',d.events)
print('Annahmen: Jinja getrennt vor jedem simulierten Aufruf, Saves synchron erfolgreich; echte Menue-Erreichbarkeit, Klipper-Runtime und Hardware ungetestet.')
