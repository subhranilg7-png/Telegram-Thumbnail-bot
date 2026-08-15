import os
import hashlib, hmac, json, time
from urllib.parse import parse_qsl
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from renderer import render
from project_store import load_project, save_project
from exporters import export_png, export_pdf, export_pptx

ROOT=Path(__file__).resolve().parent
WEB=ROOT/'webapp'
app=FastAPI()
app.mount('/static',StaticFiles(directory=str(WEB)),name='static')

def validate_init_data(init_data: str):
    if not init_data:
        if os.environ.get("WEBAPP_DEV", "0") == "1": return None
        raise HTTPException(401, "Telegram WebApp authentication required")
    pairs=dict(parse_qsl(init_data, keep_blank_values=True))
    recv=pairs.pop("hash", None)
    if not recv: raise HTTPException(401,"Invalid initData")
    check="\n".join(f"{k}={v}" for k,v in sorted(pairs.items()))
    secret=hmac.new(b"WebAppData", os.environ.get("BOT_TOKEN","").encode(), hashlib.sha256).digest()
    calc=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc,recv): raise HTTPException(401,"Invalid initData signature")
    auth_date=int(pairs.get("auth_date","0"))
    if time.time()-auth_date>86400: raise HTTPException(401,"Expired initData")
    try: return json.loads(pairs.get("user","{}"))
    except Exception: return None

def auth(request):
    return validate_init_data(request.headers.get("X-Telegram-Init-Data",""))

@app.get('/')
async def index(): return FileResponse(WEB/'index.html')

@app.get('/api/project/{pid}')
async def get_project(pid, request: Request):
    auth(request)
    p=load_project(pid)
    if not p: raise HTTPException(404,'Project not found')
    return JSONResponse(p)

@app.put('/api/project/{pid}')
async def put_project(pid, payload:dict, request: Request):
    auth(request)
    p=load_project(pid)
    if not p: raise HTTPException(404,'Project not found')
    payload['id']=pid
    payload['files']=p['files']
    save_project(pid,payload)
    return payload

@app.post('/api/project/{pid}/reset')
async def reset_project(pid, request: Request):
    auth(request)
    p=load_project(pid)
    if not p: raise HTTPException(404,'Project not found')
    default=p['default_layout']; p['layout']=default
    save_project(pid,p); return p

@app.post('/api/render/{pid}')
async def render_project(pid,payload:dict|None=None, request: Request=None):
    if request: auth(request)
    p=load_project(pid)
    if not p: raise HTTPException(404,'Project not found')
    if payload: p.update({k:v for k,v in payload.items() if k not in ('id','files')}); save_project(pid,p)
    out=ROOT/'projects'/f'{pid}.png'; render(p).save(out,'PNG')
    return {'url':f'/media/{pid}.png'}

@app.get('/media/{name}')
async def media(name):
    path=ROOT/'projects'/name
    if not path.exists(): raise HTTPException(404,'Not found')
    return FileResponse(path)

@app.get('/api/export/{fmt}/{pid}')
async def export(fmt,pid, request: Request):
    auth(request)
    p=load_project(pid)
    if not p: raise HTTPException(404,'Project not found')
    ext={'png':'png','pdf':'pdf','pptx':'pptx'}.get(fmt)
    if not ext: raise HTTPException(400,'Unsupported format')
    out=ROOT/'projects'/f'{pid}_final.{ext}'
    {'png':export_png,'pdf':export_pdf,'pptx':export_pptx}[fmt](p,out)
    return FileResponse(out,filename=f"{p['title']}.{ext}",media_type={'png':'image/png','pdf':'application/pdf','pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation'}[fmt])
