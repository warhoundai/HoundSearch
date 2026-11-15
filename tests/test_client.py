import json,httpx
from houndsearch.client import Client
from houndsearch.mcp import dispatch

def test_sdk_uses_stable_idempotency_and_only_search_endpoints():
 calls=[]
 def handle(request):
  calls.append(request);return httpx.Response(200,json={'results':[]})
 with Client(api_key='caller-owned-fixture',transport=httpx.MockTransport(handle)) as client:
  client.search('q',idempotency_key='stable-operation')
  client.search('q',idempotency_key='stable-operation')
  assert not hasattr(client,'scrape')
  assert all(c.headers['Idempotency-Key']=='stable-operation' for c in calls)
  assert all(json.loads(c.content)=={'query':'q'} for c in calls)
  assert all(c.headers['Authorization']=='Bearer caller-owned-fixture' for c in calls)
  assert dispatch({'method':'tools/list'},client)['tools']
