#!/usr/bin/env python3
"""Explizites partielles Ereignismodell zum Start/Preview-Schichtzaehler.

Es rendert unveraenderte Makro-Templates und ruft echte reine Preview-Funktionen
mit gestubbtem Status auf. Es verfolgt NUR _STATE.total_layers/mode und
_PREVIEW.name/total_layers; nur diese SET-Kommandos werden im Modell angewandt.
Keine Befehle werden ausgefuehrt, kein Klipper/Moonraker, kein Drucker, keine
Reactor-/Timer-/Planner-Simulation. Reihenfolgen und ACKs sind Annahmen.
process() veraendert ausschliesslich eine temporaere Fixture-Kopie.
"""
from pathlib import Path
from types import SimpleNamespace
import ast
import gzip
import hashlib
import re
import shlex
import shutil
import sys
import tempfile
from jinja2 import Environment

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools'))
import r2_postproc as pp

env=Environment(variable_start_string='{',variable_end_string='}')
def macro(file,name):
    data=(root/file).read_text(encoding='utf8')
    sec=data.split('[gcode_macro '+name+']',1)[1].split('\n[',1)[0]
    return env.from_string(sec.split('\ngcode:\n',1)[1])
start=macro('macros/08_print_start_stop.cfg','PRINT_START')
file_info=macro('macros/08_print_start_stop.cfg','_FILE_INFO')
preview=macro('macros/08_print_start_stop.cfg','_PREVIEW_SET')
reset=macro('macros/10_live_tuning.cfg','_LIVE_RESET')
peek=macro('macros/08_print_start_stop.cfg','_DIALOG_PEEK')
class Obj(dict):
    def __getattr__(self,name):
        try:return self[name]
        except KeyError as exc:raise AttributeError(name) from exc
def commands(txt):
    return [x for line in txt.splitlines() if (x:=line.strip()) and not x.startswith('#')]
def params(call):
    return Obj(dict(token.split('=',1) for token in shlex.split(call)[1:] if '=' in token))
pat=re.compile(r'^SET_GCODE_VARIABLE MACRO=(_STATE|_PREVIEW) VARIABLE=(total_layers|mode|name) VALUE=(.*)$')
def decoded(v):
    try:
        result=ast.literal_eval(v)
        if isinstance(result,str) and len(result)>=2 and result[0]==result[-1]=='"':
            result=ast.literal_eval(result)
        return result
    except (SyntaxError,ValueError):return v

