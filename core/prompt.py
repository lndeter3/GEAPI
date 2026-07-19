import re
class PromptEngineer:
 L=["link","url","sito","website","canale","channel","youtube","yt","spotify","twitch","instagram","tiktok","download","scarica","github"]
 R=["oggi","ora","adesso","questa settimana","questo mese","recente","ultimo","nuovo","attuale","today","now","recent","latest","current"]
 X=re.compile(r'\b(\d{2,})\s+(?:titoli|giochi|film|libri|nomi|esempi|idee|cose|elementi|items?|prodotti|canzoni|album|serie|prompt|domande|risposte)',re.I)
 C=[r'\n*A proposito, per sbloccare.*?\)\.',r'\n*Per sbloccare tutte.*?\)\.',r'\n*Nota: non posso inserire.*?\.',r'\n*\*Nota: non posso.*?\*',r'\n*http://googleusercontent\.com/[a-z_]+/\d+',r'\n*\*Nota: [^*]{5,200}\*',r'\n*Vuoi qualche consiglio su [^?]*\?',r'\n*Buon ascolto!',r'\n*Buona visione!']
 @classmethod
 def enhance(cls,p):
  low=p.lower();e=p;t=[]
  if "| *" in p or "| -" in p:
   c=re.sub(r'\|\s*\*\*|\|\s*\*|\|\s*-','-',p).replace("|","").strip()
   items=[l.strip("- *").strip() for l in c.split("\n") if l.strip().startswith(("-","*"))]
   e=("Riguardo questi elementi:\n"+"\n".join(f"- {i}" for i in items)+"\n\nDammi quello che ho chiesto in modo dettagliato." if items else c)
   t.append("cleanup")
   low=e.lower()
  if any(k in low for k in cls.L):
   e+="\n\nIMPORTANTE:\n1. Cerca sul web i link ufficiali\n2. URL COMPLETI FUNZIONANTI (https://...)\n3. NON placeholder\n4. NON dire 'non posso inserire link'\n5. Formato: [Titolo](URL)\n"
   t.append("links")
  elif any(k in low for k in cls.R):
   e="Cerca sul web informazioni AGGIORNATE e VERIFICATE:\n\n"+e
   t.append("recent")
  m=cls.X.search(p)
  if m:
   n=int(m.group(1))
   if 10<=n<=200 and "esattamente" not in low:
    e+=f"\n\nFornisci ESATTAMENTE {n} elementi numerati da 1 a {n}. Non troncare."
    t.append(f"list_{n}")
  return e,t
 @classmethod
 def clean(cls,t):
  if not t:return t
  for p in cls.C:t=re.sub(p,"",t,flags=re.DOTALL|re.I)
  return re.sub(r'\n{3,}','\n\n',t).strip()