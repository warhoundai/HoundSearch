import pytest,httpx
from houndsearch import upstreams
from houndsearch.budget import Budget
from houndsearch.models import Search
from houndcrawler.errors import ScrapeError
@pytest.mark.asyncio
@pytest.mark.parametrize('kind,payload',[
 ('exa',{'results':[{'url':'https://example.com/a','title':'A','text':'source snippet'}]}),
 ('brave',{'web':{'results':[{'url':'https://example.com/a','description':'source snippet'}]}}),
 ('serper',{'organic':[{'link':'https://example.com/a','snippet':'source snippet'}]}),
 ('searxng',{'results':[{'url':'https://example.com/a','content':'source snippet'}]})])
async def test_provider_wire_contracts(store,settings,monkeypatch,kind,payload):
 item,_=store.new_job('alpha','search',Search(query='q').model_dump(mode='json'),status='running');budget=Budget(store,item,settings);calls=[];real=httpx.AsyncClient
 async def handle(request):
  calls.append(request)
  if kind=='exa':assert request.headers['x-api-key']=='user-owned-fixture'
  if kind=='brave':assert request.headers['X-Subscription-Token']=='user-owned-fixture'
  if kind=='serper':assert request.headers['X-API-KEY']=='user-owned-fixture'
  return httpx.Response(200,json=payload)
 monkeypatch.setattr(upstreams.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handle),**kw))
 rows=await upstreams.search({'kind':kind,'key':'user-owned-fixture','endpoint':'https://search.operator.example'},'q',10,budget)
 assert len(rows)==1 and rows[0]['snippet']=='source snippet';assert len(calls)==1 and budget.usage()['requests']==1
@pytest.mark.asyncio
async def test_paid_error_not_retried_and_reservation_retained(store,settings,monkeypatch):
 item,_=store.new_job('alpha','search',Search(query='q').model_dump(mode='json'),status='running');budget=Budget(store,item,settings);calls=[];real=httpx.AsyncClient
 async def handle(request):calls.append(request);return httpx.Response(429)
 monkeypatch.setattr(upstreams.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handle),**kw))
 with pytest.raises(ScrapeError):await upstreams.search({'kind':'exa','key':'user-owned-fixture','request_cost_usd':.01},'q',10,budget)
 assert len(calls)==1 and budget.usage()['unresolved_reservations']==1 and budget.usage()['usd_configured_or_reserved']==.01
