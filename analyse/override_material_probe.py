#!/usr/bin/env python3
"""Originaltemplates + gepinnter Klipper-Parser; KEINE Maschinen- oder Dateischreibbefehle.

Klipper-Dispatch wird isoliert aus gepinnter Referenz geladen. Handler fuer
SAVE_VARIABLE schreibt nur in ein Python-Dict. Alle anderen Makros/Befehle sind
Stubs; nicht vollstaendige Klipper-Simulation, keine Sensoren oder Firmware.
"""
from pathlib import Path
from types import SimpleNamespace
import ast, hashlib, importlib.util
from jinja2 import Environment
root=Path(__file__).resolve().parents[1]
kfile=root/'analyse/klipper-referenz/gcode.py'
assert hashlib.sha256(kfile.read_bytes()).hexdigest()=='a2bcd6949b4263f608eaa71ba1cdfb713553542b7b90de739241b624f06415ae'
spec=importlib.util.spec_from_file_location('klipper_gcode_reference',kfile)
k=importlib.util.module_from_spec(spec);spec.loader.exec_module(k)
env=Environment(variable_start_string='{',variable_end_string='}')
class Obj(dict):
    def __getattr__(self,key):
        try:return self[key]
        except KeyError as exc:raise AttributeError(key) from exc
def source(file):return (root/file).read_text(encoding='utf8')
def template(file,name):
    sec=source(file).split('[gcode_macro '+name+']',1)[1].split('\n[',1)[0]
    return env.from_string(sec.split('\ngcode:\n',1)[1])
matfile='macros/05_materials.cfg';setter=template('macros/07_start_confirm.cfg','SET_OVERRIDE_VALUE')
save=template(matfile,'SAVE_MATERIAL_TEMPS');load=template(matfile,'SET_MATERIAL')
flow=template('macros/12_maintenance.cfg','FLOW_CAL_APPLY')
temp=template('macros/12_maintenance.cfg','TEMP_TOWER_RESULT')
retract=template('macros/12_maintenance.cfg','RETRACT_TOWER_RESULT')
ironing=template('macros/12_maintenance.cfg','IRONING_RESULT')
db=ast.literal_eval(source(matfile).split('variable_presets:',1)[1].split('\ngcode:',1)[0].strip())
# Echter gepinnter _process_commands + _get_extended_params, nur Handler stubben.
class Dispatcher(k.GCodeDispatch):
    def __init__(self,variables):
        self.variables=variables;self.events=[];self.gcode_handlers={'SAVE_VARIABLE':self.do_save}
        self.printer=SimpleNamespace(send_event=lambda *x:None,invoke_shutdown=lambda *x:None)
    def respond_info(self,*x,**y):pass
    def respond_raw(self,*x,**y):pass
    def _respond_error(self,msg):raise AssertionError(msg)
    def cmd_default(self,gcmd):self.events.append(('stub',gcmd.get_command()))
    def do_save(self,gcmd):
        cmd=self._get_extended_params(gcmd)
        var=cmd.get('VARIABLE');value=ast.literal_eval(cmd.get('VALUE'))
        self.variables[var]=value;self.events.append(('save',var,value))
    def run_lines(self,text):
        # CFG/Jinja-Kommentarzeilen ausblenden; nur erzeugte Befehlszeilen an den Parser.
        lines=[l.strip() for l in text.splitlines() if l.strip() and not l.lstrip().startswith('#')]
        self._process_commands(lines,need_ack=False)

def printer(sv):return Obj({'save_variables':SimpleNamespace(variables=sv),
                            'gcode_macro _MATERIALS':SimpleNamespace(presets=db),
                            'configfile':SimpleNamespace(settings=Obj({'extruder':{'pressure_advance':0.02},'firmware_retraction':{'retract_length':0.75,'retract_speed':35}}))})
