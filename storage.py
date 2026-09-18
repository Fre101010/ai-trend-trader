import os,json
from pathlib import Path
from datetime import datetime,timezone
LOCAL=Path('paper_state.json')
def _supabase():
 url=os.getenv('SUPABASE_URL');key=os.getenv('SUPABASE_KEY')
 if not url or not key:return None
 from supabase import create_client
 return create_client(url,key)
def load_state():
 sb=_supabase()
 if sb:
  res=sb.table('paper_state').select('*').eq('id',1).execute()
  if res.data:return res.data[0]['payload'],'supabase'
 if LOCAL.exists():return json.loads(LOCAL.read_text(encoding='utf-8')),'local-demo'
 return {'cash':5000.0,'positions':{},'trades':[],'equity_history':[],'last_run':None},'new'
def save_state(state):
 state['last_run']=datetime.now(timezone.utc).isoformat();sb=_supabase()
 if sb:
  sb.table('paper_state').upsert({'id':1,'payload':state}).execute();return 'supabase'
 LOCAL.write_text(json.dumps(state,indent=2),encoding='utf-8');return 'local-demo'