def scenario(path, raw, ps, name, ack, age, held, replay_mode='waiting', change_file=False):
    state=SimpleNamespace(mode='idle',start_pending='',total_layers=0)
    card=SimpleNamespace(name='',total_layers=0)
    p=Obj({'gcode_macro _STATE':state, 'gcode_macro _PREVIEW':card,
           'print_stats':SimpleNamespace(state='standby',filename=path.name),
           'save_variables':SimpleNamespace(variables={'start_confirm':True,'preview_nonce':0}),
           'configfile':SimpleNamespace(settings=Obj({'printer':Obj({'max_accel':3000})}))})
    def status():
        return {'print_stats':{'state':p.print_stats.state},
                'gcode_macro _STATE':{'mode':state.mode,'total_layers':state.total_layers},
                'gcode_macro _PREVIEW':{'name':card.name,'total_layers':card.total_layers}}
    pp._moonraker_status=status
    pp._preview_last.update(key=None,t=0.,ok=False)
    trace=[]
    def snap(stage):trace.append((stage,state.mode,state.total_layers,card.name,card.total_layers))
    def apply_output(out):
        for c in commands(out):
            if c=='_LIVE_RESET':
                apply_output(reset.render(printer=p))
            else:
                m=pat.fullmatch(c)
                if m:setattr(state if m.group(1)=='_STATE' else card,m.group(2),decoded(m.group(3)))
    def deliver(script):
        for call in script:
            if call.startswith('_PREVIEW_SET '):apply_output(preview.render(printer=p,params=params(call)))
            elif call.startswith('_FILE_INFO '):apply_output(file_info.render(printer=p,params=params(call)))
    # Explicit selection-time PREVIEW_SET/_FILE_INFO delivery if ACK succeeds.
    # For failed ACK the model ASSUMES no delivery (a real error can be ambiguous).
    lines,_=pp._preview_script(str(path))
    assert any(c.startswith('_FILE_INFO ') for c in lines)
    if ack:deliver(lines)
    pp._preview_remember(path.name,str(path),ack)
    remembered=pp._preview_last['t']
    snap('selection ACK='+str(ack))
    # The actual file then delivers its _FILE_INFO before PRINT_START.
    p.print_stats.state='printing'
    apply_output(file_info.render(printer=p,params=params(raw)))
    snap('file _FILE_INFO')
    out=commands(start.render(printer=p,params=params(ps)))
    assert any(c.split()[0]=='_DIALOG_PEEK' for c in out)
    apply_output('\n'.join(out))
    assert state.mode=='waiting' and state.total_layers==0
    snap('PRINT_START + _LIVE_RESET')
    peek_out=commands(peek.render(printer=p))
    assert any(c.startswith('SAVE_VARIABLE VARIABLE=preview_nonce ') for c in peek_out)
    # The model assumes a later nonce is processed and the motion gate is open.
    if not held:card.name='different.gcode'
    if change_file:
        with path.open('a',encoding='utf8') as f:f.write('; TEMP-MODELL: Datei geaendert\n')
    state.mode=replay_mode
    skip=pp._preview_dup_skip(path.name,str(path),now=remembered+age)
    if not skip:
        lines,_=pp._preview_script(str(path))
        deliver(lines)
    snap('repeek: skip='+str(skip))
    print('\n'+name)
    for stage,mode,total,cardname,cardtotal in trace:
        print(f'  {stage}: mode={mode}, STATE.total={total}, PREVIEW.name={cardname or "-"}, PREVIEW.total={cardtotal}')
    return skip,state.total_layers,card.total_layers

old_status=pp._moonraker_status
old_last=pp._preview_last.copy()
fixture=root/'testfixtures/bigrose_020mm.gcode.gz'
hash0=hashlib.sha256(fixture.read_bytes()).hexdigest()
try:
    with tempfile.TemporaryDirectory(prefix='r2-seq-model-') as tmp:
        path=Path(tmp)/'bigrose.gcode'
        with gzip.open(fixture,'rb') as f,path.open('wb') as out:shutil.copyfileobj(f,out)
        pp.process(str(path))
        rows=path.read_text(encoding='utf8',errors='replace').splitlines()
        raw=next(x for x in rows if x.startswith('_FILE_INFO '))
        ps=next(x for x in rows if x.startswith('PRINT_START '))
        assert rows.index(raw)<rows.index(ps)
        cases=[('ACK, gleicher Name, 1s',True,1,True,'waiting',(True,0,251)),
               ('ACK fehlte, keine Zustellung angenommen',False,1,True,'waiting',(False,251,251)),
               ('ACK, Fenster abgelaufen',True,121,True,'waiting',(False,251,251)),
               ('ACK, anderer Preview-Name',True,1,False,'waiting',(False,251,251)),
               ('ACK, Fenster abgelaufen, inzwischen printing',True,121,True,'printing',(False,0,251))]
        for name,ack,age,held,mode,expected in cases:
            got=scenario(path,raw,ps,name,ack,age,held,mode)
            assert got==expected,(name,got,expected)
        name='ACK, Datei nach ACK geaendert'
        got=scenario(path,raw,ps,name,True,1,True,change_file=True)
        assert got==(False,251,251),(name,got)
    assert hashlib.sha256(fixture.read_bytes()).hexdigest()==hash0
    print('\nFixture-Archiv unveraendert; nur teilweises Offline-Modell, keine Befehle ausgefuehrt.')
finally:
    pp._moonraker_status=old_status
    pp._preview_last.clear();pp._preview_last.update(old_last)
