"""One-battle offline action reconstruction; v2.2 must be selected explicitly."""
from pathlib import Path
import argparse
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_evidence.action_offline import run

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--battle',type=int,required=True,choices=range(5,13))
    p.add_argument('--visual-version',required=True,choices=['v2.2'])
    p.add_argument('--profile',default='champions-evidence-only-v1',choices=['champions-evidence-only-v1','showdown-champions-reference-v1'])
    p.add_argument('--reviews',type=Path)
    a=p.parse_args();print(json.dumps(run(a.battle,profile=a.profile,reviews=json.loads(a.reviews.read_text()) if a.reviews else None),ensure_ascii=False),flush=True)
