"""Thin HTTP SDK: keys remain in caller-controlled configuration."""
import uuid
from houndcrawler.client import Client as Base
class Client(Base):
 def __init__(self,endpoint='http://127.0.0.1:8082',*,api_key,**kwargs):super().__init__(endpoint,api_key=api_key,**kwargs)
 def search(self,query,**options):return self.request('POST','/v1/search',json={'query':query,**options},headers={'Idempotency-Key':uuid.uuid4().hex})
 def contents(self,urls,**options):return self.request('POST','/v1/contents',json={'urls':urls,**options})
 def similar(self,url,**options):return self.request('POST','/v1/find-similar',json={'url':url,**options})
 def answer(self,query,model_profile,**options):return self.request('POST','/v1/answer',json={'query':query,'model_profile':model_profile,**options},headers={'Idempotency-Key':uuid.uuid4().hex})
 def research(self,query,model_profile,**options):return self.request('POST','/v1/research',json={'query':query,'model_profile':model_profile,**options},headers={'Idempotency-Key':uuid.uuid4().hex})
 def collection(self,name,visibility='public'):return self.request('POST','/v1/collections',json={'name':name,'visibility':visibility})
 def ingest(self,collection,urls=None,**options):return self.request('POST','/v1/collections/'+collection+'/ingest',json={**({'urls':urls} if urls else {}),**options})
