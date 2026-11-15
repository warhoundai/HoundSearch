"""Audit all installed third-party distributions; first-party source is separately audited."""
import importlib.metadata as md,subprocess,tempfile
own={'houndcrawler','houndsearch'}
requirements=[]
for dist in md.distributions():
 name=dist.metadata['Name'];normalized=name.lower().replace('_','-')
 if normalized not in own:requirements.append(name+'=='+dist.version)
with tempfile.NamedTemporaryFile(mode='w',suffix='.txt') as f:
 f.write('\n'.join(sorted(requirements)));f.flush()
 subprocess.run(['pip-audit','--strict','--no-deps','--disable-pip','-r',f.name],check=True)
print('First-party Git dependency audited separately by source tests and audit-source.py; no third-party distribution omitted.')
