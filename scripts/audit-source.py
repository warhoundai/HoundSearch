"""Reject known credential formats and proprietary integrations before publication."""
import json,re,subprocess,sys
from pathlib import Path
root=Path(__file__).parents[1]
files=[f for f in subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0') if f and not f.startswith('src/houndsearch/static/')]
files.extend(str(p.relative_to(root)) for p in (root/'src/houndsearch/static').rglob('*') if p.is_file())
patterns=[r'AKIA[0-9A-Z]{16}',r'gh[pousr]_[A-Za-z0-9]{30,}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'vcp_[A-Za-z0-9]{30,}',r'AIza[0-9A-Za-z_-]{30,}']
findings=[]
for name in files:
    if not name or name==__file__:continue
    path=root/name
    if '.env'==path.name or path.is_symlink():findings.append({'file':name,'reason':'secret file or symlink'});continue
    text=path.read_text(errors='replace')
    for expression in patterns:
        if re.search(expression,text):findings.append({'file':name,'reason':'credential signature'})
    if name.startswith('src/') and re.search(r'751446514671|warhound/web/runtime|warhound-github-deployment|yc-demo@',text):findings.append({'file':name,'reason':'proprietary integration'})
print(json.dumps({'files_scanned':len([f for f in files if f]),'findings':findings}))
if findings:sys.exit(1)
