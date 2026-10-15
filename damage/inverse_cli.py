"""JSON inverse API: python -m damage.inverse_cli [request.json], or stdin."""
import argparse
import json
import sys
from .inverse import infer_attack_stat, _int, InputError


def solve(request):
    if not isinstance(request,dict) or not {'observations','candidate_stats'} <= set(request) or set(request) - {
        'observations','candidate_stats','stat','ruleset','variables','continuity','limits','domain_provenance'}:
        raise InputError('Supply observations and candidate_stats; unknown request fields are rejected')
    request = dict(request)
    domain = request['candidate_stats']
    if isinstance(domain,dict):
        if set(domain) != {'minimum','maximum'}:
            raise InputError('Candidate range requires minimum and maximum')
        low,high = _int(domain['minimum'],1),_int(domain['maximum'],1)
        if low > high: raise InputError('Reversed candidate range')
        request['candidate_stats'] = range(low,high+1)
    return infer_attack_stat(**request)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request',nargs='?')
    args = parser.parse_args()
    try:
        def reject_constant(value): raise InputError('Non-finite JSON value: '+value)
        if args.request:
            with open(args.request) as stream: request=json.load(stream,parse_constant=reject_constant)
        else:
            request=json.load(sys.stdin,parse_constant=reject_constant)
        result=solve(request)
    except (OSError,ValueError,TypeError) as exc:
        # Use the same response contract for parse/shape failures.
        result=infer_attack_stat(observations=[],candidate_stats=[])
        result['diagnostics']=[{'reason':str(exc),'input_status':'invalid_json_request'}]
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,allow_nan=False))
    return 0 if result['status'] in {'exact','conditional','empty'} else 2


if __name__=='__main__':
    sys.exit(main())
