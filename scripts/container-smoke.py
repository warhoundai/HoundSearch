"""Test the actual hardened container against the isolated CI PostgreSQL service."""
import os,subprocess,time,json,secrets,urllib.request,urllib.error
from cryptography.fernet import Fernet
from houndsearch.store import Store
from houndsearch.retrieval import chunks
db=Store(os.environ['HOUNDSEARCH_TEST_DATABASE_URL'])
cid=db.create_collection('alpha','Container fixture','public')['id']
text='Containersentinel verifies actual authenticated retrieval from the production image.'
db.upsert_document('alpha',cid,'https://fixture.example/container','Container fixture',text,{},chunks(text));db.close()
key=secrets.token_hex(32);name='houndsearch-ci-'+secrets.token_hex(4)
args=['docker','run','--detach','--name',name,'--network','host','--read-only','--tmpfs','/tmp:size=128m','--tmpfs','/data:uid=10001,gid=10001','--cap-drop','ALL','--security-opt','no-new-privileges','--env','HOUNDSEARCH_DATABASE_URL='+os.environ['HOUNDSEARCH_TEST_DATABASE_URL'],'--env','HOUNDSEARCH_API_KEYS='+json.dumps({'alpha':key}),'--env','HOUNDSEARCH_ENCRYPTION_KEY='+Fernet.generate_key().decode(),'houndsearch:test']
subprocess.run(args,check=True,capture_output=True)
try:
 for attempt in range(60):
  try:
   with urllib.request.urlopen('http://127.0.0.1:8082/health',timeout=2) as r:assert json.load(r)['status']=='ok'
   break
  except Exception:
   if attempt==59:raise RuntimeError('Container did not become healthy')
   time.sleep(1)
 request=urllib.request.Request('http://127.0.0.1:8082/v1/search',data=json.dumps({'query':'containersentinel','mode':'fast'}).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=20) as response:
  data=json.load(response);assert data['results'] and data['results'][0]['url'].endswith('/container')
 print('Real container healthy; authenticated keyword query returned indexed fixture evidence.')
finally:subprocess.run(['docker','rm','--force',name],check=True,capture_output=True)
