"""Public market recorder. Standard library only; no models or private repositories."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.request import Request,urlopen,HTTPRedirectHandler,build_opener
from urllib.parse import urlencode,urlparse
import argparse,json,hashlib,re,time,os,subprocess,base64,gzip,fcntl
UTC=timezone.utc
ROOT=Path(__file__).parent
ENDPOINT='https://info.cld.hkjc.com/graphql/base-get/'
SCHEMA='public-market-v1'
def now():return datetime.now(UTC)
def utc(v):
 d=datetime.fromisoformat(str(v).replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('timezone required')
 return d.astimezone(UTC)
def encode(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def sha(v):return hashlib.sha256(encode(v).encode()).hexdigest()
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*a,**kw):raise ValueError('redirect rejected')
def graphql(name,variables):
 q=(ROOT/'queries'/f'{name}.graphql').read_text()
 # GraphQL tokens stay separated; commas are permitted by the public endpoint.
 tokens=re.findall(r'"(?:\\.|[^"\\])*"|[_A-Za-z][_0-9A-Za-z]*|\.\.\.|[^\s,]',q)
 q=''.join((' ' if i and re.match(r'[\w]$',tokens[i-1][-1]) and re.match(r'\w',t[0]) else '')+t for i,t in enumerate(tokens))
 url=ENDPOINT+'?'+urlencode({'query':q,'variables':encode(variables)})
 req=Request(url,headers={'User-Agent':'Mozilla/5.0','Content-Type':'application/json','Accept':'application/json','Origin':'https://bet.hkjc.com','Referer':'https://bet.hkjc.com/'})
 with build_opener(NoRedirect).open(req,timeout=5) as r:raw=r.read(8_000_001)
 if len(raw)>8_000_000:raise ValueError('oversized public response')
 if raw[:2]==b'\x1f\x8b':raw=gzip.decompress(raw)
 if len(raw)>8_000_000:raise ValueError('oversized expanded response')
 p=json.loads(raw)
 if p.get('errors') or not isinstance(p.get('data'),dict):raise ValueError('invalid public response')
 return p['data']
def calendar(payload):
 out=[]
 for m in payload.get('raceMeetings') or []:
  if m.get('venueCode') not in ['ST','HV']:continue
  day=str(m['date']);datetime.strptime(day,'%Y-%m-%d');mid=str(m['id'])
  if not re.fullmatch('MTG_'+day.replace('-','')+r'_\d+',mid):raise ValueError('meeting identity')
  races=[]
  for r in m.get('races') or []:
   no=int(r['no'])
   if not 1<=no<=20:raise ValueError('race number')
   runners=[];seen=set()
   for h in r.get('runners') or []:
    status=str(h.get('status',''))
    if status.upper() in ['RESERVED','STANDBY']:continue
    n=int(h['no']);code=str(h['horse']['code'])
    if n in seen or not re.fullmatch('[A-Za-z0-9_-]{1,30}',code):raise ValueError('runner identity')
    seen.add(n);runners.append({'no':n,'code':code,'name':str(h.get('name_ch') or h.get('name_en') or '')[:100],'status':status[:30]})
   races.append({'no':no,'post':utc(r['postTime']).isoformat(),'status':str(r.get('status',''))[:30],'runners':runners})
  out.append({'id':mid,'date':day,'venue':m['venueCode'],'status':str(m.get('status',''))[:30],'races':races})
 return out

def clean_pool(p,m,r):
 k=p['oddsType'];no=r['no'];legs=[no,no+1] if k=='DBL' else [no]
 if k not in ['WIN','PLA','QIN','DBL'] or p.get('id')!=m['id']+k+str(no) or p.get('leg',{}).get('races')!=legs:raise ValueError('pool identity/leg mismatch')
 def node(h,depth=0):
  if depth>1:raise ValueError('nested grid too deep')
  s=str(h.get('combString',''));v=str(h.get('oddsValue',''))
  if not re.fullmatch(r'[0-9,/\- ]{1,30}',s):raise ValueError('combination format')
  # Preserve explicit missing/capped markers as data; never reinterpret them as a price.
  if len(v)>32 or not re.fullmatch(r'[A-Za-z0-9.\-+ /]*',v):raise ValueError('quote format')
  x={'combString':s,'oddsValue':v}
  if h.get('bankerOdds'):x['bankerOdds']=[node(z,depth+1) for z in h['bankerOdds']]
  return x
 at=p.get('oddsLastUpdateTime') or p.get('lastUpdateTime')
 published=utc(at).isoformat() if at else None
 return {'id':p['id'],'kind':k,'legs':legs,'published_at':published,'status':str(p.get('status',''))[:30],'sell_status':str(p.get('sellStatus',''))[:30],'nodes':[node(n) for n in p.get('oddsNodes') or []]}

def atomic(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(encode(value));os.replace(temp,path)

def record(state,item):
 day=item['date'];venue=item['venue']
 hour=utc(item['captured_at']).strftime('%Y%m%dT%H')
 label=f"race_{int(item['race_no']):02}" if item['kind']=='book' else 'calendar'
 path=state/'market'/f'{day}_{venue}'/f'{label}_{hour}.jsonl.gz';path.parent.mkdir(parents=True,exist_ok=True)
 with (state/'.write.lock').open('a') as guard:
  fcntl.flock(guard,fcntl.LOCK_EX)
  with gzip.open(path,'at',encoding='utf-8') as f:f.write(encode(item)+'\n')

def tick(state,cache,clock=now):
 at=clock()
 if 'calendar_at' not in cache or (at-cache['calendar_at']).total_seconds()>=120:
  meetings=calendar(graphql('calendar',{'date':None,'venueCode':None}));cache['meetings']=meetings;cache['calendar_at']=clock()
  atomic(state/'calendar.json',{'schema':SCHEMA,'captured_at':clock().isoformat(),'meetings':meetings})
  for m in meetings:
   if m['date']==at.astimezone(ZoneInfo('Asia/Hong_Kong')).date().isoformat():record(state,{'schema':SCHEMA,'kind':'schedule','date':m['date'],'venue':m['venue'],'captured_at':clock().isoformat(),'meeting':m})
 count=0
 for m in cache.get('meetings',[]):
  if m['date']!=at.astimezone(ZoneInfo('Asia/Hong_Kong')).date().isoformat():continue
  for r in m['races']:
   sec=(utc(r['post'])-clock()).total_seconds()
   if not 0<sec<=5400 or r['status'] in ['RESULT','VOID','CANCELLED']:continue
   try:
    data=graphql('pools',{'date':m['date'],'venueCode':m['venue'],'raceNo':r['no'],'oddsTypes':['WIN','PLA','QIN','DBL']});captured=clock();ms=data.get('raceMeetings') or []
    if len(ms)!=1:raise ValueError('ambiguous source')
    pools=[clean_pool(p,m,r) for p in ms[0].get('pmPools') or [] if p.get('oddsType') in ['WIN','PLA','QIN','DBL']]
    if len({p['kind'] for p in pools})!=len(pools):raise ValueError('duplicate pool')
    entry={'schema':SCHEMA,'kind':'book','date':m['date'],'venue':m['venue'],'race_no':r['no'],'captured_at':captured.isoformat(),'recorded_at':clock().isoformat(),'meeting_id':m['id'],'race':r,'pools':pools,'source_sha256':sha(data),'collector_commit':os.environ.get('GITHUB_SHA','local'),'source_run_id':os.environ.get('GITHUB_RUN_ID','local')}
    record(state,entry)
    folder=state/'market'/f"{m['date']}_{m['venue']}"
    atomic(folder/f"race_{r['no']:02}_latest.json",entry)
    # Public transport indexes: 5-minute opening samples and last 12 preoff captures.
    # These are raw observations; no private thresholds, models or decisions.
    sample=folder/f"race_{r['no']:02}_opening_samples.json"
    prior=json.loads(sample.read_text()) if sample.exists() else []
    if not prior or (captured-utc(prior[-1]['captured_at'])).total_seconds()>=300:
     atomic(sample,(prior+[entry])[-24:])
    tail=folder/f"race_{r['no']:02}_preoff_samples.json"
    prior=json.loads(tail.read_text()) if tail.exists() else []
    atomic(tail,(prior+[entry])[-12:]);count+=1
   except Exception:
    cache['source_errors']=cache.get('source_errors',0)+1 # Never echo remote response or request headers.
 atomic(state/'heartbeat.json',{'schema':SCHEMA,'checked_at':clock().isoformat(),'books_this_tick':count,'source_errors':cache.get('source_errors',0),'collector_commit':os.environ.get('GITHUB_SHA','local'),'source_run_id':os.environ.get('GITHUB_RUN_ID','local')})
 return count

def plan(meetings,at,done):
 today=at.astimezone(ZoneInfo('Asia/Hong_Kong')).date().isoformat()
 for m in meetings:
  posts=sorted(utc(r['post']) for r in m['races'] if r['status'] not in ['VOID','CANCELLED'])
  if m['date']!=today or not posts or m['id'] in done:continue
  end=posts[-1]+timedelta(minutes=5)
  if not posts[0]-timedelta(minutes=110)<=at<end:continue
  candidates=[p+timedelta(minutes=5) for p,n in zip(posts,posts[1:]) if n-p>=timedelta(minutes=25)]
  if not candidates:raise ValueError('no safe phase split')
  split=min(candidates,key=lambda p:abs((p-(posts[0]+(posts[-1]-posts[0])/2)).total_seconds()))
  cut=max(at,split)
  if max((cut-at).total_seconds(),(end-max(at,split)).total_seconds())>330*60:raise ValueError('meeting too long')
  return {'eligible':True,'meeting_id':m['id'],'phase1_until':cut.isoformat(),'phase2_until':end.isoformat()}
 return {'eligible':False,'checked_at':at.isoformat()}

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['probe','plan','watch','complete']);p.add_argument('--state',default='state');p.add_argument('--until');a=p.parse_args();state=Path(a.state);state.mkdir(parents=True,exist_ok=True)
 if a.action=='plan':
  m=calendar(graphql('calendar',{'date':None,'venueCode':None}));done=json.loads((state/'completed.json').read_text()) if (state/'completed.json').exists() else {};result=plan(m,now(),done)
  atomic(state/'session.json',result)
  if os.environ.get('GITHUB_OUTPUT'):
   with open(os.environ['GITHUB_OUTPUT'],'a') as f:
    for k in ['eligible','phase1_until','phase2_until']:f.write(k+'='+str(result.get(k,'')).lower()+'\n' if k=='eligible' else k+'='+str(result.get(k,''))+'\n')
  print(encode(result));return
 if a.action=='complete':
  result=json.loads((state/'session.json').read_text())
  if now()<utc(result['phase2_until'])-timedelta(seconds=20):raise ValueError('session still active')
  path=state/'completed.json';done=json.loads(path.read_text()) if path.exists() else {};done[result['meeting_id']]=now().isoformat();atomic(path,done);return
 cache={};end=utc(a.until) if a.until else now();last_log=0
 while True:
  try:tick(state,cache)
  except Exception:atomic(state/'heartbeat.json',{'schema':SCHEMA,'checked_at':now().isoformat(),'status':'source_unavailable'})
  if time.monotonic()-last_log>=60:print('public recorder tick',flush=True);last_log=time.monotonic()
  if now()>=end:break
  time.sleep(min(10,max(0,(end-now()).total_seconds())))
if __name__=='__main__':main()
