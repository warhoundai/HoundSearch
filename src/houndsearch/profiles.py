"""Encrypted, tenant-owned upstream profiles. No service-owned production keys."""
import json,re
from urllib.parse import urlsplit
from cryptography.fernet import Fernet
from houndcrawler.errors import ScrapeError
FIXED={'exa':'https://api.exa.ai','brave':'https://api.search.brave.com','serper':'https://google.serper.dev','gemini':'https://generativelanguage.googleapis.com/v1beta'}
class Profiles:
 def __init__(self,settings,store):self.cfg=settings;self.store=store;self.cipher=Fernet(settings.encryption_key.encode())
 def validate(self,value):
  allowed={'kind','key','endpoint','model','pricing','request_cost_usd','project','location'}
  if not isinstance(value,dict) or set(value)-allowed:raise ScrapeError('PROFILE_INVALID','Unknown profile setting',422)
  kind=value.get('kind')
  if kind not in ('exa','brave','serper','searxng','openai','gemini','vertex','crawler'):raise ScrapeError('PROFILE_INVALID','Unsupported provider',422)
  if kind in ('exa','brave','serper','gemini') and (not isinstance(value.get('key'),str) or not value['key']):raise ScrapeError('PROFILE_INVALID','This provider requires your own key',422)
  endpoint=value.get('endpoint')
  if kind in FIXED and endpoint and endpoint.rstrip('/')!=FIXED[kind]:raise ScrapeError('PROFILE_INVALID','Fixed provider endpoints cannot be overridden',422)
  if kind in ('searxng','openai','crawler'):
   if not endpoint or endpoint.rstrip('/') not in [u.rstrip('/') for u in self.cfg.trusted_endpoints]:raise ScrapeError('PROFILE_ENDPOINT_DENIED','Operator must allowlist this exact endpoint first',403)
   p=urlsplit(endpoint)
   if p.scheme not in ('https','http') or p.username or p.password or p.query or p.fragment:raise ScrapeError('PROFILE_INVALID','Invalid configured service endpoint',422)
   if p.scheme=='http' and p.hostname not in ('localhost','127.0.0.1','::1') and not p.hostname.endswith('.internal'):raise ScrapeError('PROFILE_INVALID','Remote endpoints require TLS; explicit .internal development names are allowed',422)
  if kind in ('gemini','openai','vertex') and not value.get('model'):raise ScrapeError('PROFILE_INVALID','Specify your model explicitly',422)
  for k in ('request_cost_usd',):
   if k in value and (not isinstance(value[k],(int,float)) or not 0<=value[k]<=100):raise ScrapeError('PROFILE_INVALID','Invalid request price',422)
  if value.get('key') and ('\n' in value['key'] or '\r' in value['key']):raise ScrapeError('PROFILE_INVALID','Invalid credential',422)
  return value
 def put(self,tenant,name,value):
  if not re.fullmatch('[A-Za-z0-9_-]{1,100}',name):raise ScrapeError('PROFILE_INVALID','Invalid profile name',422)
  value=self.validate(value);encrypted=self.cipher.encrypt(json.dumps(value).encode()).decode()
  with self.store.pool.connection() as c:c.execute('INSERT INTO hsearch_profiles VALUES(%s,%s,%s) ON CONFLICT(tenant,name) DO UPDATE SET ciphertext=excluded.ciphertext',(tenant,name,encrypted))
  return {'name':name,'kind':value['kind'],'configured':True}
 def get(self,tenant,name):
  with self.store.pool.connection() as c:r=c.execute('SELECT ciphertext FROM hsearch_profiles WHERE tenant=%s AND name=%s',(tenant,name)).fetchone()
  if r:value=json.loads(self.cipher.decrypt(r['ciphertext'].encode()))
  else:value=self.cfg.provider_profiles.get(tenant,{}).get(name)
  if not value:raise ScrapeError('PROFILE_NOT_CONFIGURED','Configure your own provider profile for this tenant',503)
  return self.validate(value)
 def delete(self,tenant,name):
  with self.store.pool.connection() as c:c.execute('DELETE FROM hsearch_profiles WHERE tenant=%s AND name=%s',(tenant,name))
 def known_secrets(self,tenant):
  with self.store.pool.connection() as c:rows=c.execute('SELECT ciphertext FROM hsearch_profiles WHERE tenant=%s',(tenant,)).fetchall()
  profiles=[json.loads(self.cipher.decrypt(r['ciphertext'].encode())) for r in rows]+list(self.cfg.provider_profiles.get(tenant,{}).values())
  return [p['key'] for p in profiles if p.get('key')]
