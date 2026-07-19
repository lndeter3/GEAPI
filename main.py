import uuid,time,threading,os
from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException,Query,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse,HTMLResponse
from core.client import GeminiClient
from core.session import SessionState
_lock=threading.Lock()
_sessions:dict={}
_client=None
_last_cleanup=time.time()
def get_client():
 global _client
 if _client is None:
  _client=GeminiClient()
 return _client
def get_state(sid):
 global _last_cleanup
 with _lock:
  now=time.time()
  if now-_last_cleanup>3600:
   _last_cleanup=now
   cutoff=now-7200
   dead=[k for k,v in _sessions.items() if getattr(v,"lqt",0)<cutoff and v.lqt>0]
   for k in dead:_sessions.pop(k,None)
  if sid not in _sessions:_sessions[sid]=SessionState()
  return _sessions[sid]
@asynccontextmanager
async def lifespan(app):
 try:
  c=get_client()
  tmp=SessionState()
  c.bootstrap(tmp)
  print(f"[STARTUP] Bootstrap OK · bl={tmp.bl[:20] if tmp.bl else 'NONE'}...",flush=True)
 except Exception as e:
  print(f"[STARTUP WARN] {e}",flush=True)
 yield
 print("[SHUTDOWN] Bye",flush=True)
app=FastAPI(title="Gemini API",version="1.0",description="API pubblica per Gemini · gratis · no auth · no rate limit noto",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["GET","POST","DELETE","OPTIONS"],allow_headers=["*"])
@app.get("/",response_class=HTMLResponse)
async def root(request:Request):
 base=str(request.base_url).rstrip("/")
 return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gemini API · Free</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:'Inter',sans-serif;background:#0a0a0a;color:#e8e8e8;min-height:100vh;padding:40px 20px;line-height:1.7;}}
