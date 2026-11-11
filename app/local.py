"""Dependency-free local preview: same queries and dashboard as the container app."""
import argparse,json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from app.storage import initialize
from app.service import response
FRONTEND=Path(__file__).resolve().parents[1]/'frontend'
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(FRONTEND),**kwargs)
    def do_GET(self):
        url=urlsplit(self.path)
        if not url.path.startswith('/api/'): return super().do_GET()
        try:
            body=response(url.path,{k:v[-1] for k,v in parse_qs(url.query).items()});status=200
        except (ValueError,KeyError) as exc: body={'detail':str(exc)};status=400 if isinstance(exc,ValueError) else 404
        except Exception: body={'detail':'Database unavailable'};status=503
        payload=json.dumps(body).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8080);p.add_argument('--host',default='127.0.0.1');a=p.parse_args();initialize()
    print(f'Open http://{a.host}:{a.port}',flush=True);ThreadingHTTPServer((a.host,a.port),Handler).serve_forever()
