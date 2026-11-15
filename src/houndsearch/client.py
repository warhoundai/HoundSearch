"""Thin HTTP SDK: explicit idempotency and caller-controlled keys, no paid retries."""
import uuid,time
from houndcrawler.client import Client as Transport
class Client:
 def __init__(self,endpoint='http://127.0.0.1:8082',*,api_key,**kwargs):self.transport=Transport(endpoint,api_key=api_key,**kwargs)
 def __enter__(self):return self
 def __exit__(self,*_):self.close()
 def close(self):self.transport.close()
 def request(self,method,path,**kwargs):return self.transport.request(method,path,**kwargs)
 def _submit(self,path,value,idempotency_key=None):return self.request('POST',path,json=value,headers={'Idempotency-Key':idempotency_key or uuid.uuid4().hex})
 def search(self,query,*,idempotency_key=None,**options):return self._submit('/v1/search',{'query':query,**options},idempotency_key)
 def contents(self,urls,**options):return self.request('POST','/v1/contents',json={'urls':urls,**options})
 def similar(self,url,*,idempotency_key=None,**options):return self._submit('/v1/find-similar',{'url':url,**options},idempotency_key)
 def answer(self,query,model_profile,*,idempotency_key=None,**options):return self._submit('/v1/answer',{'query':query,'model_profile':model_profile,**options},idempotency_key)
 def research(self,query,model_profile,*,idempotency_key=None,**options):return self._submit('/v1/research',{'query':query,'model_profile':model_profile,**options},idempotency_key)
 def job(self,jid):return self.request('GET','/v1/jobs/'+jid)
 def transition(self,jid,action,**budgets):return self.request('POST','/v1/jobs/'+jid+'/'+action,**({'json':budgets} if budgets else {}))
 def collection(self,name,visibility='public'):return self.request('POST','/v1/collections',json={'name':name,'visibility':visibility})
 def ingest(self,collection,urls=None,**options):return self.request('POST','/v1/collections/'+collection+'/ingest',json={**({'urls':urls} if urls else {}),**options})
 def ingestion(self,jid):return self.request('GET','/v1/ingestions/'+jid)
 def wait_ingestion(self,jid,timeout=900):
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   result=self.ingestion(jid)
   if result['status'] in ('completed','paused','cancelled'):return result
   time.sleep(.5)
  raise TimeoutError('Ingestion is still durable; poll its original ID')
