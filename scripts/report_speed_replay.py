"""M3.2.2 Stage A: one battle, sealed caches, deterministic evidence audit."""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_evidence.speed_replay_offline import run

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--battle',type=int,required=True,choices=[10,11,12])
    parser.add_argument('--visual-version',required=True,choices=['v2.2'])
    parser.add_argument('--reviews',type=Path,help='Optional source-backed v2 review attachments, keyed by retained relation ID')
    parser.add_argument('--max-configurations',type=int,default=100000)
    parser.add_argument('--max-evaluations',type=int,default=100000)
    args=parser.parse_args()
    reviews=json.loads(args.reviews.read_text()) if args.reviews else None
    print(json.dumps(run(args.battle,reviews=reviews,max_configurations=args.max_configurations,
                         max_evaluations=args.max_evaluations),ensure_ascii=False),flush=True)
