"""Offline inference and one-battle cached-evidence audit CLI."""
import argparse
import json
from pathlib import Path
from .posterior import infer
from .controlled import experiment
from .offline import atomic_json,audit_battle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('infer');p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True)
    p=sub.add_parser('controlled');p.add_argument('--output',type=Path,required=True)
    p=sub.add_parser('audit');p.add_argument('--battle',type=int,choices=range(5,10),required=True)
    args=parser.parse_args()
    if args.command=='audit':print(json.dumps(audit_battle(args.battle),ensure_ascii=False));return
    request=experiment() if args.command=='controlled' else json.loads(args.input.read_text())
    result=infer(**request);atomic_json(args.output,result)
    p=result['posterior'];print(json.dumps(dict(output=str(args.output),support=p['support'],mean=p['mean'],
        status=p['status'],information_gain_nats=p['information_gain_nats']),ensure_ascii=False))


if __name__=='__main__':main()
