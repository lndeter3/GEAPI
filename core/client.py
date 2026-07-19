import re,json,time,mimetypes
from pathlib import Path
from urllib.parse import quote
from curl_cffi import requests as R
from .parser import GeminiParser
from .prompt import PromptEngineer
from .session import SessionState,SessionManager
class GeminiClient:
 UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
 B="https://gemini.google.com"
 A=B+"/app"
 S=B+"/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
 U="https://push.clients6.google.com/upload/"
 CK="SOCS=CAESNggeEixib3FfYXNzaXN0YW50LWJhcmQtd2ViLXNlcnZlcl8yMDI2MDcwOS4wOV9wMBoCaXQgARoGCICyy9IG"
 MIME_IMG={".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".webp":"image/webp",".gif":"image/gif",".bmp":"image/bmp"}
 LR=re.compile(r'\b(\d{2,})\s+(?:titoli|giochi|film|libri|nomi|esempi|idee|cose|elementi|items?|prodotti|canzoni|album|serie|prompt|domande|risposte)',re.I)
 def __init__(self):
  self._h=self._mk()
 def _mk(self):
  s=R.Session(impersonate="chrome131")
  s.headers.update({"user-agent":self.UA,"accept":"*/*","accept-language":"it-IT,it;q=0.9,en;q=0.8","origin":self.B,"referer":self.B+"/","x-same-domain":"1","connection":"keep-alive"})
  s.cookies.update({"SOCS":self.CK})
  return s
 def bootstrap(self,st):
  r=self._h.get(self.A,timeout=15)
  r.raise_for_status()
  h=r.text
  for n,a in [("FdrFJe","fsid"),("cfb2h","bl"),("SNlM0e","at")]:
   m=re.search(rf'"{n}"\s*:\s*"([^"]+)"',h)
   if m:setattr(st,a,m.group(1))
  if not st.bl:raise RuntimeError("Bootstrap: bl mancante")
 def upload_image(self,data,name,mime):
  size=len(data)
  if size>262144:raise RuntimeError(f"Immagine {size/1024:.0f}KB > 256KB max")
  h1={"x-goog-upload-command":"start","x-goog-upload-protocol":"resumable","x-goog-upload-header-content-length":str(size),"x-goog-upload-header-content-type":mime,"push-id":"feeds/mcudyrk2a4khkz","content-type":"application/x-www-form-urlencoded;charset=UTF-8"}
  r1=self._h.post(self.U,headers=h1,data=f"File name: {name}",timeout=20)
  if r1.status_code!=200:raise RuntimeError(f"Upload init HTTP {r1.status_code}: {r1.text[:200]}")
  url=r1.headers.get("x-goog-upload-url") or r1.headers.get("X-Goog-Upload-URL")
  if not url:raise RuntimeError(f"Upload URL mancante")
  r2=self._h.post(url,headers={"x-goog-upload-command":"upload, finalize","x-goog-upload-offset":"0"},data=data,timeout=60)
  if r2.status_code!=200:raise RuntimeError(f"Upload finalize HTTP {r2.status_code}: {r2.text[:200]}")
  uid=r2.text.strip()
  if not uid or len(uid)<5:raise RuntimeError(f"Upload ID invalido")
  return {"id":uid,"name":name,"mime":mime,"size":size}
 def chat(self,message,state,use_engineer=True,force_complete=True,files=None):
  SessionManager.throttle(state)
  SessionManager.pre(state)
  orig=message
  tags=[]
  if use_engineer:message,tags=PromptEngineer.enhance(message)
  last=None
  sr=False
  for a in range(4):
   try:
    ans=self._send(message,state,files)
    ans=PromptEngineer.clean(ans)
    if force_complete and not files:ans=self._cont(orig,ans,state)
    return ans,tags
   except ValueError as e:
    m=str(e)
    if "1097" in m and not sr:
     SessionManager.reset(state)
     sr=True
     continue
    if "1096" in m:
     state.lft=time.time()
     raise RuntimeError("Rate limit. Attendi 15-30 min.")
    raise RuntimeError(m)
   except Exception as e:
    last=e
    if a<3:
     time.sleep(1)
     continue
  raise RuntimeError(f"Tentativi esauriti: {last}")
 def _send(self,msg,st,files=None):
  st.reqid+=100000
  p={"bl":st.bl,"f.sid":st.fsid or "-1","hl":"it","_reqid":str(st.reqid),"rt":"c"}
  att=None
  if files:att=[[[f["id"],f["name"]],1] for f in files]
  mp=[msg,0,None,att,None,None,0]
  ip=[st.cid,st.rid,st.rcid,None,None,None,None,None,None,""]
  inner=[mp,["it"],ip]
  outer=[None,json.dumps(inner,ensure_ascii=False)]
  body="f.req="+quote(json.dumps(outer,ensure_ascii=False),safe="")
  if st.at:body+="&at="+quote(st.at,safe="")
  r=self._h.post(self.S,params=p,data=body,headers={"content-type":"application/x-www-form-urlencoded;charset=UTF-8"},timeout=60 if files else 30)
  if r.status_code!=200:raise ValueError(f"HTTP {r.status_code}: {r.text[:200]}")
  txt,ids=GeminiParser.parse(r.text)
  st.cid=ids["cid"] or st.cid
  st.rid=ids["rid"] or st.rid
  st.rcid=ids["rcid"] or st.rcid
  return txt
 def _cont(self,orig,ans,state):
  m=self.LR.search(orig)
  if not m:return ans
  req=int(m.group(1))
  if req<10:return ans
  found=set()
  for mm in re.finditer(r'(?:^|\n)\s*(\d{1,4})[.\)]\s',ans):found.add(int(mm.group(1)))
  act=max((x for x in found if x<=req),default=0)
  if act==0 or act>=req*0.85:return ans
  try:
   add=self._send(f"Continua dal {act+1} al {req}. Solo i {req-act} mancanti.",state)
   return ans.rstrip()+"\n\n"+PromptEngineer.clean(add).strip()
  except:return ans