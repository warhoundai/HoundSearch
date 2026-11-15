"""Authenticated REST API. Operator keys identify isolated tenants."""
import asyncio,json
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request,Query
from fastapi.responses import JSONResponse,Response,StreamingResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from houndcrawler.errors import ScrapeError
from .config import Settings
from .store import Store
from .engine import Engine
from .worker import Worker
from .models import Search,Contents,Similar,Answer,Collection,Ingest,Limits
from .budget import Budget
from . import __version__
def create_app(settings=None,*,store=None,engine=None,run_worker=True):
 cfg=(settings or Settings()).validate();db=store or Store(cfg.database,cfg.semantic);eng=engine or Engine(cfg,db);worker=Worker(eng)
 @asynccontextmanager
 async def lifespan(app):
  task=asyncio.create_task(worker.run()) if run_worker else None
  try:yield
  finally:
   worker.stopping=True
   if task:task.cancel();await asyncio.gather(task,return_exceptions=True)
   if store is None:db.close()
 app=FastAPI(title='HoundSearch',version=__version__,lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None);app.state.engine=eng;app.state.store=db
 def error(e):return JSONResponse({'error':{'code':e.code,'message':e.message,'retryable':e.retryable}},status_code=e.status)
 @app.middleware('http')
 async def auth(request,call_next):
  try:
   if request.url.path!='/health':request.state.tenant=cfg.tenant(request.headers.get('authorization',''))
   if request.method in ('POST','PUT','PATCH'):
    body=bytearray()
    async for part in request.stream():
     body.extend(part)
     if len(body)>262144:raise ScrapeError('BODY_TOO_LARGE','Request exceeds 256 KiB',413)
    request._body=bytes(body)
   response=await call_next(request);response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'});return response
  except ScrapeError as e:return error(e)
 @app.exception_handler(ScrapeError)
 async def known(request,e):return error(e)
 @app.exception_handler(RequestValidationError)
 @app.exception_handler(ValidationError)
 async def invalid(request,e):return JSONResponse({'error':{'code':'INVALID_REQUEST','message':'Request failed validation'}},status_code=422)
 @app.get('/health')
 async def health():
  with db.pool.connection() as c:c.execute('SELECT 1')
  return {'status':'ok','version':__version__}
 @app.get('/v1/openapi.json')
 async def openapi():return app.openapi()
 @app.get('/v1/capabilities')
 async def capabilities():return {'version':__version__,'release':'measured-preview','keyword':True,'semantic':cfg.semantic,'rerank':cfg.rerank,'upstreams':['exa','brave','serper','searxng'],'answers':'explicit BYO model profile','research':True,'hosted_service':False,'telemetry':False}
 async def execution(kind,value,request,fn):
  tenant=request.state.tenant;eng.check_request(tenant,value)
  item,fresh=db.new_job(tenant,kind,value.model_dump(mode='json'),request.headers.get('idempotency-key'),status='running');budget=Budget(db,item,cfg)
  if not fresh:
   if item['status']=='completed':return item['result']
   raise ScrapeError('EXECUTION_EXISTS','Execution already exists; inspect its status',409)
  try:
   result=await fn(tenant,value,budget);result['execution_id']=item['id'];result['usage']=budget.usage()
   if 'results' in result:
    sid=db.snapshot(tenant,result['results']);result['snapshot']=sid;result['next']=None
   db.checkpoint_search(item,{},'completed',result=result);return result
  except ScrapeError as e:
   if db.job(tenant,item['id'])['status']=='running':db.checkpoint_search(item,{},'paused',e.code)
   raise
  except Exception:
   db.checkpoint_search(item,{},'paused','EXECUTION_FAILED');raise ScrapeError('EXECUTION_FAILED','Execution failed; inspect status before retrying',502)
 @app.post('/v1/search')
 async def search(value:Search,request:Request):return await execution('search',value,request,eng.search)
 @app.get('/v1/search/results/{snapshot}')
 async def page(snapshot:str,request:Request,offset:int=Query(0,ge=0),limit:int=Query(10,ge=1,le=100)):
  rows=db.read_snapshot(request.state.tenant,snapshot);end=offset+limit
  return {'results':rows[offset:end],'next_offset':end if end<len(rows) else None,'snapshot':snapshot}
 @app.post('/v1/find-similar')
 async def similar(value:Similar,request:Request):return await execution('similar',value,request,eng.similar)
 @app.post('/v1/answer')
 async def answer(value:Answer,request:Request):return await execution('answer',value,request,eng.answer)
 @app.post('/v1/contents')
 async def contents(value:Contents,request:Request):
  results=[]
  for url in value.urls:
   try:results.append(await eng.content(request.state.tenant,url,value.max_characters,value.refresh))
   except ScrapeError as e:results.append({'url':url,'error':{'code':e.code,'message':e.message}})
  return {'results':results}
 @app.post('/v1/collections',status_code=201)
 async def collection(value:Collection,request:Request):return db.create_collection(request.state.tenant,value.name,value.visibility)
 @app.get('/v1/collections')
 async def collections(request:Request):return {'collections':db.collections(request.state.tenant)}
 @app.delete('/v1/collections/{cid}',status_code=204)
 async def delete_collection(cid:str,request:Request):
  db.collection(request.state.tenant,cid)
  with db.pool.connection() as c:c.execute('DELETE FROM hsearch_collections WHERE tenant=%s AND id=%s',(request.state.tenant,cid))
  return Response(status_code=204)
 @app.post('/v1/collections/{cid}/ingest',status_code=202)
 async def ingest(cid:str,value:Ingest,request:Request):return worker.ingest(request.state.tenant,cid,value)
 @app.get('/v1/ingestions/{jid}')
 async def ingestion(jid:str,request:Request):
  row=worker.ingestion(request.state.tenant,jid);return {k:row[k] for k in ('id','collection','crawler_job','cursor','indexed','status','reason')}
 @app.post('/v1/ingestions/{jid}/{action}')
 async def ingest_action(jid:str,action:str,request:Request):
  if action not in ('pause','resume','cancel'):raise ScrapeError('NOT_FOUND','Unknown action',404)
  r=worker.ingestion(request.state.tenant,jid)
  if not r['remote']:
   job=db.get(request.state.tenant,r['crawler_job'])
   if job['status']!='completed':db.transition(request.state.tenant,r['crawler_job'],action)
  status={'pause':'paused','resume':'queued','cancel':'cancelled'}[action]
  with db.pool.connection() as c:c.execute('UPDATE hsearch_ingestions SET status=%s,lease=NULL,lease_until=NULL WHERE tenant=%s AND id=%s',(status,request.state.tenant,jid))
  return {'id':jid,'status':status}
 @app.put('/v1/profiles/{name}')
 async def profile(name:str,request:Request):return eng.profiles.put(request.state.tenant,name,await request.json())
 @app.delete('/v1/profiles/{name}',status_code=204)
 async def delete_profile(name:str,request:Request):eng.profiles.delete(request.state.tenant,name);return Response(status_code=204)
 @app.post('/v1/research',status_code=202)
 async def research(value:Answer,request:Request):
  eng.check_request(request.state.tenant,value);eng.model(request.state.tenant,value.model_profile)
  row,_=db.new_job(request.state.tenant,'research',value.model_dump(mode='json'),request.headers.get('idempotency-key'));return {'id':row['id'],'status':row['status']}
 @app.get('/v1/jobs/{jid}')
 async def job(jid:str,request:Request):
  row=db.job(request.state.tenant,jid);budget=Budget(db,row,cfg);return {**{k:row[k] for k in ('id','kind','status','reason','state','result','created','updated')},'usage':budget.usage()}
 @app.post('/v1/jobs/{jid}/{action}')
 async def transition(jid:str,action:str,request:Request):
  if action not in ('pause','resume','cancel'):raise ScrapeError('NOT_FOUND','Unknown action',404)
  raw=await request.body();updates=Limits.model_validate_json(raw).model_dump() if raw else None
  row=db.search_transition(request.state.tenant,jid,action,updates);return {'id':jid,'status':row['status']}
 @app.get('/v1/jobs/{jid}/events')
 async def events(jid:str,request:Request,after:int=Query(0,ge=0)):
  db.job(request.state.tenant,jid)
  async def stream():
   cursor=after
   while not await request.is_disconnected():
    for event in db.search_events(request.state.tenant,jid,cursor):
     cursor=event['id'];yield 'id: '+str(cursor)+'\nevent: '+event['kind']+'\ndata: '+json.dumps(event['value'])+'\n\n'
    if db.job(request.state.tenant,jid)['status'] in ('completed','paused','cancelled'):break
    yield ': heartbeat\n\n';await asyncio.sleep(1)
  return StreamingResponse(stream(),media_type='text/event-stream')
 default_openapi=app.openapi
 def secured_openapi():
     schema=default_openapi();schema.setdefault('components',{}).setdefault('securitySchemes',{})['InstanceKey']={'type':'http','scheme':'bearer'}
     for path,methods in schema.get('paths',{}).items():
         if path not in ('/health','/','/sdk.mjs') and not path.startswith('/assets/'):
             for operation in methods.values():
                 if isinstance(operation,dict):operation['security']=[{'InstanceKey':[]}]
     return schema
 app.openapi=secured_openapi
 return app
