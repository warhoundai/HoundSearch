"""Deterministic fusion, filtering and optional pinned local neural retrieval."""
import hashlib,re,os
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from datetime import datetime,timezone
from houndcrawler.errors import ScrapeError
from houndcrawler.network import normalize_url
EMBED_MODEL='sentence-transformers/all-MiniLM-L6-v2'
EMBED_REV='1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
RERANK_MODEL='cross-encoder/ms-marco-MiniLM-L6-v2'
RERANK_REV='233902d25c440f23af6f7d6e94d2946bac0bee0a'
def canonical(url):
 p=urlsplit(normalize_url(url));pairs=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('gclid','fbclid')]
 return urlunsplit((p.scheme,p.netloc,p.path,urlencode(pairs),''))
def match_domain(url,pattern):
 p=urlsplit(url);pattern=pattern.lower().removeprefix('https://').removeprefix('http://');host,_,path=pattern.partition('/')
 matched=p.hostname==host or host.startswith('*.') and p.hostname.endswith(host[1:])
 return bool(matched and (not path or p.path=='/'+path.rstrip('/') or p.path.startswith('/'+path.rstrip('/')+'/')))
def permitted(result,request):
 url=result['url'];meta=result.get('metadata',{})
 if request.include_domains and not any(match_domain(url,p) for p in request.include_domains):return False
 if any(match_domain(url,p) for p in request.exclude_domains):return False
 if request.language and str(meta.get('language') or '').lower()!=request.language.lower():return False
 if request.content_types and meta.get('content_type') not in request.content_types:return False
 if request.start_published or request.end_published:
  try:date=datetime.fromisoformat(meta.get('published_at','').replace('Z','+00:00'));date=date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
  except (ValueError,TypeError):return False
  start=request.start_published;end=request.end_published
  if start and date<(start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start):return False
  if end and date>(end.replace(tzinfo=timezone.utc) if end.tzinfo is None else end):return False
 return True
def fuse(rankings):
 out={}
 for backend,rows in rankings:
  seen=set()
  for rank,row in enumerate(rows,1):
   url=canonical(row['url'])
   if url in seen:continue
   seen.add(url)
   if url not in out:
    out[url]={'id':hashlib.sha256(url.encode()).hexdigest(),'url':url,'title':str(row.get('title') or url)[:500],'snippet':str(row.get('snippet',row.get('body','')))[:2000],'metadata':row.get('metadata',{}),'score':0.0,'sources':[],'evidence':[]}
   value=out[url];value['score']+=1/(60+rank);value['sources'].append({'backend':backend,'rank':rank})
   if row.get('document') and row.get('id'):
    evidence={'chunk_id':row['id'],'document_id':row['document'],'start':row['start_pos'],'end':row['end_pos'],'sha256':row['hash'],'text':row['body']}
    if evidence not in value['evidence']:value['evidence'].append(evidence)
 return sorted(out.values(),key=lambda v:(-v['score'],v['url']))
def chunks(text,maximum=200,overlap=32):
 matches=list(re.finditer(r'\S+',text))
 return [{'start':matches[i].start(),'end':matches[min(i+maximum,len(matches))-1].end(),'text':text[matches[i].start():matches[min(i+maximum,len(matches))-1].end()]} for i in range(0,len(matches),maximum-overlap)]
class Models:
 def __init__(self,settings):
  self.enabled=settings.semantic;self.reranker=None;self.encoder=None
  if self.enabled:
   try:
    from sentence_transformers import SentenceTransformer,CrossEncoder
    self.encoder=SentenceTransformer(EMBED_MODEL,revision=EMBED_REV,cache_folder=settings.model_cache,local_files_only=True,device='cpu')
    if settings.rerank:self.reranker=CrossEncoder(RERANK_MODEL,revision=RERANK_REV,cache_folder=settings.model_cache,local_files_only=True,device='cpu')
   except (ImportError,OSError) as error:raise ScrapeError('MODELS_UNAVAILABLE','Install the semantic extra and run houndsearch prepare-models explicitly',503) from error
 def document_chunks(self,text):
  if not self.encoder:return chunks(text)
  spans=self.encoder.tokenizer(text,add_special_tokens=False,return_offsets_mapping=True)['offset_mapping'];out=[]
  for i in range(0,len(spans),188):
   first=spans[i][0];last=spans[min(i+220,len(spans))-1][1];out.append({'start':first,'end':last,'text':text[first:last]})
  return out
 def embed(self,texts):
  if not self.encoder:raise ScrapeError('SEMANTIC_DISABLED','Enable and install the local semantic profile',503)
  return self.encoder.encode(texts,normalize_embeddings=True,show_progress_bar=False,batch_size=32).tolist()
 def rerank(self,query,rows):
  if not self.reranker or not rows:return rows
  candidates=rows[:32];scores=self.reranker.predict([(query,str(v['title'])+'\n'+str(v['snippet'])) for v in candidates],show_progress_bar=False)
  for r,score in zip(candidates,scores):r['rerank_score']=float(score)
  return sorted(candidates,key=lambda v:(-v['rerank_score'],v['url']))+rows[32:]
def download_models(directory):
 from sentence_transformers import SentenceTransformer,CrossEncoder
 SentenceTransformer(EMBED_MODEL,revision=EMBED_REV,cache_folder=directory,device='cpu')
 CrossEncoder(RERANK_MODEL,revision=RERANK_REV,cache_folder=directory,device='cpu')
