"""Build a source ZIP for GitHub without credentials, binaries, or site identity."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
ROOT=Path(__file__).resolve().parent
out=ROOT/'dist'/'Parallel-Arcade-GitHub.zip'
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if not p.is_file() or any(part in {'.git','.openai','.sites-runtime','.venv','__pycache__','data','models'} for part in rel.parts):
            continue
        if p.name == '.env' or p.suffix in {'.zip','.tar','.gz','.pyc','.iso','.rom','.bin','.state'}:
            continue
        z.write(p,rel)
print(out)