def render(t,sv,params=None):return t.render(printer=printer(sv),params=Obj(params or {}))
def setters(out):return [x.strip() for x in out.splitlines() if x.strip().startswith('SET_OVERRIDE_VALUE ')]
def run_setters(sv,lines):
    d=Dispatcher(sv)
    for line in lines:
        # Diese Probe modelliert nur wohlgeformte NAME/VALUE-Aufrufe aus Result-Makros.
        args=dict(part.split('=',1) for part in line.split()[1:])
        out=render(setter,sv,args)
        if '; SAVE_VARIABLE' in out:
            print('  Setter-Zeile:',next(l.strip() for l in out.splitlines() if '; SAVE_VARIABLE' in l))
        d.run_lines(out)
    return d.events
# Alle 16 einfachen Setterzweige untersuchen, jeweils mit zuvor ausgeschaltetem Flag.
# Feature-Setter werden gesondert getestet: sie benutzen eigene Zeilen.
scalar_keys=['bed','bed_after','hotend_first','hotend_after','pa','retract_len',
             'retract_speed','unretract_speed','accel','ironing_flow','pa_smooth',
             'flow','velocity','min_cruise','square_corner','fan']
for key in scalar_keys:
    sv=Obj({'ov_'+key+'_on':False})
    events=run_setters(sv,[f'SET_OVERRIDE_VALUE NAME={key} VALUE=42'])
    assert sv['ov_'+key]==42 and sv['ov_'+key+'_on'] is False
    assert not any(e[:2]==('save','ov_'+key+'_on') for e in events)
print('Skalare Setterzweige: 16/16 Werte im Modell gespeichert, 0/16 ausgeschaltete Flags aktiviert.')
# Jeweils Startzustand aus = Flag bleibt aus, vorher an = Flag bleibt an.
for prior in (False,True):
    sv=Obj({'flow_cal_result':90,'ov_flow_on':prior,'ov_flow':100})
    outs=setters(render(flow,sv));events=run_setters(sv,outs)
    assert sv['ov_flow']==90 and sv['ov_flow_on']==prior
    assert not any(e[:2]==('save','ov_flow_on') for e in events)
    print('FLOW_CAL_APPLY prior_on=',prior,'-> Wert=',sv['ov_flow'],'on=',sv['ov_flow_on'],'Aufruf=',outs)
# Fuenf Resultpfade; Ironing Feature-Speed benutzt einen anderen Setterzweig.
cases=[('temperature',temp,{'ttg_nb':5,'ttg_start':220,'ttg_step':-5,'ov_hotend_first_on':False,'ov_hotend_after_on':False},{'BLOCK':'2'},['ov_hotend_first_on','ov_hotend_after_on']),
       ('retract',retract,{'rt_nb':6,'rt_start':0.5,'rt_step':0.5,'ov_retract_len_on':False},{'BLOCK':'3'},['ov_retract_len_on']),
       ('ironing',ironing,{'iron_cal_cards':3,'ovf_ironing_on':False,'ov_ironing_flow_on':False},{'CARD':'2'},['ov_ironing_flow_on'])]
for label,t,initial,params,flags in cases:
    sv=Obj(initial);calls=setters(render(t,sv,params));events=run_setters(sv,calls)
    assert all(sv[f] is False for f in flags)
    if label=='ironing':assert sv['ovf_ironing_on'] is True and sv['ov_ironing_flow']==15
    print(label,'Result-Aufrufe=',calls,'Werte/Flags=',dict(sv),'saves=',[e for e in events if e[0]=='save'])
# Startverwendung: originaler Ausschnitt ohne Motion aus _RUN_PRINT_START.
lines=source('macros/08_print_start_stop.cfg').splitlines()
assert "{% set cfg_e = printer.configfile.settings['extruder']" in lines[327]
start=env.from_string('\n'.join(lines[327:341]))
for flag in (False,True):
    sv=Obj({'ov_flow':90,'ov_flow_on':flag})
    out=start.render(printer=printer(sv),sv=sv,apply=True)
    cmd=next(l.strip() for l in out.splitlines() if l.strip().startswith('M221 ')) if 'M221 ' in out else None
    # M221 steht in Zeile 351 ausserhalb des Ausschnitts: den Wert aus gleicher
    # Original-Jinja-Auswertung per angehaengtem reinem Ausgabemarker sichtbar machen.
    text=env.from_string('\n'.join(lines[327:341])+'\nRESULT_FLOW={fl}').render(printer=printer(sv),sv=sv,apply=True)
    marker=next(l.strip() for l in text.splitlines() if l.strip().startswith('RESULT_FLOW='))
    assert marker==('RESULT_FLOW=90.0' if flag else 'RESULT_FLOW=100')
    print('Startausschnitt apply=True, flow_on=',flag,'->',marker)