.container{{max-width:820px;margin:0 auto;}}
h1{{font-size:2.5rem;background:linear-gradient(135deg,#8B5CF6,#EC4899,#F59E0B);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-weight:700;letter-spacing:-0.03em;margin-bottom:8px;}}
.sub{{color:#666;font-size:1rem;margin-bottom:24px;}}
.pill{{display:inline-flex;align-items:center;gap:6px;background:rgba(16,185,129,0.1);color:#34d399;padding:6px 14px;border-radius:20px;font-size:12px;font-weight:600;border:1px solid rgba(16,185,129,0.2);}}
.dot{{width:8px;height:8px;background:#10a37f;border-radius:50%;box-shadow:0 0 8px #10a37f;}}
h2{{margin:32px 0 12px;font-size:1.3rem;color:#f5f5f5;font-weight:600;}}
code,pre{{font-family:'JetBrains Mono',monospace;}}
code{{background:rgba(139,92,246,0.1);color:#c4b5fd;padding:2px 8px;border-radius:5px;font-size:14px;}}
pre{{background:#111;border:1px solid rgba(255,255,255,0.06);padding:16px;border-radius:12px;overflow-x:auto;margin:12px 0;font-size:13px;}}
pre code{{background:transparent;padding:0;color:#e8e8e8;}}
a{{color:#a78bfa;text-decoration:none;border-bottom:1px solid rgba(167,139,250,0.3);}}
a:hover{{border-bottom-color:#a78bfa;}}
.card{{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:20px;margin:16px 0;}}
.method{{display:inline-block;background:rgba(16,185,129,0.15);color:#34d399;padding:4px 10px;border-radius:6px;font-size:11px;font-weight:700;font-family:'JetBrains Mono',monospace;}}
.url{{color:#e8e8e8;font-family:'JetBrains Mono',monospace;font-size:14px;margin-left:8px;}}
ul{{list-style:none;}}
li{{padding:6px 0;color:#aaa;font-size:14px;}}
li strong{{color:#c4b5fd;font-family:'JetBrains Mono',monospace;margin-right:8px;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:16px 0;}}
.tag{{background:rgba(139,92,246,0.08);color:#a78bfa;padding:4px 10px;border-radius:6px;font-size:11px;display:inline-block;margin:2px;}}
</style></head>
<body><div class="container">
<span class="pill"><span class="dot"></span>ONLINE</span>
<h1 style="margin-top:16px;">✨ Gemini API</h1>
<p class="sub">Free · No auth · No API key required</p>

<h2>🚀 Try it now</h2>
<div class="card">
<div><span class="method">GET</span><span class="url">{base}/ask?q=Ciao</span></div>
<p style="margin-top:12px;color:#888;font-size:14px;">👉 <a href="/ask?q=Ciao+come+stai" target="_blank">Live demo</a> · <a href="/docs">Swagger UI</a> · <a href="/redoc">ReDoc</a></p>
</div>

<h2>📖 Endpoints</h2>
<div class="card">
<div><span class="method">GET</span><span class="url">/ask</span></div>
<p style="color:#888;font-size:14px;margin-top:8px;">Chiedi qualsiasi cosa a Gemini</p>
<ul style="margin-top:12px;">
<li><strong>q</strong> <span class="tag">required</span> domanda per Gemini</li>
<li><strong>session_id</strong> <span class="tag">optional</span> mantiene contesto multi-turno</li>
<li><strong>engineer</strong> <span class="tag">bool</span> prompt enhancement (default: true)</li>
<li><strong>complete</strong> <span class="tag">bool</span> auto-completa liste (default: true)</li>
</ul>
</div>

<div class="card">
<div><span class="method">GET</span><span class="url">/health</span></div>
<p style="color:#888;font-size:14px;margin-top:8px;">Status server e numero sessioni attive</p>
</div>

<div class="card">
<div><span class="method">GET</span><span class="url">/sessions</span></div>
<p style="color:#888;font-size:14px;margin-top:8px;">Lista sessioni attive</p>
</div>

<div class="card">
<div><span class="method" style="background:rgba(239,68,68,0.15);color:#f87171;">DELETE</span><span class="url">/session/{{sid}}</span></div>
<p style="color:#888;font-size:14px;margin-top:8px;">Cancella una sessione</p>
</div>

<h2>💻 Esempi</h2>

<h3 style="color:#c4b5fd;font-size:1rem;margin-top:16px;">Python</h3>
<pre><code>import requests

API = "{base}"

r = requests.get(f"{{API}}/ask", params={{"q": "Ciao come stai?"}})
data = r.json()
print(data["answer"])
print(f"Tempo: {{data['elapsed_ms']}}ms")

# Multi-turno con session_id
sid = data["session_id"]
r2 = requests.get(f"{{API}}/ask", params={{"q": "E ora?", "session_id": sid}})
print(r2.json()["answer"])</code></pre>

<h3 style="color:#c4b5fd;font-size:1rem;margin-top:16px;">JavaScript</h3>
<pre><code>const API = "{base}";

const r = await fetch(`${{API}}/ask?q=${{encodeURIComponent("Ciao!")}}`);
const data = await r.json();
console.log(data.answer);</code></pre>

<h3 style="color:#c4b5fd;font-size:1rem;margin-top:16px;">cURL</h3>
<pre><code>curl "{base}/ask?q=Ciao+come+stai"

# Con jq
curl -s "{base}/ask?q=Ciao" | jq -r '.answer'</code></pre>

<h2>📦 Response format</h2>
<pre><code>{{
  "status": "success",
  "answer": "Ciao! Sto benissimo, grazie...",
  "session_id": "abc-123-def-456",
  "enhancements": [],
  "elapsed_ms": 3420
}}</code></pre>

<h2>⚠️ Note</h2>
<ul>
<li style="padding-left:20px;">Nessuna API key richiesta</li>
<li style="padding-left:20px;">Sessioni in RAM (auto-cleanup dopo 2h di inattività)</li>
<li style="padding-left:20px;">Risposte in italiano di default (aggiungi "in inglese" al prompt per switch)</li>
<li style="padding-left:20px;">Max ~2500 token per prompt</li>
<li style="padding-left:20px;">Rate limit automatico interno (~2 req/sec)</li>
</ul>

<div style="margin-top:60px;padding-top:24px;border-top:1px solid rgba(255,255,255,0.06);color:#555;font-size:12px;text-align:center;">
Powered by <a href="https://gemini.google.com" target="_blank">Google Gemini</a> · Hosted on Railway
</div>
</div></body></html>"""
@app.get("/ask")
async def ask(
 q:str=Query(...,description="Domanda per Gemini",min_length=1,max_length=30000),
 session_id:str=Query("",description="ID sessione (opzionale, mantiene contesto)"),
 engineer:bool=Query(True,description="Attiva prompt engineering"),
 complete:bool=Query(True,description="Auto-completa liste numeriche"),
):
 t0=time.perf_counter()
 sid=session_id.strip() or str(uuid.uuid4())
 try:
  client=get_client()
  state=get_state(sid)
  if not state.bl:
   client.bootstrap(state)
  ans,tags=client.chat(message=q,state=state,use_engineer=engineer,force_complete=complete)
  return {"status":"success","answer":ans,"session_id":sid,"enhancements":tags,"elapsed_ms":int((time.perf_counter()-t0)*1000)}
 except RuntimeError as e:
  msg=str(e)
  code=429 if "Rate limit" in msg else 500
  return JSONResponse({"status":"error","error":msg,"session_id":sid,"elapsed_ms":int((time.perf_counter()-t0)*1000)},status_code=code)
 except Exception as e:
  return JSONResponse({"status":"error","error":f"{type(e).__name__}: {e}","session_id":sid,"elapsed_ms":int((time.perf_counter()-t0)*1000)},status_code=500)
@app.get("/health")
async def health():
 return {"status":"ok","sessions":len(_sessions),"client_ready":_client is not None,"uptime_ok":True}
@app.get("/sessions")
async def list_sessions():
 with _lock:
  return {"count":len(_sessions),"sessions":[{"id":k[:16]+"...","turns":v.turn,"last":v.lqt} for k,v in list(_sessions.items())[:50]]}
@app.delete("/session/{sid}")
async def del_session(sid:str):
 with _lock:
  dropped=_sessions.pop(sid,None)
 return {"deleted":dropped is not None,"session_id":sid}
@app.post("/session/{sid}/reset")
async def reset_session(sid:str):
 with _lock:
  if sid in _sessions:
   s=_sessions[sid]
   s.cid=s.rid=s.rcid=""
   s.turn=0
   return {"reset":True,"session_id":sid}
 return {"reset":False,"session_id":sid,"error":"session not found"}