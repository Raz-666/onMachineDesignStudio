#!/usr/bin/env python3
"""Seitentreue Textextraktion des im Repo befindlichen KALIBRIERUNG.pdf.
Benötigt pypdf. Nur Lesezugriff aufs Produkt; Analyseausgabe unter analyse/.
Extraktion kann Bilder und Zeichensatzdetails verlieren; Seite bleibt Autorität.
"""
from pathlib import Path
import hashlib
from pypdf import PdfReader
root=Path(__file__).resolve().parents[1]
p=root/'KALIBRIERUNG.pdf'
sha=hashlib.sha256(p.read_bytes()).hexdigest()
r=PdfReader(str(p)); parts=[]
for n,page in enumerate(r.pages,1):
    text=page.extract_text() or ''
    parts.append(f'===== PDF-SEITE {n} =====\n{text}\n')
    print(f'Seite {n}: {len(text)} Zeichen')
out=root/'analyse/KALIBRIERUNG-PDF-TEXT.txt'
out.write_text('\n'.join(parts),encoding='utf8')
assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
print(f'PDF {p.name}: sha256={sha}, Seiten={len(r.pages)}, unveraendert=True')
