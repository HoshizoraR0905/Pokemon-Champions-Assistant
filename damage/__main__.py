"""JSON stdin/file API: python -m damage [input.json]."""
import argparse,json,sys
from . import calculate,calculate_scenarios

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input',nargs='?');args=parser.parse_args()
    try:
        with open(args.input) if args.input else sys.stdin as stream:request=json.load(stream,parse_constant=lambda token: (_ for _ in ()).throw(ValueError('Non-finite JSON number: '+token)))
        result=calculate_scenarios(request) if isinstance(request,dict) and 'scenarios' in request else calculate(request)
    except (OSError,ValueError) as exc:result=dict(status='invalid_input',reason=str(exc),distribution=None)
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    return 0 if result['status'] in {'exact_reference','conditional_scenarios'} else 2
if __name__=='__main__':sys.exit(main())
