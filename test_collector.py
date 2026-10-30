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
 def test_no_redirect(self):
  with self.assertRaises(ValueError):c.NoRedirect().redirect_request(None,None,None,None,None,None)
 def test_public_source_export_file_allowlist(self):
  allowed={'collector.py','publish.py','test_collector.py','README.md','SECURITY.md','.gitignore','queries/calendar.graphql','queries/pools.graphql','.github/workflows/collect.yml','.github/CODEOWNERS'}
  files={str(p.relative_to(c.ROOT)) for p in c.ROOT.rglob('*') if p.is_file() and '__pycache__' not in str(p) and '.git' not in p.relative_to(c.ROOT).parts}
  self.assertLessEqual(files,allowed)
if __name__=='__main__':unittest.main()
