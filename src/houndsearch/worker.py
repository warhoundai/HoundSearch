"""Lease-owned research and restart-safe crawler result ingestion."""
import asyncio,time,uuid,logging
import httpx
from psycopg.types.json import Jsonb
from houndcrawler.worker import Worker as CollectorWorker
from houndcrawler.errors import ScrapeError
from .models import Ingest
from houndcrawler.models import JobRequest,Options
class Worker:
 def __init__(self,engine):self.engine=engine;self.store=engine.store;self.stopping=False;self.collector=CollectorWorker(engine.collector)
 def ingest(self,tenant,cid,value:Ingest):
  self.store.collection(tenant,cid)
  if value.crawler_profile:
   p=self.engine.profiles.get(tenant,value.crawler_profile)
   if p['kind']!='crawler' or not value.crawler_job:raise ScrapeError('INVALID_REQUEST','Remote import requires a crawler profile and existing job',422)
  job=value.crawler_job
  if not job:job=self.store.create(tenant,JobRequest(kind='batch',urls=value.urls,options=Options(formats=['text'],render='never'),max_pages=value.max_pages))['id']
  elif not value.crawler_profile:self.store.get(tenant,job)
  with self.store.pool.connection() as c:return c.execute('INSERT INTO hsearch_ingestions(id,tenant,collection,crawler_job,remote,profile,created) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id,status,crawler_job',(uuid.uuid4().hex,tenant,cid,job,bool(value.crawler_profile),value.crawler_profile,time.time())).fetchone()
 def ingestion(self,tenant,jid):
  with self.store.pool.connection() as c:r=c.execute('SELECT * FROM hsearch_ingestions WHERE tenant=%s AND id=%s',(tenant,jid)).fetchone()
  if not r:raise ScrapeError('NOT_FOUND','Ingestion not found',404)
  return r
 async def ingest_once(self):
  with self.store.pool.connection() as c:
   r=c.execute("SELECT * FROM hsearch_ingestions WHERE status IN ('queued','running') AND (lease_until IS NULL OR lease_until<%s) ORDER BY created FOR UPDATE SKIP LOCKED LIMIT 1",(time.time(),)).fetchone()
   if not r:return
   lease=uuid.uuid4().hex;c.execute("UPDATE hsearch_ingestions SET lease=%s,lease_until=%s,status='running' WHERE id=%s",(lease,time.time()+120,r['id']))
  try:
   if r['remote']:
    p=self.engine.profiles.get(r['tenant'],r['profile'])
    async with httpx.AsyncClient(base_url=p['endpoint'].rstrip('/')+'/',headers={'Authorization':'Bearer '+p.get('key','')},timeout=30,trust_env=False) as client:
     a=await client.get('v1/jobs/'+r['crawler_job']);a.raise_for_status();job=a.json()
     b=await client.get('v1/jobs/'+r['crawler_job']+'/results',params={'cursor':r['cursor'],'limit':20});b.raise_for_status();payload=b.json();rows=payload.get('results',payload.get('data',[]))
   else:job=self.store.get(r['tenant'],r['crawler_job']);rows=self.store.results(r['tenant'],r['crawler_job'],r['cursor'],20)
   count=0;cursor=r['cursor']
   for row in rows:
    # Upserts are idempotent. A crash before cursor commit safely replays the batch.
    result=row.get('result',row)
    if not result.get('error') and await asyncio.to_thread(self.engine.index,r['tenant'],r['collection'],result):count+=1
    cursor=max(cursor,int(row['id']))
   status='completed' if not rows and job['status']=='completed' else 'paused' if not rows and job['status'] in ('paused','cancelled','partial') else 'running'
   with self.store.pool.connection() as c:c.execute('UPDATE hsearch_ingestions SET cursor=%s,indexed=indexed+%s,status=%s,lease=NULL,lease_until=%s WHERE id=%s AND lease=%s',(cursor,count,status,time.time()+.5,r['id'],lease))
  except Exception:
   with self.store.pool.connection() as c:c.execute("UPDATE hsearch_ingestions SET status='paused',reason='import_failed',lease=NULL,lease_until=NULL WHERE id=%s AND lease=%s",(r['id'],lease))
 async def research_once(self):
  item=self.store.claim_research()
  if not item:return False
  async def heartbeat():
   while True:
    await asyncio.sleep(15)
    if not self.store.heartbeat_search(item):return
  task=asyncio.create_task(heartbeat())
  try:await self.engine.research(item)
  except ScrapeError as error:
   try:self.store.checkpoint_search(item,self.store.job(item['tenant'],item['id'])['state'],'paused',error.code)
   except ScrapeError:pass
  except Exception:
   logging.getLogger(__name__).error('Research failed; pausing without exposing provider payloads')
   try:self.store.checkpoint_search(item,self.store.job(item['tenant'],item['id'])['state'],'paused','EXECUTION_FAILED')
   except ScrapeError:pass
  finally:task.cancel();await asyncio.gather(task,return_exceptions=True)
  return True
 async def run(self):
  collector=asyncio.create_task(self.collector.run());research=None;last_cleanup=0
  try:
   while not self.stopping:
    if time.monotonic()-last_cleanup>3600:self.store.expire_search(self.engine.settings.retention_days);last_cleanup=time.monotonic()
    if research is None or research.done():
     if research:await research
     research=asyncio.create_task(self.research_once())
    await self.ingest_once();await asyncio.sleep(.5)
  finally:
   self.collector.stopping=True;collector.cancel()
   if research:research.cancel()
   await asyncio.gather(collector,*([research] if research else []),return_exceptions=True)
