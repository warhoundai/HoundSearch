"""Instance configuration. Optional upstreams always belong to the operator/user."""
import os,json
from dataclasses import dataclass,field
from houndcrawler.config import Settings as CollectorSettings
@dataclass
class Settings(CollectorSettings):
 database:str=field(default_factory=lambda:os.environ.get('HOUNDSEARCH_DATABASE_URL',''))
 keys:dict=field(default_factory=lambda:json.loads(os.environ.get('HOUNDSEARCH_API_KEYS','{}')))
 encryption_key:str=field(default_factory=lambda:os.environ.get('HOUNDSEARCH_ENCRYPTION_KEY',''))
 storage:str=field(default_factory=lambda:os.environ.get('HOUNDSEARCH_STORAGE','./data'))
 semantic:bool=field(default_factory=lambda:os.environ.get('HOUNDSEARCH_SEMANTIC','false')=='true')
 rerank:bool=field(default_factory=lambda:os.environ.get('HOUNDSEARCH_RERANK','false')=='true')
 model_cache:str=field(default_factory=lambda:os.environ.get('HOUNDSEARCH_MODEL_CACHE','./models'))
 provider_profiles:dict=field(default_factory=lambda:json.loads(os.environ.get('HOUNDSEARCH_PROFILES','{}')))
 primary_provider:str=field(default_factory=lambda:os.environ.get('HOUNDSEARCH_PRIMARY_PROVIDER',''))
 trusted_endpoints:list=field(default_factory=lambda:json.loads(os.environ.get('HOUNDSEARCH_TRUSTED_ENDPOINTS','[]')))
 crawler_endpoint:str=field(default_factory=lambda:os.environ.get('HOUNDSEARCH_CRAWLER_ENDPOINT',''))
 vertex_project:str=''
 vertex_location:str='global'
 def validate(self):
  super().validate()
  if not self.encryption_key:raise ValueError('Configure an independent encryption key')
  from cryptography.fernet import Fernet
  Fernet(self.encryption_key.encode())
  if self.rerank and not self.semantic:raise ValueError('Reranking requires explicit semantic model enablement')
  return self