# _APPLY_OV_RETRACT als separat gerenderter Folgeaufruf; keine Ausfuehrung.
applyret=template('macros/10_live_tuning.cfg','_APPLY_OV_RETRACT')
for flag in (False,True):
    sv=Obj({'ov_retract_len':1.5,'ov_retract_len_on':flag})
    p=printer(sv);p['firmware_retraction']=SimpleNamespace(retract_length=0.75,retract_speed=35,unretract_speed=35,unretract_extra_length=0)
    out=applyret.render(printer=p,params=Obj())
    cmd=next(l.strip() for l in out.splitlines() if l.strip().startswith('SET_RETRACTION_BASE '))
    assert ('RETRACT_LENGTH=1.5' if flag else 'RETRACT_LENGTH=0.75') in cmd
    print('_APPLY_OV_RETRACT len_on=',flag,'->',cmd)
# PA-Test liest alte gemeinsame Schaltervariable, nicht die einzelnen Flags.
mlines=source('macros/12_maintenance.cfg').splitlines()
assert 'sv.ov_retract_on' in mlines[646] and 'sv.ov_retract_on' in mlines[647]
pa_fragment=env.from_string('\n'.join(mlines[645:648])+'\nRESULT={rl},{rs}')
for legacy in (False,True):
    sv=Obj({'ov_retract_on':legacy,'ov_retract_len_on':True,'ov_retract_speed_on':True,'ov_retract_len':1.5,'ov_retract_speed':20})
    out=pa_fragment.render(printer=printer(sv),sv=sv)
    result=next(l.strip() for l in out.splitlines() if l.strip().startswith('RESULT='))
    assert result==('RESULT=1.5,20.0' if legacy else 'RESULT=0.75,35.0')
    print('PA CAL Ausschnitt: separate Flags an, alter Flag=',legacy,'->',result)
# Save-Material liest gespeicherte Werte unabhaengig vom jeweiligen ON-Flag.
sv=Obj({'material':'PLA','ov_flow':83,'ov_flow_on':False,'ov_pa':0.123,'ov_pa_on':False,'ov_hotend_first':222,'ov_hotend_first_on':False})
d=Dispatcher(sv);d.run_lines(render(save,sv))
assert sv['mat_pla_flow']==83 and sv['mat_pla_pa']==0.123 and sv['mat_pla_hot1']==222
print('SAVE_MATERIAL_TEMPS bei Flags AUS ->',[(x,sv[x]) for x in ['mat_pla_flow','mat_pla_pa','mat_pla_hot1']])
d.run_lines(render(load,sv,{'MATERIAL':'PLA'}))
assert sv['ov_flow']==83 and sv['ov_flow_on'] is True and sv['ov_pa_on'] is True and sv['ov_hotend_first_on'] is True
print('SET_MATERIAL default apply ->',[(x,sv[x]) for x in ['ov_flow','ov_flow_on','ov_pa','ov_pa_on','ov_hotend_first','ov_hotend_first_on']])
# Kontrast apply=0 bewahrt die vorherige Override-Einstellung.
sv=Obj({'ov_flow':83,'ov_flow_on':False});d=Dispatcher(sv);d.run_lines(render(load,sv,{'MATERIAL':'PETG','APPLY_PRESET':'0'}))
assert sv['ov_flow']==83 and sv['ov_flow_on'] is False and sv['material']=='PETG'
print('SET_MATERIAL APPLY_PRESET=0 ->',dict(sv))
print('Ausser SAVE_VARIABLE im In-Memory-Dict alle Handler Stubs; keine G-Code-Ausfuehrung, kein Klipper-Runtime-/Druckertest.')
