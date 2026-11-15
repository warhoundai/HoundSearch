"""Execution-wide model/search reservations; unknown outcomes keep their reservation."""
import json,time,uuid
from decimal import Decimal
from psycopg.types.json import Jsonb
from houndcrawler.errors import ScrapeError
from houndcrawler.pricing import reserve_cost
class Budget:
 def __init__(self,store,item,settings):self.store=store;self.item=item;self.settings=settings
 def active(self):
  job=self.store.job(self.item['tenant'],self.item['id'])
  if job['status']!='running' or self.item.get('lease') and job['lease']!=self.item['lease']:raise ScrapeError('STALE_LEASE','Execution is paused, cancelled or recovered',409)
  return job
 def reserve_call(self,kind,tokens=0,cost=0):
  rid=uuid.uuid4().hex
  with self.store.pool.connection() as c:
   j=c.execute('SELECT * FROM hsearch_jobs WHERE id=%s AND tenant=%s FOR UPDATE',(self.item['id'],self.item['tenant'])).fetchone()
   if not j or j['status']!='running' or self.item.get('lease') and j['lease']!=self.item['lease']:raise ScrapeError('STALE_LEASE','Execution is no longer active',409)
   cap=j['request']['budget'];totals=c.execute('SELECT count(*) AS requests,COALESCE(sum(tokens),0) AS tokens,COALESCE(sum(cost_nano),0) AS cost FROM hsearch_calls WHERE job=%s',(j['id'],)).fetchone()
   if totals['requests']+1>cap['max_requests'] or totals['tokens']+tokens>cap['max_tokens']:raise ScrapeError('EXECUTION_BUDGET','Execution request/token budget exhausted',402)
   if cap.get('max_cost_usd') is not None and totals['cost']+cost>int(Decimal(str(cap['max_cost_usd']))*1000000000):raise ScrapeError('COST_BUDGET','Execution dollar budget exhausted',402)
   c.execute('INSERT INTO hsearch_calls(id,job,kind,tokens,cost_nano,created) VALUES(%s,%s,%s,%s,%s,%s)',(rid,j['id'],kind,tokens,cost,time.time()))
  if kind=='fetch':
   with self.store.pool.connection() as c:c.execute('UPDATE hsearch_calls SET settled=true WHERE id=%s',(rid,))
  return rid
 def reserve(self,messages,output):
  input_ceiling=len(json.dumps(messages,ensure_ascii=False).encode())+4096
  cap=self.item['request']['budget'].get('max_cost_usd');cost=reserve_cost(self.settings,input_ceiling,output) if cap is not None else 0
  return self.reserve_call('model',input_ceiling+output,cost)
 def settle(self,rid,usage):
  counters=usage.get('provider_tokens',{});values=[counters.get('input_tokens'),counters.get('output_tokens')]
  actual=sum(values) if all(type(v) is int and v>=0 for v in values) else None
  cost=usage.get('cost_nano_usd');violation=False
  with self.store.pool.connection() as c:
   c.execute('SELECT id FROM hsearch_jobs WHERE id=%s FOR UPDATE',(self.item['id'],))
   row=c.execute('SELECT * FROM hsearch_calls WHERE id=%s FOR UPDATE',(rid,)).fetchone()
   if not row or row['settled']:return
   violation=actual is not None and actual>row['tokens'] or row['cost_nano']>0 and cost is not None and cost>row['cost_nano']
   c.execute('UPDATE hsearch_calls SET tokens=%s,cost_nano=%s,settled=%s,usage=%s WHERE id=%s',(actual if actual is not None else row['tokens'],cost if row['cost_nano'] and cost is not None else row['cost_nano'],actual is not None,Jsonb(usage),rid))
   if violation:c.execute("UPDATE hsearch_jobs SET status='paused',reason='provider_limit_violation' WHERE id=%s",(self.item['id'],))
  if violation:raise ScrapeError('PROVIDER_LIMIT_VIOLATION','Provider exceeded reserved usage; execution paused',502)
 def search_reserve(self,profile):
  cap=self.item['request']['budget'].get('max_cost_usd')
  if cap is not None and profile.get('request_cost_usd') is None:raise ScrapeError('PRICING_UNAVAILABLE','Dollar budgets require your configured search request price',503)
  return self.reserve_call('search',cost=int(Decimal(str(profile.get('request_cost_usd',0)))*1000000000))
 def search_settle(self,rid,actual_cost=None):
  violation=False
  with self.store.pool.connection() as c:
   c.execute('SELECT id FROM hsearch_jobs WHERE id=%s FOR UPDATE',(self.item['id'],))
   row=c.execute('SELECT * FROM hsearch_calls WHERE id=%s FOR UPDATE',(rid,)).fetchone()
   if not row or row['settled']:return
   cost=int(Decimal(str(actual_cost))*1000000000) if actual_cost is not None else row['cost_nano']
   c.execute('UPDATE hsearch_calls SET settled=true,cost_nano=%s,usage=%s WHERE id=%s',(cost,Jsonb({'cost_status':'provider_reported' if actual_cost is not None else 'operator_configured_or_unknown'}),rid))
   if row['cost_nano'] and cost>row['cost_nano']:
    c.execute("UPDATE hsearch_jobs SET status='paused',reason='provider_limit_violation' WHERE id=%s",(self.item['id'],));violation=True
  if violation:raise ScrapeError('PROVIDER_LIMIT_VIOLATION','Search provider exceeded configured cost; execution paused',502)
 def usage(self):
  with self.store.pool.connection() as c:r=c.execute('SELECT count(*) requests,COALESCE(sum(tokens),0) tokens,COALESCE(sum(cost_nano),0) cost,count(*) FILTER(WHERE NOT settled) unresolved FROM hsearch_calls WHERE job=%s',(self.item['id'],)).fetchone()
  return {'requests':r['requests'],'tokens_used_or_reserved':int(r['tokens']),'usd_configured_or_reserved':int(r['cost'])/1000000000,'unresolved_reservations':r['unresolved'],'warhound_fee_usd':0}
