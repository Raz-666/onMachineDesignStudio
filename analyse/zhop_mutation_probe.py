#!/usr/bin/env python3
"""Isolierter Gegenmutationstest zu _ZScan, KEIN Produktfix.

Die Mutante lehnt nur E0 ab: E<0 und M82 werden weiterhin NICHT richtig
behandelt. Sie dient ausschliesslich der Ursachenisolierung und ist keine
vorgeschlagene Implementierung. Keine Dateien ausser temporaeren Python-Objekten.
"""
import ast
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools'))
import r2_postproc as pp

tree=ast.parse((root/'tools/r2_postproc.py').read_text())
node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='_ZScan')
class Mutate(ast.NodeTransformer):
    def __init__(self):self.changed=0
    def visit_Assign(self,node):
        self.generic_visit(node)
        if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='extruding':
            node.value=ast.BoolOp(op=ast.And(),values=[node.value,
                ast.Compare(left=ast.Call(func=ast.Attribute(value=ast.Name(id='p',ctx=ast.Load()),
                                                            attr='get',ctx=ast.Load()),
                                          args=[ast.Constant(value='E'),ast.Constant(value=0)],keywords=[]),
                            ops=[ast.NotEq()],comparators=[ast.Constant(value=0)])])
            self.changed+=1
        return node
mutation=Mutate(); node=mutation.visit(node); assert mutation.changed==1
env={'MOVE_RE':pp.MOVE_RE,'parse_params':pp.parse_params}
exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(root/'tools/r2_postproc.py'),'exec'),env)
for event in ('G1 X12 Y0','G1 X12 Y0 E0','G1 X12 Y0 E-0.2'):
    lines=['M83','G90','G1 X10 Y0 Z0.2 E1','G0 Z0.4',event,'G0 Z0.2',
           'G1 X20 Y0 E1','G0 Z0.4','G1 X30 Y0 E1']
    results=[]
    for cls in (pp._ZScan,env['_ZScan']):
        scan=cls()
        for i,line in enumerate(lines):scan.step(i,i,line)
        ins,_=scan.result();results.append([lines[idx] for _,idx in ins])
    print(event,'original=',results[0],'E0-Gegenmutation=',results[1])
assert results[0]==results[1], 'Rueckzug muss auch in dieser unvollstaendigen Mutante falsch bleiben'
