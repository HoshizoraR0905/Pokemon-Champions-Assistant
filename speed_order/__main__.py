"""JSON CLI: python -m speed_order [request.json]."""
import argparse,json,sys
from . import effective_speed,infer_speed,compare_speed


def solve(request):
    if not isinstance(request,dict) or set(request)!={'operation','input'} or request['operation'] not in ('effective','infer','compare'):
        raise ValueError('Supply operation effective/infer/compare and input')
    data=dict(request['input'])
    for key in ('candidate_speeds','opponent_speeds'):
        if isinstance(data.get(key),dict):
            value=data[key]
            if set(value)!={'minimum','maximum'} or any(type(value[k]) is not int for k in value) or not 1<=value['minimum']<=value['maximum']<=4095:
                raise ValueError('Inclusive Speed range must be integers 1..4095')
            data[key]=range(value['minimum'],value['maximum']+1)
    return {'effective':effective_speed,'infer':infer_speed,'compare':compare_speed}[request['operation']](**data)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('request',nargs='?');args=parser.parse_args()
    try:
        def reject(v):raise ValueError('Non-finite JSON '+v)
        if args.request:
            with open(args.request) as stream:request=json.load(stream,parse_constant=reject)
        else:request=json.load(sys.stdin,parse_constant=reject)
        result=solve(request)
    except (ValueError,TypeError,OSError) as exc:result=dict(schema_version=1,status='insufficient_information',diagnostics=[str(exc)])
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,allow_nan=False))
    return 2 if result['status'] in ('unsupported','insufficient_information') else 0

if __name__=='__main__':sys.exit(main())
