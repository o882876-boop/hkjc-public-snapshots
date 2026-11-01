import unittest,tempfile,json
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import collector as c
class PublicBoundaryTests(unittest.TestCase):
 def meeting(self):
  return {'id':'MTG_20270101_0001','date':'2027-01-01','venueCode':'ST','status':'PREBET','private_model':'NEVER_EXPORT','races':[{'no':i+1,'postTime':(datetime(2027,1,1,5,tzinfo=timezone.utc)+timedelta(minutes=35*i)).isoformat(),'status':'PREBET','finalOdds':999,'runners':[{'no':1,'status':'DECLARED','horse':{'code':'H001'},'name_en':'Horse','personal_email':'NEVER_EXPORT'}]} for i in range(10)]}
 def test_calendar_allowlist_removes_private_and_final_fields(self):
  m=c.calendar({'raceMeetings':[self.meeting()]})
  self.assertNotIn('NEVER_EXPORT',c.encode(m));self.assertNotIn('finalOdds',c.encode(m));self.assertEqual(len(m[0]['races']),10)
 def test_foreign_excluded(self):
  m=self.meeting();m['venueCode']='S1';self.assertEqual(c.calendar({'raceMeetings':[m]}),[])
 def test_pool_id_and_leg_validation(self):
  m=c.calendar({'raceMeetings':[self.meeting()]})[0];r=m['races'][0]
  p={'id':m['id']+'DBL1','oddsType':'DBL','leg':{'races':[1,2]},'oddsNodes':[{'combString':'1','oddsValue':'','bankerOdds':[{'combString':'2','oddsValue':'10','secret':'NEVER_EXPORT'}]}],'secret':'NEVER_EXPORT'}
  x=c.clean_pool(p,m,r);self.assertNotIn('NEVER_EXPORT',c.encode(x));p['leg']['races']=[2,3]
  with self.assertRaises(ValueError):c.clean_pool(p,m,r)
 def test_unexpected_quote_data_rejected(self):
  m=c.calendar({'raceMeetings':[self.meeting()]})[0];p={'id':m['id']+'WIN1','oddsType':'WIN','leg':{'races':[1]},'oddsNodes':[{'combString':'1','oddsValue':'<script>run()</script>'}]}
  with self.assertRaises(ValueError):c.clean_pool(p,m,m['races'][0])
 def test_closed_pool_marker_preserved_not_treated_as_selling(self):
  m=c.calendar({'raceMeetings':[self.meeting()]})[0];p={'id':m['id']+'WIN1','oddsType':'WIN','leg':{'races':[1]},'sellStatus':'STOP_SELL','status':'PAYOUT','oddsNodes':[]}
  self.assertEqual(c.clean_pool(p,m,m['races'][0])['sell_status'],'STOP_SELL')
 def test_calendar_gate_and_completed(self):
  m=c.calendar({'raceMeetings':[self.meeting()]});t=datetime(2027,1,1,4,tzinfo=timezone.utc)
  self.assertTrue(c.plan(m,t,{})['eligible']);self.assertFalse(c.plan(m,t,{m[0]['id']:'done'})['eligible']);self.assertFalse(c.plan(m,t-timedelta(days=1),{})['eligible'])
 def test_offday_tick_only_calendar(self):
  with tempfile.TemporaryDirectory() as d,patch.object(c,'graphql',return_value={'raceMeetings':[self.meeting()]}) as api:
   n=c.tick(Path(d),{},clock=lambda:datetime(2026,12,31,tzinfo=timezone.utc));self.assertEqual(n,0);self.assertEqual(api.call_count,1);self.assertFalse((Path(d)/'market').exists())
 def test_transport_indexes_keep_actual_timestamps_and_bounded_tail(self):
  start=datetime(2027,1,1,4,40,tzinfo=timezone.utc);clock=[start];m=self.meeting()
  def api(name,v):
   if name=='calendar':return {'raceMeetings':[m]}
   no=v['raceNo'];return {'raceMeetings':[{'pmPools':[{'id':m['id']+'WIN'+str(no),'oddsType':'WIN','leg':{'races':[no]},'oddsLastUpdateTime':clock[0].isoformat(),'status':'PREBET','sellStatus':'START_SELL','oddsNodes':[{'combString':'1','oddsValue':'5'}]}]}]}
  with tempfile.TemporaryDirectory() as d,patch.object(c,'graphql',side_effect=api):
   cache={};state=Path(d)
   for i in range(15):
    clock[0]=start+timedelta(seconds=10*i);c.tick(state,cache,clock=lambda:clock[0])
   folder=state/'market/2027-01-01_ST';tail=json.loads((folder/'race_01_preoff_samples.json').read_text());early=json.loads((folder/'race_01_opening_samples.json').read_text())
   archives=list(folder.glob('race_01_*.jsonl.gz'));self.assertEqual(len(archives),1)
   with c.gzip.open(archives[0],'rt',encoding='utf-8') as f:self.assertEqual(len(f.readlines()),15)
   self.assertEqual(len(tail),12);self.assertEqual(len(early),1);self.assertEqual(early[0]['captured_at'],start.isoformat());self.assertEqual(tail[-1]['captured_at'],clock[0].isoformat())
 def test_no_redirect(self):
  with self.assertRaises(ValueError):c.NoRedirect().redirect_request(None,None,None,None,None,None)
 def test_public_source_export_file_allowlist(self):
  allowed={'collector.py','publish.py','test_collector.py','README.md','SECURITY.md','.gitignore','queries/calendar.graphql','queries/pools.graphql','.github/workflows/collect.yml','.github/workflows/watchdog.yml','.github/CODEOWNERS'}
  files={str(p.relative_to(c.ROOT)) for p in c.ROOT.rglob('*') if p.is_file() and '__pycache__' not in str(p) and '.git' not in p.relative_to(c.ROOT).parts}
  self.assertLessEqual(files,allowed)
