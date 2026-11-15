"""Generate local self-hosting credentials, never provider keys."""
import json,secrets,os
from pathlib import Path
from cryptography.fernet import Fernet
p=Path('.env')
if p.exists():raise SystemExit('.env already exists; refusing to overwrite credentials')
values={'POSTGRES_PASSWORD':secrets.token_hex(24),'HOUNDSEARCH_API_KEYS':json.dumps({'local':secrets.token_hex(32)}),'HOUNDSEARCH_ENCRYPTION_KEY':Fernet.generate_key().decode()}
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:
 for k,v in values.items():f.write(k+"='"+v+"'\n")
print('Created owner-only .env. Keep it private. No provider keys were generated or copied.')
