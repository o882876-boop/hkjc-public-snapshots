"""Write only public data to this repository, with its short-lived scoped token."""
from pathlib import Path
import os,subprocess,base64,fcntl,argparse
REPOSITORY='o882876-boop/hkjc-public-snapshots'
BOT='41898282+github-actions[bot]@users.noreply.github.com'
def git(*args,cwd=None,network=False,check=True):
 prefix=['git']
 if network:
  token=os.environ.get('GH_TOKEN','')
  if not token:raise ValueError('scoped job token required')
  header=base64.b64encode(('x-access-token:'+token).encode()).decode()
  prefix+=['-c','http.https://github.com/.extraheader=AUTHORIZATION: basic '+header]
 p=subprocess.run(prefix+list(args),cwd=cwd,capture_output=True,text=True)
 if check and p.returncode:raise RuntimeError('git operation failed: '+args[0])
 return p

def restore(state):
 state=Path(state).resolve()
 if os.environ.get('GITHUB_REPOSITORY')!=REPOSITORY:raise ValueError('unexpected repository')
 git('config','user.name','github-actions[bot]');git('config','user.email',BOT)
 exists=git('ls-remote','--exit-code','--heads','origin','public-data',network=True,check=False).returncode==0
 if exists:
  git('fetch','origin','public-data',network=True);git('worktree','add','-B','public-data',str(state),'FETCH_HEAD')
 else:
  git('worktree','add','--detach',str(state),'HEAD');git('checkout','--orphan','public-data',cwd=state);git('rm','-rf','.',cwd=state)
 (state/'.gitignore').write_text('.write.lock\n*.tmp\n')

def publish(state):
 state=Path(state).resolve()
 with (state/'.write.lock').open('a') as f:
  fcntl.flock(f,fcntl.LOCK_EX)
  # No directories from the source checkout or runner home can be staged.
  for name in ['calendar.json','session.json','heartbeat.json','completed.json','.gitignore','market']:
   if (state/name).exists():git('add','--',name,cwd=state)
 if git('diff','--cached','--quiet',cwd=state,check=False).returncode:git('commit','-m','Record public market observations',cwd=state)
 if git('rev-parse','--verify','HEAD',cwd=state,check=False).returncode==0:git('push','origin','HEAD:refs/heads/public-data',cwd=state,network=True)

def clean_initial_history():
 """This fresh public repository only: replace personal author metadata on main.
 Unreferenced copies/caches require GitHub support; no guarantee of erasure.
 """
 if os.environ.get('GITHUB_REPOSITORY')!=REPOSITORY or os.environ.get('GITHUB_REF')!='refs/heads/main':raise ValueError('wrong source repository')
 emails=git('log','--format=%ae').stdout.splitlines()
 if any('@users.noreply.github.com' not in x and x!='noreply@github.com' for x in emails):
  git('config','user.name','github-actions[bot]');git('config','user.email',BOT)
  tree=git('rev-parse','HEAD^{tree}').stdout.strip();root=git('commit-tree',tree,'-m','Initialize reviewed public-only recorder').stdout.strip()
  expected=git('rev-parse','HEAD').stdout.strip()
  git('push','origin',root+':refs/heads/main','--force-with-lease=refs/heads/main:'+expected,network=True)
  print('Fresh public source history uses bot author metadata; cached older objects are not guaranteed erased.')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['restore','publish','clean-initial-history']);p.add_argument('--state',default='/tmp/public-market-state');a=p.parse_args()
 if a.action=='restore':restore(a.state)
 elif a.action=='publish':publish(a.state)
 else:clean_initial_history()
