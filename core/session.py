import time,random,threading
from dataclasses import dataclass,field
@dataclass
class SessionState:
 cid:str=""
 rid:str=""
 rcid:str=""
 at:str=""
 bl:str=""
 fsid:str=""
 reqid:int=field(default_factory=lambda:random.randint(100000,900000))
 turn:int=0
 toxic:bool=False
 ws:bool=False
 lqt:float=0.0
 lft:float=0.0
 cfast:int=0
class SessionManager:
 _l=threading.Lock()
 _s:dict={}
 @classmethod
 def get(cls,sid):
  with cls._l:
   if sid not in cls._s:cls._s[sid]=SessionState()
   return cls._s[sid]
 @classmethod
 def reset(cls,s):
  s.cid=s.rid=s.rcid=""
  s.toxic=False
  s.turn=0
 @classmethod
 def throttle(cls,s):
  now=time.time()
  el=now-s.lqt
  w=min(3.0+s.cfast*0.5,10.0) if s.cfast>=5 else(5.0 if now-s.lft<60 else 2.0)
  r=max(0.0,w-el)
  if r>0 and s.lqt>0:time.sleep(r)
  s.lqt=time.time()
  if el<3.0:s.cfast+=1
  else:s.cfast=max(0,s.cfast-1)
 @classmethod
 def pre(cls,s):
  s.turn+=1
  if s.turn%8==0 and s.cid:cls.reset(s)
  if s.turn>40:cls.reset(s)