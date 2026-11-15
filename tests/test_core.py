import concurrent.futures,time
import pytest
from fastapi.testclient import TestClient
from houndcrawler.errors import ScrapeError
from houndsearch.api import create_app
from houndsearch.engine import Engine
from houndsearch.models import Search,Answer,Limits
from houndsearch.budget import Budget
from houndsearch.retrieval import canonical,chunks,match_domain,fuse,permitted

def index(eng,tenant,cid,url,text):return eng.index(tenant,cid,{'url':url,'data':{'text':text},'metadata':{'title':'Security handbook'},'content_type':'text/html','fetched_at':'2026-01-01T00:00:00Z'})
def budget(store,settings,cap=5):
 item,_=store.new_job('alpha','search',Search(query='security',budget=Limits(max_requests=cap)).model_dump(mode='json'),status='running');return Budget(store,item,settings)
def test_chunks_offsets_and_canonical():
 text=' '.join('word'+str(i) for i in range(600));parts=chunks(text)
 assert len(parts)==4 and all(text[p['start']:p['end']]==p['text'] for p in parts)
 assert canonical('https://example.com/a?x=1&utm_source=z#x')=='https://example.com/a?x=1'
 assert match_domain('https://a.example.com/docs/x','*.example.com/docs')
 assert not match_domain('https://evil-example.com/docs','*.example.com')
def test_fusion_and_filters():
 rows=fuse([('a',[{'url':'https://example.com/?utm_a=x'}]),('b',[{'url':'https://example.com/'}])]);assert len(rows)==1 and len(rows[0]['sources'])==2
 assert not permitted(rows[0],Search(query='q',exclude_domains=['example.com']))
 assert not permitted(rows[0],Search(query='q',language='en'))
def test_index_search_tenant_and_reindex(store,settings):
 e=Engine(settings,store);a=store.create_collection('alpha','Docs','public');b=store.create_collection('beta','Docs','public')
 index(e,'alpha',a['id'],'https://example.com/security','SQL injection authentication vulnerability')
 index(e,'beta',b['id'],'https://private.example.com/','SQL injection private sentinel')
 rows,_=store.candidates('alpha','SQL injection');assert rows and all(r['tenant']=='alpha' for r in rows)
 index(e,'alpha',a['id'],'https://example.com/security','Fresh cache replacement content')
 assert not store.candidates('alpha','injection')[0]
 assert store.candidates('alpha','replacement')[0]
 with pytest.raises(ScrapeError):index(e,'beta',a['id'],'https://example.com/','bad')
def test_api_auth_snapshots_idempotency(store,settings):
 e=Engine(settings,store);cid=store.create_collection('alpha','Docs','public')['id'];index(e,'alpha',cid,'https://example.com/','Session security cookies')
 with TestClient(create_app(settings,store=store,engine=e,run_worker=False)) as c:
  assert c.post('/v1/search',json={'query':'security'}).status_code==401
  h={'Authorization':'Bearer '+'a'*40,'Idempotency-Key':'once'}
  r=c.post('/v1/search',json={'query':'security'},headers=h);assert r.status_code==200,r.text
  out=r.json();assert len(out['results'])==1
  assert c.post('/v1/search',json={'query':'security'},headers=h).json()==out
  assert c.post('/v1/search',json={'query':'different'},headers=h).status_code==409
  assert c.get('/v1/search/results/'+out['snapshot'],headers={'Authorization':'Bearer '+'b'*40}).status_code==410
  assert c.get('/v1/jobs/'+out['execution_id'],headers={'Authorization':'Bearer '+'b'*40}).status_code==404
  assert c.post('/v1/search',json={'query':'x','unknown':1},headers=h).status_code==422
  assert c.post('/v1/search',content=b'x'*262145,headers=h).status_code==413
  assert c.get('/v1/openapi.json',headers=h).status_code==200
@pytest.mark.asyncio
async def test_private_consent_and_no_profile_fallback(store,settings):
 e=Engine(settings,store);cid=store.create_collection('alpha','Private','private')['id']
 with pytest.raises(ScrapeError,match='consent'):e.check_request('alpha',Search(query='x',collections=[cid],providers=['mine']))
 with pytest.raises(ScrapeError):e.profiles.get('alpha','mine')
def test_atomic_budget_concurrency(store,settings):
 b=budget(store,settings,7)
 def reserve(_):
  try:return b.reserve_call('fetch')
  except ScrapeError:return None
 with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:results=list(pool.map(reserve,range(30)))
 assert sum(bool(r) for r in results)==7
 assert b.usage()['requests']==7
 assert b.usage()['unresolved_reservations']==0
 assert b.usage()['warhound_fee_usd']==0
def test_unknown_usage_and_overrun_persist(store,settings):
 b=budget(store,settings);rid=b.reserve_call('model',100)
 b.settle(rid,{'provider_tokens':{}});assert b.usage()['tokens_used_or_reserved']==100 and b.usage()['unresolved_reservations']==1
 with pytest.raises(ScrapeError):b.settle(rid,{'provider_tokens':{'input_tokens':80,'output_tokens':30}})
 assert store.job('alpha',b.item['id'])['status']=='paused'
def test_cost_overrun_commits_pause(store,settings):
 b=budget(store,settings);rid=b.search_reserve({'request_cost_usd':.01})
 with pytest.raises(ScrapeError):b.search_settle(rid,.02)
 assert store.job('alpha',b.item['id'])['status']=='paused'
 assert b.usage()['usd_configured_or_reserved']==.02
