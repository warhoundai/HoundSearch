import os,pytest
from cryptography.fernet import Fernet
from houndsearch.store import Store
from houndsearch.config import Settings
@pytest.fixture
def store():
 url=os.environ.get('HOUNDSEARCH_TEST_DATABASE_URL')
 if not url:pytest.skip('Set HOUNDSEARCH_TEST_DATABASE_URL to isolated houndsearch_test')
 if not url.split('?',1)[0].endswith('/houndsearch_test'):raise RuntimeError('Refusing non-test database')
 db=Store(url)
 with db.pool.connection() as c:
  c.execute('TRUNCATE hsearch_collections,hsearch_jobs,hsearch_profiles,hsearch_snapshots,hc_jobs,hc_cache,hc_artifacts RESTART IDENTITY CASCADE')
 yield db;db.close()
@pytest.fixture
def settings(store,tmp_path):return Settings(database='test',keys={'alpha':'a'*40,'beta':'b'*40},storage=str(tmp_path),encryption_key=Fernet.generate_key().decode(),workers=2)
