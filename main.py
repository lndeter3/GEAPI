import uuid,time,threading,json
from contextlib import asynccontextmanager
from fastapi import FastAPI,Query,Request,UploadFile,File,Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse,HTMLResponse,StreamingResponse
from core.client import GeminiClient
from core.session import SessionState

_lock=threading.Lock()
_sessions:dict[str,SessionState]={}
_uploads:dict[str,list]={}
_client:GeminiClient|None=None
_last_cleanup=0.0

def get_client()->GeminiClient:
 global _client
 if _client is None:_client=GeminiClient()
 return _client

def cleanup_sessions():
 global _last_cleanup
 now=time.time()
 if now-_last_cleanup<3600:return
 _last_cleanup=now
 cutoff=now-7200
 dead=[k for k,v in _sessions.items() if getattr(v,"lqt",0)>0 and v.lqt<cutoff]
 for k in dead:
  _sessions.pop(k,None)
  _uploads.pop(k,None)

def get_state(sid:str)->SessionState:
 with _lock:
  cleanup_sessions()
  if sid not in _sessions:_sessions[sid]=SessionState()
  return _sessions[sid]

def sse(event:str,data)->str:
 if isinstance(data,(dict,list)):data=json.dumps(data,ensure_ascii=False)
 out=f"event: {event}\n"
 s=str(data).replace("\r","")
 for line in s.split("\n"):out+=f"data: {line}\n"
 out+="\n"
 return out

def chunk_text(text:str,chunk_size:int=220):
 i=0;n=len(text)
 while i<n:
  yield text[i:i+chunk_size]
  i+=chunk_size

def pop_files(sid:str)->list:
 with _lock:
  files=_uploads.get(sid,[])
  _uploads[sid]=[]
  return files

@asynccontextmanager
async def lifespan(app:FastAPI):
 try:
  c=get_client()
  tmp=SessionState()
  c.bootstrap(tmp)
  print("[STARTUP] bootstrap ok",flush=True)
 except Exception as e:
  print(f"[STARTUP WARN] {e}",flush=True)
 yield

