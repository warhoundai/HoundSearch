"""Explicit synthetic scale/relevance qualification; no open-web parity claim."""
import os,json,time,uuid,hashlib,platform
from pathlib import Path
import pytest
from houndsearch.store import vector
from houndsearch.retrieval import EMBED_MODEL,EMBED_REV,RERANK_MODEL,RERANK_REV

def test_100k_index_and_200_held_out_queries(store,settings):
 if os.environ.get('HOUNDSEARCH_SCALE')!='true':pytest.skip('Explicit scale qualification profile')
 cid=store.create_collection('alpha','Synthetic scale corpus','public')['id'];n=100000;started=time.monotonic()
 # Independent predictable relevance labels. Not presented as real-web relevance.
 with store.pool.connection() as c:
  with c.cursor().copy('COPY hsearch_documents(id,collection,tenant,url,title,body,hash,metadata,created) FROM STDIN') as copy:
   for i in range(n):
    text=f'Controlled document reference{i} about security topic{i%200}';copy.write_row((f'scale{i}',cid,'alpha',f'https://fixture.example/{i}',f'Reference {i}',text,hashlib.sha256(text.encode()).hexdigest(),'{}',time.time()))
  with c.cursor().copy('COPY hsearch_chunks(id,document,tenant,collection,start_pos,end_pos,body,search) FROM STDIN') as copy:
   for i in range(n):
    text=f'Controlled document reference{i} about security topic{i%200}';copy.write_row((f'chunk{i}',f'scale{i}','alpha',cid,0,len(text),text,"'reference"+str(i)+"':1 'security':2 'topic"+str(i%200)+"':3"))
  c.execute('ANALYZE hsearch_documents');c.execute('ANALYZE hsearch_chunks')
 indexed=time.monotonic();latencies=[];hits=0
 for q in range(200):
  i=(q*499+173)%n;t=time.monotonic();rows,_=store.candidates('alpha',f'reference{i}',[cid],limit=10);latencies.append((time.monotonic()-t)*1000);hits+=bool(rows and rows[0]['url']==f'https://fixture.example/{i}')
 with store.pool.connection() as c:
  assert c.execute('SELECT count(*) n FROM hsearch_documents WHERE collection=%s',(cid,)).fetchone()['n']==n
  size=c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
 report={'fixture':'100000 synthetic documents; 200 deterministic held-out document-ID queries','documents':n,'queries':200,'hit_at_1':hits/200,'p50_ms':sorted(latencies)[100],'p95_ms':sorted(latencies)[190],'index_seconds':indexed-started,'total_seconds':time.monotonic()-started,'database_bytes':size,'cpu_count':os.cpu_count(),'platform':platform.platform(),'commit':os.environ.get('GITHUB_SHA'),'semantic_scale':'separate profile','competitor_comparison':'not run'}
 Path('benchmark-results').mkdir(exist_ok=True);Path('benchmark-results/search-scale.json').write_text(json.dumps(report,indent=2));assert hits==200,report

def test_optional_real_semantic_profile(store,settings):
 if os.environ.get('HOUNDSEARCH_SEMANTIC_QUALIFY')!='true':pytest.skip('Explicit model download/pgvector profile')
 from houndsearch.store import Store
 from houndsearch.engine import Engine
 settings.semantic=True;settings.rerank=True;settings.model_cache=os.environ['HOUNDSEARCH_MODEL_CACHE'];db=Store(os.environ['HOUNDSEARCH_TEST_DATABASE_URL'],True)
 try:
  e=Engine(settings,db);cid=db.create_collection('alpha','Semantic fixture','public')['id']
  for i,text in enumerate(['An automobile engine needs regular servicing.','A gardener grows tomatoes in the soil.','HTTP session cookies should use secure flags.']):e.index('alpha',cid,{'url':f'https://fixture.example/semantic/{i}','data':{'text':text}})
  embedding=e.models.embed(['car maintenance'])[0];_,rows=db.candidates('alpha','car maintenance',[cid],embedding,10);assert rows and rows[0]['url'].endswith('/0')
  from houndsearch.retrieval import fuse
  ranked=e.models.rerank('car maintenance',fuse([('semantic',rows)]));assert ranked[0]['url'].endswith('/0')
  report={'embedding':EMBED_MODEL+'@'+EMBED_REV,'reranker':RERANK_MODEL+'@'+RERANK_REV,'documents':3,'semantic_top1_expected':True,'rerank_top1_expected':True,'commit':os.environ.get('GITHUB_SHA'),'limitations':'small fixture, not a 100k vector-scale or real-web relevance benchmark'}
  Path('benchmark-results').mkdir(exist_ok=True);Path('benchmark-results/semantic.json').write_text(json.dumps(report,indent=2))
 finally:db.close()
