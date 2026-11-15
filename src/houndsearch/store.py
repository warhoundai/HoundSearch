"""Tenant-bound PostgreSQL index, durable research state and atomic reservations."""
import hashlib,json,time,uuid,math
from psycopg.types.json import Jsonb
from houndcrawler.database import Store as CollectorStore,fingerprint
from houndcrawler.errors import ScrapeError
SCHEMA='''
CREATE TABLE IF NOT EXISTS hsearch_collections(id text PRIMARY KEY,tenant text NOT NULL,name text NOT NULL,visibility text NOT NULL,created double precision NOT NULL);
CREATE INDEX IF NOT EXISTS hsearch_collection_tenant ON hsearch_collections(tenant);
CREATE TABLE IF NOT EXISTS hsearch_documents(id text PRIMARY KEY,collection text NOT NULL REFERENCES hsearch_collections ON DELETE CASCADE,tenant text NOT NULL,url text NOT NULL,title text NOT NULL,body text NOT NULL,hash text NOT NULL,metadata jsonb NOT NULL,created double precision NOT NULL,UNIQUE(collection,url));
CREATE TABLE IF NOT EXISTS hsearch_chunks(id text PRIMARY KEY,document text REFERENCES hsearch_documents ON DELETE CASCADE,tenant text NOT NULL,collection text NOT NULL,start_pos int NOT NULL,end_pos int NOT NULL,body text NOT NULL,search tsvector NOT NULL);
CREATE INDEX IF NOT EXISTS hsearch_chunks_fts ON hsearch_chunks USING gin(search);
CREATE INDEX IF NOT EXISTS hsearch_chunk_tenant_collection ON hsearch_chunks(tenant,collection);
CREATE TABLE IF NOT EXISTS hsearch_profiles(tenant text NOT NULL,name text NOT NULL,ciphertext text NOT NULL,PRIMARY KEY(tenant,name));
CREATE TABLE IF NOT EXISTS hsearch_jobs(id text PRIMARY KEY,tenant text NOT NULL,kind text NOT NULL,request jsonb NOT NULL,state jsonb NOT NULL DEFAULT '{}',status text NOT NULL,reason text,lease text,lease_until double precision,created double precision NOT NULL,updated double precision NOT NULL,idempotency text,request_hash text NOT NULL,result jsonb,UNIQUE(tenant,idempotency));
CREATE INDEX IF NOT EXISTS hsearch_jobs_claim ON hsearch_jobs(status,created);
CREATE TABLE IF NOT EXISTS hsearch_calls(id text PRIMARY KEY,job text REFERENCES hsearch_jobs ON DELETE CASCADE,kind text NOT NULL,tokens bigint NOT NULL,cost_nano bigint NOT NULL,settled boolean NOT NULL DEFAULT false,usage jsonb,created double precision NOT NULL);
CREATE TABLE IF NOT EXISTS hsearch_events(id bigserial PRIMARY KEY,job text REFERENCES hsearch_jobs ON DELETE CASCADE,kind text NOT NULL,value jsonb NOT NULL,created double precision NOT NULL);
CREATE TABLE IF NOT EXISTS hsearch_snapshots(id text PRIMARY KEY,tenant text NOT NULL,value jsonb NOT NULL,expires double precision NOT NULL);
CREATE TABLE IF NOT EXISTS hsearch_ingestions(id text PRIMARY KEY,tenant text NOT NULL,collection text REFERENCES hsearch_collections ON DELETE CASCADE,crawler_job text NOT NULL,remote boolean NOT NULL,profile text,cursor bigint NOT NULL DEFAULT 0,indexed int NOT NULL DEFAULT 0,status text NOT NULL DEFAULT 'queued',reason text,lease text,lease_until double precision,created double precision NOT NULL);
'''
VECTOR_SCHEMA='''CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS hsearch_vectors(id text PRIMARY KEY REFERENCES hsearch_chunks ON DELETE CASCADE,tenant text NOT NULL,embedding vector(384) NOT NULL);
CREATE INDEX IF NOT EXISTS hsearch_vectors_hnsw ON hsearch_vectors USING hnsw(embedding vector_cosine_ops);'''
class Store(CollectorStore):
 def __init__(self,url,semantic=False):
  super().__init__(url);self.semantic=semantic
  with self.pool.connection() as c:
   c.execute('SELECT pg_advisory_xact_lock(6741453456135)');c.execute(SCHEMA)
   if semantic:c.execute(VECTOR_SCHEMA)
 def collection(self,tenant,cid):
  with self.pool.connection() as c:r=c.execute('SELECT * FROM hsearch_collections WHERE tenant=%s AND id=%s',(tenant,cid)).fetchone()
  if not r:raise ScrapeError('NOT_FOUND','Collection not found',404)
  return r
 def create_collection(self,tenant,name,visibility):
  with self.pool.connection() as c:return c.execute('INSERT INTO hsearch_collections VALUES(%s,%s,%s,%s,%s) RETURNING *',(uuid.uuid4().hex,tenant,name,visibility,time.time())).fetchone()
 def collections(self,tenant):
  with self.pool.connection() as c:return c.execute('SELECT * FROM hsearch_collections WHERE tenant=%s ORDER BY created',(tenant,)).fetchall()
 def upsert_document(self,tenant,cid,url,title,body,metadata,chunks,embeddings=None):
  self.collection(tenant,cid);did=hashlib.sha256((tenant+'\0'+cid+'\0'+url).encode()).hexdigest();sha=hashlib.sha256(body.encode()).hexdigest()
  if embeddings is not None and (not self.semantic or len(embeddings)!=len(chunks)):raise ValueError('Embedding configuration mismatch')
  with self.pool.connection() as c:
   c.execute('SELECT id FROM hsearch_collections WHERE id=%s AND tenant=%s FOR UPDATE',(cid,tenant))
   old=c.execute('SELECT hash,title,metadata FROM hsearch_documents WHERE id=%s',(did,)).fetchone()
   if old and old['hash']==sha and old['title']==title and old['metadata']==metadata:return did
   c.execute('INSERT INTO hsearch_documents VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET title=excluded.title,body=excluded.body,hash=excluded.hash,metadata=excluded.metadata,created=excluded.created',(did,cid,tenant,url,title,body,sha,Jsonb(metadata),time.time()))
   c.execute('DELETE FROM hsearch_chunks WHERE document=%s',(did,))
   for i,chunk in enumerate(chunks):
    key=hashlib.sha256((did+':'+str(i)).encode()).hexdigest();text=chunk['text']
    c.execute("INSERT INTO hsearch_chunks VALUES(%s,%s,%s,%s,%s,%s,%s,setweight(to_tsvector('english',%s),'A')||setweight(to_tsvector('english',%s),'B'))",(key,did,tenant,cid,chunk['start'],chunk['end'],text,title,text))
    if embeddings is not None:c.execute('INSERT INTO hsearch_vectors VALUES(%s,%s,%s::vector)',(key,tenant,vector(embeddings[i])))
  return did
 def candidates(self,tenant,query,collections=(),embedding=None,limit=100):
  restriction=' AND c.collection=ANY(%s)' if collections else '';args=[tenant,query]+([list(collections)] if collections else [])+[limit]
  with self.pool.connection() as c:
   rows=c.execute("SELECT c.*,d.url,d.title,d.hash,d.metadata,ts_rank_cd(c.search,websearch_to_tsquery('english',%s)) AS rank FROM hsearch_chunks c JOIN hsearch_documents d ON d.id=c.document WHERE c.tenant=%s AND c.search@@websearch_to_tsquery('english',%s)"+restriction+' ORDER BY rank DESC,c.id LIMIT %s',[query,*args]).fetchall()
   lexical=[{**r,'rank':float(r['rank'])} for r in rows];semantic=[]
   if embedding is not None and self.semantic:
    # Restrict tenant before joining content; pgvector cannot return another tenant's evidence.
    sql='SELECT c.*,d.url,d.title,d.hash,d.metadata,1-(v.embedding<=>%s::vector) AS rank FROM hsearch_vectors v JOIN hsearch_chunks c ON c.id=v.id JOIN hsearch_documents d ON d.id=c.document WHERE v.tenant=%s'+restriction+' ORDER BY v.embedding<=>%s::vector,c.id LIMIT %s'
    semantic=c.execute(sql,[vector(embedding),tenant]+([list(collections)] if collections else [])+[vector(embedding),limit]).fetchall()
  return lexical,semantic
 def document(self,tenant,url,collections=()):
  with self.pool.connection() as c:return c.execute('SELECT * FROM hsearch_documents WHERE tenant=%s AND url=%s'+(' AND collection=ANY(%s)' if collections else '')+' ORDER BY created DESC LIMIT 1',[tenant,url]+([list(collections)] if collections else [])).fetchone()
 def new_job(self,tenant,kind,request,idempotency=None,status='queued'):
  sha=fingerprint({'kind':kind,'request':request});now=time.time()
  with self.pool.connection() as c:
   r=c.execute('INSERT INTO hsearch_jobs(id,tenant,kind,request,status,created,updated,idempotency,request_hash) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(tenant,idempotency) DO NOTHING RETURNING *',(uuid.uuid4().hex,tenant,kind,Jsonb(request),status,now,now,idempotency,sha)).fetchone()
   fresh=bool(r)
   if not r:r=c.execute('SELECT * FROM hsearch_jobs WHERE tenant=%s AND idempotency=%s',(tenant,idempotency)).fetchone()
   if r['request_hash']!=sha:raise ScrapeError('IDEMPOTENCY_CONFLICT','Key already used for another request',409)
   if fresh:self.search_event(c,r['id'],'created',{})
   return r,fresh
 def job(self,tenant,jid):
  with self.pool.connection() as c:r=c.execute('SELECT * FROM hsearch_jobs WHERE tenant=%s AND id=%s',(tenant,jid)).fetchone()
  if not r:raise ScrapeError('NOT_FOUND','Search execution not found',404)
  return r
 def claim_research(self):
  now=time.time()
  with self.pool.connection() as c:
   c.execute("UPDATE hsearch_jobs SET status='queued',lease=NULL WHERE kind='research' AND status='running' AND lease_until<%s",(now,))
   r=c.execute("SELECT * FROM hsearch_jobs WHERE kind='research' AND status='queued' ORDER BY created FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
   if not r:return None
   lease=uuid.uuid4().hex;c.execute("UPDATE hsearch_jobs SET status='running',lease=%s,lease_until=%s,updated=%s WHERE id=%s",(lease,now+120,now,r['id']));r.update(status='running',lease=lease,lease_until=now+120);return r
 def heartbeat_search(self,item):
  with self.pool.connection() as c:return bool(c.execute("UPDATE hsearch_jobs SET lease_until=%s WHERE id=%s AND lease=%s AND status='running' RETURNING id",(time.time()+120,item['id'],item['lease'])).fetchone())
 def checkpoint_search(self,item,state,status='running',reason=None,result=None):
  with self.pool.connection() as c:
   r=c.execute("UPDATE hsearch_jobs SET state=%s,status=%s,reason=%s,result=%s,updated=%s WHERE id=%s AND status='running' AND (lease=%s OR lease IS NULL) RETURNING id",(Jsonb(state),status,reason,Jsonb(result),time.time(),item['id'],item.get('lease'))).fetchone()
   if not r:raise ScrapeError('STALE_LEASE','Search execution no longer active',409)
   self.search_event(c,item['id'],status,{'reason':reason})
 def search_transition(self,tenant,jid,action,updates=None):
  with self.pool.connection() as c:
   r=c.execute('SELECT * FROM hsearch_jobs WHERE id=%s AND tenant=%s FOR UPDATE',(jid,tenant)).fetchone()
   if not r:raise ScrapeError('NOT_FOUND','Execution not found',404)
   if r['kind']!='research':raise ScrapeError('INVALID_STATE','Only research jobs are resumable',409)
   if action=='resume':
    if r['status'] not in ('paused','cancelled'):raise ScrapeError('INVALID_STATE','Execution is not resumable',409)
    request=r['request'];request['budget'].update(updates or {});status='queued'
   else:
    if r['status'] not in ('queued','running','paused'):raise ScrapeError('INVALID_STATE','Execution is terminal',409)
    request=r['request'];status={'pause':'paused','cancel':'cancelled'}[action]
   c.execute('UPDATE hsearch_jobs SET status=%s,request=%s,lease=NULL,updated=%s WHERE id=%s',(status,Jsonb(request),time.time(),jid));self.search_event(c,jid,action,{});return {**r,'status':status,'request':request}
 def search_event(self,c,jid,kind,value):c.execute('INSERT INTO hsearch_events(job,kind,value,created) VALUES(%s,%s,%s,%s)',(jid,kind,Jsonb(value),time.time()))
 def search_events(self,tenant,jid,after=0):
  self.job(tenant,jid)
  with self.pool.connection() as c:return c.execute('SELECT * FROM hsearch_events WHERE job=%s AND id>%s ORDER BY id LIMIT 100',(jid,after)).fetchall()
 def snapshot(self,tenant,value):
  sid=uuid.uuid4().hex
  with self.pool.connection() as c:c.execute('INSERT INTO hsearch_snapshots VALUES(%s,%s,%s,%s)',(sid,tenant,Jsonb(value),time.time()+900))
  return sid
 def read_snapshot(self,tenant,sid):
  with self.pool.connection() as c:r=c.execute('SELECT value FROM hsearch_snapshots WHERE tenant=%s AND id=%s AND expires>%s',(tenant,sid,time.time())).fetchone()
  if not r:raise ScrapeError('SNAPSHOT_EXPIRED','Result snapshot is missing or expired',410)
  return r['value']
 def expire_search(self,days=7):
  with self.pool.connection() as c:
   c.execute('DELETE FROM hsearch_snapshots WHERE expires<%s',(time.time(),));c.execute("DELETE FROM hsearch_jobs WHERE updated<%s AND status IN ('completed','cancelled')",(time.time()-days*86400,))
def vector(values):
 if len(values)!=384 or any(not isinstance(v,(float,int)) or not math.isfinite(v) for v in values):raise ValueError('Expected 384 finite embedding dimensions')
 return '['+','.join(str(float(v)) for v in values)+']'