app=FastAPI(title="Gemini API",version="2.1",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

@app.get("/",response_class=HTMLResponse)
async def root(request:Request):
 base=str(request.base_url).rstrip("/")
 return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gemini API</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:860px;margin:40px auto;padding:0 16px;background:#0b0b0b;color:#eaeaea;line-height:1.6;}}
h1{{margin:0 0 8px;font-size:34px;}}
.badge{{display:inline-block;padding:4px 10px;border-radius:999px;background:#0f2;color:#041;font-weight:700;font-size:12px;}}
code,pre{{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;}}
pre{{background:#111;border:1px solid #222;border-radius:10px;padding:14px;overflow:auto;}}
a{{color:#9aa6ff;text-decoration:none;}}
a:hover{{text-decoration:underline;}}
.card{{background:#0f0f0f;border:1px solid #222;border-radius:12px;padding:16px;margin:12px 0;}}
</style></head><body>
<div class="badge">ONLINE</div>
<h1>Gemini API</h1>
<p>Free · No auth · No API key required</p>
<div class="card">
<b>JSON:</b>   <code>GET {base}/ask?q=Ciao</code><br>
<b>SSE:</b>    <code>GET {base}/ask/stream?q=Ciao</code><br>
<b>Upload:</b> <code>POST {base}/upload</code> (multipart: file, session_id)
</div>
<div class="card"><a href="/docs">Swagger UI</a> · <a href="/redoc">ReDoc</a></div>
<h3>Endpoints</h3>
<pre><code>GET    /ask
GET    /ask/stream
POST   /upload
DELETE /uploads/{{sid}}
GET    /health
GET    /sessions
DELETE /session/{{sid}}
POST   /session/{{sid}}/reset</code></pre>
</body></html>"""

@app.get("/health")
async def health():
 with _lock:
  return {"status":"ok","sessions":len(_sessions),"uploads":sum(len(v) for v in _uploads.values()),"client_ready":_client is not None}

@app.get("/sessions")
async def sessions():
 with _lock:
  items=list(_sessions.items())[:50]
  return {"count":len(_sessions),"sessions":[{"id":k,"turns":v.turn,"last":v.lqt,"pending_files":len(_uploads.get(k,[]))} for k,v in items]}

@app.delete("/session/{sid}")
async def delete_session(sid:str):
 with _lock:
  dropped=_sessions.pop(sid,None)
  _uploads.pop(sid,None)
 return {"deleted":dropped is not None,"session_id":sid}

@app.post("/session/{sid}/reset")
async def reset_session(sid:str):
 with _lock:
  s=_sessions.get(sid)
  if not s:return {"reset":False,"session_id":sid}
  s.cid=s.rid=s.rcid="";s.turn=0
  _uploads.pop(sid,None)
  return {"reset":True,"session_id":sid}

@app.post("/upload")
async def upload(file:UploadFile=File(...),session_id:str=Form(...)):
 if not session_id:return JSONResponse({"status":"error","error":"session_id required"},status_code=400)
 data=await file.read()
 mime=file.content_type or "application/octet-stream"
 name=file.filename or "file"
 if not mime.startswith("image/"):return JSONResponse({"status":"error","error":"only images supported (jpg/png/webp/gif/bmp)"},status_code=400)
 if len(data)>262144:return JSONResponse({"status":"error","error":f"image too large: {len(data)} bytes (max 262144)"},status_code=413)
 try:
  client=get_client()
  state=get_state(session_id)
  if not state.bl:client.bootstrap(state)
  result=client.upload_image(data,name,mime)
  with _lock:
   _uploads.setdefault(session_id,[]).append(result)
  return {"status":"success","session_id":session_id,"file":{"name":result["name"],"size":result["size"],"mime":result["mime"]},"pending_count":len(_uploads[session_id])}
 except Exception as e:
  return JSONResponse({"status":"error","error":f"{type(e).__name__}: {e}"},status_code=500)

@app.delete("/uploads/{sid}")
async def clear_uploads(sid:str):
 with _lock:
  n=len(_uploads.get(sid,[]))
  _uploads[sid]=[]
 return {"cleared":n,"session_id":sid}

@app.get("/ask")
async def ask(
 q:str=Query(...,min_length=1,max_length=30000),
 session_id:str=Query(""),
 engineer:bool=Query(True),
 complete:bool=Query(True),
):
 t0=time.perf_counter()
 sid=session_id.strip() or str(uuid.uuid4())
 try:
  client=get_client()
  state=get_state(sid)
  if not state.bl:client.bootstrap(state)
  files=pop_files(sid)
  ans,tags=client.chat(message=q,state=state,use_engineer=engineer,force_complete=complete,files=files if files else None)
  return {"status":"success","answer":ans,"session_id":sid,"enhancements":tags,"files_sent":len(files),"elapsed_ms":int((time.perf_counter()-t0)*1000)}
 except RuntimeError as e:
  msg=str(e);code=429 if "Rate limit" in msg else 500
  return JSONResponse({"status":"error","error":msg,"session_id":sid,"elapsed_ms":int((time.perf_counter()-t0)*1000)},status_code=code)
 except Exception as e:
  return JSONResponse({"status":"error","error":f"{type(e).__name__}: {e}","session_id":sid,"elapsed_ms":int((time.perf_counter()-t0)*1000)},status_code=500)

@app.get("/ask/stream")
async def ask_stream(
 q:str=Query(...,min_length=1,max_length=30000),
 session_id:str=Query(""),
 engineer:bool=Query(True),
 complete:bool=Query(True),
 chunk_size:int=Query(220,ge=50,le=1500),
):
 sid=session_id.strip() or str(uuid.uuid4())
 def gen():
  t0=time.perf_counter()
  yield sse("open",{"status":"open","session_id":sid})
  try:
   client=get_client()
   state=get_state(sid)
   if not state.bl:client.bootstrap(state)
   files=pop_files(sid)
   if files:yield sse("status",{"stage":"files_attached","count":len(files)})
   yield sse("status",{"stage":"processing"})
   ans,tags=client.chat(message=q,state=state,use_engineer=engineer,force_complete=complete,files=files if files else None)
   yield sse("meta",{"enhancements":tags,"files_sent":len(files)})
   for ch in chunk_text(ans,chunk_size):yield sse("chunk",ch)
   yield sse("done",{"status":"success","session_id":sid,"elapsed_ms":int((time.perf_counter()-t0)*1000)})
  except Exception as e:
   yield sse("error",{"status":"error","error":str(e),"session_id":sid})
 headers={"Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"}
 return StreamingResponse(gen(),media_type="text/event-stream",headers=headers)