class MonitoringTests(unittest.TestCase):
 def race(self,statuses=('DECLARED','DECLARED','DECLARED')):
  return {'no':1,'post':'2027-01-01T05:00:00+00:00','status':'DECLARED','runners':[{'no':i+1,'code':f'H00{i+1}','name':'x','status':s} for i,s in enumerate(statuses)]}
 def pool(self,vals,sell='START_SELL'):
  return [{'kind':'WIN','sell_status':sell,'status':'START_SELL','nodes':[{'combString':str(i+1),'oddsValue':v} for i,v in enumerate(vals)]}]
 def test_win_summary_complete_and_reasons(self):
  s=c.win_summary(self.pool(['2.5','4.0','8.0']),self.race());self.assertTrue(s['complete']);self.assertEqual(s['missing_reasons'],[]);self.assertAlmostEqual(s['inverse_sum'],1/2.5+1/4+1/8,places=6)
  s=c.win_summary(self.pool(['2.5','SCR','999']),self.race());self.assertFalse(s['complete']);self.assertIn('capped_999',s['missing_reasons']);self.assertIn('non_numeric_quote:SCR',s['missing_reasons']);self.assertIn('active_runner_without_valid_quote',s['missing_reasons'])
  s=c.win_summary(self.pool(['2.5','4.0','8.0']),self.race(('DECLARED','DECLARED','SCRATCHED')));self.assertIn('quoted_runner_not_active',s['missing_reasons'])
  s=c.win_summary(self.pool(['2.5','4.0','SCR']),self.race(('DECLARED','DECLARED','SCRATCHED')));self.assertTrue(s['complete']);self.assertEqual(s['info'],['scratched_runner_marker:SCR'])
  self.assertEqual(c.win_summary([],self.race())['missing_reasons'],['no_win_pool'])
  self.assertIn('pool_not_selling',c.win_summary(self.pool(['2.5','4.0','8.0'],sell='STOP_SELL'),self.race())['missing_reasons'])
 def meeting(self):
  return {'id':'MTG_20270101_0001','date':'2027-01-01','venueCode':'ST','status':'PREBET','races':[{'no':1,'postTime':'2027-01-01T05:00:00+00:00','status':'PREBET','runners':[{'no':1,'status':'DECLARED','horse':{'code':'H001'},'name_en':'A'}]}]}
 def run_ticks(self,start,n,sells,probe='0'):
  clock=[start];calls={'pools':0};m=self.meeting()
  def api(name,v):
   if name=='calendar':return {'raceMeetings':[m]}
   calls['pools']+=1;i=min(calls['pools']-1,len(sells)-1)
   return {'raceMeetings':[{'pmPools':[{'id':m['id']+'WIN1','oddsType':'WIN','leg':{'races':[1]},'oddsLastUpdateTime':clock[0].isoformat(),'status':sells[i],'sellStatus':sells[i],'oddsNodes':[{'combString':'1','oddsValue':'5'}]}]}]}
  d=tempfile.TemporaryDirectory();state=Path(d.name);cache={}
  with patch.object(c,'graphql',side_effect=api),patch.dict(c.os.environ,{'STOP_SELL_PROBE_MINUTES':probe}):
   for i in range(n):clock[0]=start+timedelta(seconds=10*i);c.tick(state,cache,clock=lambda:clock[0])
  return d,state,calls,cache
 def test_probe_off_by_default_makes_no_postoff_requests(self):
  d,state,calls,_=self.run_ticks(datetime(2027,1,1,5,0,5,tzinfo=timezone.utc),6,['START_SELL'])
  self.assertEqual(calls['pools'],0);self.assertFalse(list(state.glob('market/*/poolstate_*')));d.cleanup()
 def test_probe_records_first_not_selling_and_stops(self):
  d,state,calls,cache=self.run_ticks(datetime(2027,1,1,5,0,5,tzinfo=timezone.utc),8,['START_SELL','START_SELL','STOP_SELL'],probe='3')
  folder=state/'market/2027-01-01_ST';summ=json.loads((folder/'race_01_pool_state.json').read_text())
  self.assertEqual(summ['first_not_selling_status'],'STOP_SELL');self.assertIn('NOT the actual off time',summ['note'])
  self.assertEqual(summ['probe_requests'],3);self.assertEqual(calls['pools'],3)       # stops polling once not selling
  self.assertLess(summ['last_selling_seen_at'],summ['first_not_selling_seen_at'])
  self.assertFalse((folder/'race_01_preoff_samples.json').exists());self.assertFalse((folder/'race_01_latest.json').exists())   # private-read indexes untouched
  self.assertEqual(len(list(folder.glob('poolstate_race_01_*.jsonl.gz'))),1);self.assertEqual(len(list(folder.glob('race_01_2027*.jsonl.gz'))),0);d.cleanup()
 def test_probe_capped_at_ten_minutes(self):
  with patch.dict(c.os.environ,{'STOP_SELL_PROBE_MINUTES':'60'}):self.assertEqual(c.probe_minutes(),10)
  with patch.dict(c.os.environ,{'STOP_SELL_PROBE_MINUTES':'x'}):self.assertEqual(c.probe_minutes(),0)
 def test_watchdog(self):
  m=c.calendar({'raceMeetings':[self.meeting()]});at=datetime(2027,1,1,4,0,tzinfo=timezone.utc)
  with tempfile.TemporaryDirectory() as d:
   state=Path(d);ok,f=c.watchdog(state,m,at);self.assertFalse(ok);self.assertEqual(f[0]['status'],'ALERT_recorder_not_started')
   c.atomic(state/'session.json',{'eligible':True,'meeting_id':m[0]['id']});c.atomic(state/'heartbeat.json',{'checked_at':(at-timedelta(minutes=9)).isoformat()})
   ok,f=c.watchdog(state,m,at);self.assertFalse(ok);self.assertEqual(f[0]['status'],'ALERT_heartbeat_stale')
   c.atomic(state/'heartbeat.json',{'checked_at':(at-timedelta(minutes=1)).isoformat()});ok,f=c.watchdog(state,m,at);self.assertTrue(ok)
   ok,f=c.watchdog(state,m,at-timedelta(hours=3));self.assertTrue(ok);self.assertEqual(f[0]['status'],'outside_window')
if __name__=='__main__':unittest.main()
