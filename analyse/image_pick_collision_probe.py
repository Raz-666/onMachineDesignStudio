#!/usr/bin/env python3
"""Extrahierter Image-Pick-Block: temporaere Dateien, Moonraker nur Stub."""
import ast, os, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'tools/r2_postproc.py').read_text()
tree=ast.parse(source)
watch=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='watch')
# Der Block liegt in der Watcher-Schleife; zielgenau anhand img_pick_nonce finden.
target=[]
for n in ast.walk(watch):
    if isinstance(n, ast.Try) and 25890 <= n.lineno <= 25905:
        target.append(n)
assert len(target)==1, len(target)
code=compile(ast.fix_missing_locations(ast.Module(body=[target[0]],type_ignores=[])), 'tools/r2_postproc.py','exec')
with tempfile.TemporaryDirectory(prefix='r2-imagepick-') as d:
    p=Path(d); (p/'sub').mkdir(); (p/'photo.png').write_bytes(b'ORIGINAL_ROOT_IMAGE'); (p/'sub/photo.png').write_bytes(b'SUBFOLDER_IMAGE')
    notices=[]
    env={'rv':{'img_pick_nonce':'new','img_pick_file':'sub/photo.png'},'last_img_pick_nonce':None,'directory':d,'os':os,'_moonraker_gcode':notices.append}
    exec(code,env)
    print('root_after=',(p/'photo.png').read_bytes())
    print('sub_after=',(p/'sub/photo.png').read_bytes())
    print('notice=',notices[0])
    assert (p/'photo.png').read_bytes()==b'SUBFOLDER_IMAGE'
    assert (p/'sub/photo.png').read_bytes()==b'SUBFOLDER_IMAGE'
    print('PASS: basename collision overwrites existing root image in extracted block; no actual watcher or printer tested.')
