from fastapi import FastAPI, HTTPException, Request
from app.storage import initialize
from app.service import response
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    initialize();yield
app=FastAPI(title='Multi-Store Sales Analytics',version='1.0.0',lifespan=lifespan)

@app.get('/api/{resource}')
def get_resource(resource:str,request:Request):
    try: return response('/api/'+resource,dict(request.query_params))
    except ValueError as exc: raise HTTPException(422,str(exc))
    except KeyError: raise HTTPException(404,'Unknown endpoint')
