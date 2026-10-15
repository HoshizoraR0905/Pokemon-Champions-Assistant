"""JSON composition: python -m damage.champions_cli [request.json]."""
import argparse
import json
import sys
from .champions_feasibility import infer_champions_attack_stat


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('request',nargs='?');args=parser.parse_args()
    try:
        def reject(value):raise ValueError('Non-finite JSON: '+value)
        if args.request:
            with open(args.request) as stream:request=json.load(stream,parse_constant=reject)
        else:request=json.load(sys.stdin,parse_constant=reject)
        if not isinstance(request,dict):raise ValueError('Expected request object')
        result=infer_champions_attack_stat(**request)
    except (ValueError,TypeError,OSError) as exc:
        result=infer_champions_attack_stat(champions={});result['diagnostics']=[dict(reason=str(exc))]
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,allow_nan=False))
    return 0 if result['status'] in ('exact','conditional','empty') else 2


if __name__=='__main__':sys.exit(main())
