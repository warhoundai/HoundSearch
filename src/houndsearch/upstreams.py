"""BYO search providers. One bounded request; paid calls are never retried silently."""
import json
import httpx
from houndcrawler.errors import ScrapeError
from .profiles import FIXED
async def search(profile,query,limit,budget):
 kind=profile['kind'];base=FIXED.get(kind,profile.get('endpoint','')).rstrip('/');headers={};params=None;body=None
 if kind=='exa':url=base+'/search';headers={'x-api-key':profile['key']};body={'query':query,'numResults':min(limit,100),'type':'auto'}
 elif kind=='brave':url=base+'/res/v1/web/search';headers={'X-Subscription-Token':profile['key']};params={'q':query,'count':min(limit,20)}
 elif kind=='serper':url=base+'/search';headers={'X-API-KEY':profile['key']};body={'q':query,'num':min(limit,100)}
 elif kind=='searxng':
  url=base+'/search';params={'q':query,'format':'json'}
  if profile.get('key'):headers={'Authorization':'Bearer '+profile['key']}
 else:raise ScrapeError('PROFILE_INVALID','Select a search provider profile',422)
 rid=budget.search_reserve(profile)
 try:
  async with httpx.AsyncClient(timeout=30,trust_env=False,follow_redirects=False) as client:
   async with client.stream('POST' if body is not None else 'GET',url,json=body,params=params,headers=headers) as response:
    if response.status_code>=300:raise ScrapeError('SEARCH_PROVIDER_FAILED','Search provider rejected the request; reservation retained',502)
    raw=bytearray()
    async for part in response.aiter_bytes():
     raw.extend(part)
     if len(raw)>4194304:raise ScrapeError('PROVIDER_RESPONSE_TOO_LARGE','Search response exceeds 4 MiB',502)
    data=json.loads(raw)
 except (httpx.HTTPError,ValueError):raise ScrapeError('SEARCH_PROVIDER_FAILED','Search response unavailable; reservation retained',502)
 rows=data.get('results',[]) if kind in ('exa','searxng') else data.get('web',{}).get('results',[]) if kind=='brave' else data.get('organic',[])
 if not isinstance(rows,list):raise ScrapeError('SEARCH_PROVIDER_FAILED','Invalid provider result list',502)
 budget.search_settle(rid)
 out=[]
 for row in rows[:limit]:
  if not isinstance(row,dict) or not row.get('url',row.get('link')):continue
  out.append({'url':row.get('url',row.get('link')),'title':row.get('title',''),'snippet':row.get('text',row.get('description',row.get('snippet',row.get('content','')))),'metadata':{'published_at':row.get('publishedDate',row.get('age',row.get('published_date'))),'language':row.get('language'),'content_type':row.get('content_type')},'evidence_kind':'provider_snippet'})
 return out
