#!/usr/bin/env python3
"""Datei- und Symbolindizes des getrackten Produktbaums, ohne semantische Prüfung."""
import ast
import csv
import hashlib
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
paths=[x for x in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0') if x]
with (ROOT/'analyse/DATEI-INVENTAR.tsv').open('w',encoding='utf8',newline='') as f:
    w=csv.writer(f,delimiter='\t',lineterminator='\n')
    w.writerow(('pfad','bytes','sha256','zeilen_utf8','python_top_level_definitionen','cfg_sektionen'))
    for name in paths:
        p=ROOT/name; b=p.read_bytes(); lines=defs=sections=''
        try:
            text=b.decode('utf8');lines=len(text.splitlines())
            if p.suffix=='.cfg':
                sections=sum(1 for x in text.splitlines() if x.lstrip().startswith('[') and x.strip().endswith(']'))
            if p.suffix=='.py':
                try:defs=sum(isinstance(x,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) for x in ast.parse(text).body)
                except SyntaxError:defs='SyntaxError'
        except UnicodeDecodeError:pass
        w.writerow((name,len(b),hashlib.sha256(b).hexdigest(),lines,defs,sections))
entries=[]
class Visitor(ast.NodeVisitor):
    def __init__(self):self.scope=[]
    def visit_ClassDef(self,n):self.record(n,'Klasse')
    def visit_FunctionDef(self,n):self.record(n,'Funktion')
    def visit_AsyncFunctionDef(self,n):self.record(n,'AsyncFunktion')
    def record(self,n,kind):
        doc=(ast.get_docstring(n) or '').split('\n')[0].replace('\t',' ')
        entries.append((kind,'.'.join(self.scope+[n.name]),n.lineno,n.end_lineno,doc))
        self.scope.append(n.name);self.generic_visit(n);self.scope.pop()
Visitor().visit(ast.parse((ROOT/'tools/r2_postproc.py').read_text(encoding='utf8')))
with (ROOT/'analyse/POSTPROZESSOR-SYMBOLINDEX.tsv').open('w',encoding='utf8',newline='') as f:
    w=csv.writer(f,delimiter='\t',lineterminator='\n')
    w.writerow(('typ','qualifizierter_name','start','ende','docstring_erste_zeile'));w.writerows(entries)
print('Produktdateien:',len(paths),'Symbole:',len(entries),'– keine semantische Prüfung')