def test_encrypted_profiles_and_endpoint_policy(store,settings):
 e=Engine(settings,store);e.profiles.put('alpha','own',{'kind':'exa','key':'local-fixture-key'})
 with store.pool.connection() as c:assert 'local-fixture-key' not in c.execute('SELECT ciphertext FROM hsearch_profiles').fetchone()['ciphertext']
 assert e.profiles.get('alpha','own')['key']=='local-fixture-key'
 with pytest.raises(ScrapeError):e.profiles.get('beta','own')
 with pytest.raises(ScrapeError):e.profiles.put('alpha','bad',{'kind':'openai','endpoint':'http://169.254.169.254','model':'test'})
 with pytest.raises(ScrapeError):e.check_request('alpha',Search(query='my local-fixture-key'))
def test_research_lease_recovery_and_cancel(store,settings):
 request=Answer(query='security',model_profile='mine').model_dump(mode='json');j,_=store.new_job('alpha','research',request);old=store.claim_research()
 with store.pool.connection() as c:c.execute('UPDATE hsearch_jobs SET lease_until=0 WHERE id=%s',(j['id'],))
 new=store.claim_research();assert new['lease']!=old['lease']
 with pytest.raises(ScrapeError):store.checkpoint_search(old,{'bad':True})
 store.checkpoint_search(new,{'cursor':1});store.search_transition('alpha',j['id'],'pause');store.search_transition('alpha',j['id'],'resume',{'max_requests':100})
 recovered=store.claim_research();assert recovered['state']['cursor']==1
 store.search_transition('alpha',j['id'],'cancel')
 with pytest.raises(ScrapeError):Budget(store,recovered,settings).reserve_call('fetch')
@pytest.mark.asyncio
async def test_answer_rejects_fabricated_quotes(store,settings):
 e=Engine(settings,store);cid=store.create_collection('alpha','Docs','public')['id'];index(e,'alpha',cid,'https://example.com/','Cookies require secure flags.')
 async def complete(*args,**kwargs):return {'claims':[{'text':'Supported','url':'https://example.com/','quote':'Cookies require secure flags.'},{'text':'Invented','url':'https://example.com/','quote':'This never appeared'}]},{}
 e.complete=complete;b=budget(store,settings,20);a=Answer(query='cookies',model_profile='test')
 out=await e.answer('alpha',a,b);assert len(out['claims'])==1 and out['answer']=='Supported'
 assert out['claims'][0]['citation']['start']==0
@pytest.mark.asyncio
async def test_no_evidence_abstains(store,settings):
 e=Engine(settings,store);out=await e.answer('alpha',Answer(query='nonexistent',model_profile='test'),budget(store,settings))
 assert out['abstained'] and out['answer'] is None
@pytest.mark.asyncio
async def test_worker_import_and_resume(store,settings):
 from houndsearch.worker import Worker
 from houndsearch.models import Ingest
 e=Engine(settings,store);w=Worker(e);cid=store.create_collection('alpha','Docs','public')['id'];i=w.ingest('alpha',cid,Ingest(urls=['https://example.com/']))
 # Seed an acquired fixture result into the normal durable crawl-result table.
 from psycopg.types.json import Jsonb
 with store.pool.connection() as c:
  c.execute('INSERT INTO hc_results(job,url,result) VALUES(%s,%s,%s)',(i['crawler_job'],'https://example.com/',Jsonb({'url':'https://example.com/','data':{'text':'Index this browser security content'}})))
  c.execute("UPDATE hc_jobs SET status='completed' WHERE id=%s",(i['crawler_job'],))
 await w.ingest_once()
 assert w.ingestion('alpha',i['id'])['indexed']==1 and store.candidates('alpha','browser')[0]
 with store.pool.connection() as c:c.execute('UPDATE hsearch_ingestions SET lease_until=0')
 await w.ingest_once();assert w.ingestion('alpha',i['id'])['status']=='completed'
@pytest.mark.asyncio
async def test_research_runs_through_real_model_reservations(store,settings,monkeypatch):
 from houndsearch.worker import Worker
 from houndcrawler.providers import Providers
 e=Engine(settings,store);cid=store.create_collection('alpha','Docs','public')['id'];index(e,'alpha',cid,'https://example.com/','Session security cookies use secure flags.')
 e.profiles.put('alpha','mine',{'kind':'gemini','key':'user-fixture-only','model':'fixture-model'})
 calls=[]
 async def complete(self,messages,max_output_tokens):
  calls.append(messages)
  value={'queries':['session security']} if 'Plan web research' in messages[0]['content'] else {'claims':[{'text':'Cookies use secure flags.','url':'https://example.com/','quote':'cookies use secure flags.'}]}
  return value,{'provider_tokens':{'input_tokens':25,'output_tokens':15,'reasoning_tokens':5}}
 monkeypatch.setattr(Providers,'_complete',complete)
 j,_=store.new_job('alpha','research',Answer(query='session security',model_profile='mine',budget=Limits(max_requests=10,max_steps=2)).model_dump(mode='json'))
 assert await Worker(e).research_once()
 out=store.job('alpha',j['id']);assert out['status']=='completed' and not out['result']['abstained'];assert len(calls)==2
 usage=Budget(store,out,settings).usage();assert usage['tokens_used_or_reserved']==80 and usage['requests']==4
