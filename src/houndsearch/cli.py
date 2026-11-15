import argparse,os,json,asyncio

def main():
 p=argparse.ArgumentParser(prog='houndsearch');sub=p.add_subparsers(dest='command',required=True)
 s=sub.add_parser('serve');s.add_argument('--host',default='127.0.0.1');s.add_argument('--port',type=int,default=8082);s.add_argument('--no-worker',action='store_true')
 sub.add_parser('worker');sub.add_parser('mcp');sub.add_parser('prepare-models')
 q=sub.add_parser('search');q.add_argument('query');q.add_argument('--provider',action='append',default=[])
 args=p.parse_args()
 if args.command=='prepare-models':
  from .retrieval import download_models
  download_models(os.environ.get('HOUNDSEARCH_MODEL_CACHE','./models'));return
 if args.command=='serve':
  import uvicorn
  from .api import create_app
  uvicorn.run(create_app(run_worker=not args.no_worker),host=args.host,port=args.port);return
 if args.command=='worker':
  from .config import Settings
  from .store import Store
  from .engine import Engine
  from .worker import Worker
  cfg=Settings().validate();db=Store(cfg.database,cfg.semantic)
  try:asyncio.run(Worker(Engine(cfg,db)).run())
  finally:db.close()
  return
 if args.command=='mcp':
  from .mcp import main as run
  run();return
 from .client import Client
 with Client(os.environ.get('HOUNDSEARCH_ENDPOINT','http://127.0.0.1:8082'),api_key=os.environ['HOUNDSEARCH_API_KEY']) as c:print(json.dumps(c.search(args.query,providers=args.provider),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
