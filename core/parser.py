import json,re
class GeminiParser:
 E={37:"Web search vuoto",1096:"Rate limit",1097:"Sessione scaduta",1103:"Rate limit",1104:"Policy",1155:"Login richiesto"}
 @classmethod
 def parse(cls,raw):
  t=raw.lstrip()
  if t.startswith(")]}'"):t=t[4:].lstrip()
  blocks=cls._blocks(t)
  cands=[]
  for b in blocks:
   try:
    p=json.loads(b)
    for e in p:
     if isinstance(e,list) and len(e)>=3 and e[0]=="wrb.fr" and e[2]:cands.append(e[2])
   except:continue
  if not cands:
   m=re.search(r'BardErrorInfo".*?\[(\d+)\]',raw)
   if m:
    c=int(m.group(1))
    raise ValueError(f"[{c}] {cls.E.get(c,f'Errore #{c}')}")
   raise ValueError("Risposta vuota")
  payload=max(cands,key=len)
  try:inner=json.loads(payload)
  except json.JSONDecodeError as e:raise ValueError(f"Payload malformato: {e}")
  ids={"cid":"","rid":"","rcid":""}
  try:
   ids["cid"]=inner[1][0] or ""
   ids["rid"]=inner[1][1] or ""
  except:pass
  try:
   c=inner[4][0]
   ids["rcid"]=c[0] or ""
   txt=c[1][0]
   if txt and txt.startswith("[{") and len(txt)<50:
    try:
     pt=json.loads(txt)
     if isinstance(pt,list) and pt and isinstance(pt[0],dict) and "37" in pt[0]:raise ValueError("Web search vuoto")
    except json.JSONDecodeError:pass
   return txt,ids
  except ValueError:raise
  except:return json.dumps(inner,ensure_ascii=False),ids
 @staticmethod
 def _blocks(t):
  b=[];i=0;n=len(t)
  while i<n:
   while i<n and t[i] in " \r\n\t":i+=1
   if i>=n:break
   if t[i].isdigit():
    while i<n and t[i]!="\n":i+=1
    continue
   if t[i]=="[":
    d=0;s=i
    while i<n:
     if t[i]=="[":d+=1
     elif t[i]=="]":
      d-=1
      if d==0:
       i+=1
       b.append(t[s:i])
       break
     i+=1
   else:i+=1
  return b