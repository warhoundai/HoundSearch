from datetime import datetime
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class Limits(Strict):
 max_requests:int=Field(40,ge=1,le=10000)
 max_tokens:int=Field(100000,ge=1024,le=10000000)
 max_cost_usd:float|None=Field(None,gt=0,le=10000)
 max_steps:int=Field(8,ge=1,le=100)
class Search(Strict):
 query:str=Field(min_length=1,max_length=2000)
 mode:Literal['fast','balanced','deep']='balanced'
 providers:list[str]=Field(default_factory=list,max_length=4)
 collections:list[str]=Field(default_factory=list,max_length=20)
 limit:int=Field(10,ge=1,le=100)
 include_domains:list[str]=Field(default_factory=list,max_length=100)
 exclude_domains:list[str]=Field(default_factory=list,max_length=100)
 start_published:datetime|None=None
 end_published:datetime|None=None
 language:str|None=Field(None,max_length=20)
 content_types:list[str]=Field(default_factory=list,max_length=10)
 include_contents:bool=False
 external_private_consent:bool=False
 budget:Limits=Field(default_factory=Limits)
 @model_validator(mode='after')
 def range_order(self):
  if self.start_published and self.end_published and self.start_published>self.end_published:raise ValueError('Publication date range is reversed')
  return self
class Contents(Strict):
 urls:list[str]=Field(min_length=1,max_length=20)
 max_characters:int=Field(24000,ge=1,le=120000)
 refresh:bool=False
class Similar(Search):
 url:str
 query:str='similar pages'
class Answer(Search):
 model_profile:str=Field(min_length=1,max_length=100)
 max_output_tokens:int=Field(2048,ge=128,le=8192)
class Collection(Strict):
 name:str=Field(min_length=1,max_length=100)
 visibility:Literal['public','private']='public'
class Ingest(Strict):
 urls:list[str]=Field(default_factory=list,max_length=10000)
 crawler_job:str|None=Field(None,pattern='^[0-9a-f]{32}$')
 crawler_profile:str|None=None
 max_pages:int=Field(1000,ge=1,le=100000)
 @model_validator(mode='after')
 def exactly_one(self):
  if bool(self.urls)==bool(self.crawler_job):raise ValueError('Supply URLs or an existing crawler job, exclusively')
  return self
