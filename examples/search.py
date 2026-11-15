"""Query an already ingested local collection; no paid provider needed."""
import os
from houndsearch.client import Client
with Client(os.environ['HOUNDSEARCH_ENDPOINT'],api_key=os.environ['HOUNDSEARCH_API_KEY']) as client:
 print(client.search('security',mode='fast'))
