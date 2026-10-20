"""Published-design collection and explicit equal-build/equal-composition queries."""
import argparse
from pathlib import Path
import sys
from metagame.common import encode
from .adapters import SOURCES
from .collect import collect
from .query import query,coverage
from . import VERSION

DEFAULT=Path(__file__).resolve().parents[2]/'.cache/metagame/published-teams'


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',type=Path,default=DEFAULT)
    sub=p.add_subparsers(dest='command',required=True)
    ingest=sub.add_parser('collect')
    ingest.add_argument('--source',choices=SOURCES,required=True)
    ingest.add_argument('--limit',type=int)
    ingest.add_argument('--from-file',type=Path)
    ingest.add_argument('--receipt',type=Path)
    ingest.add_argument('--force',action='store_true')
    ingest.add_argument('--request-interval',type=float,default=2.)
    details=sub.add_parser('collect-details',help='Pinned licensed VGC Multicalc source data, including every locally paginated detail block')
    details.add_argument('--regulation',choices=['M-A','M-B','M-C'],default='M-C')
    from .vgcmulticalc import DEFAULT_REVISION
    details.add_argument('--revision',default=DEFAULT_REVISION)
    details.add_argument('--limit',type=int)
    details.add_argument('--request-interval',type=float,default=2.)
    public=sub.add_parser('collect-submissions',help='Public submissions only after reuse authorization is established')
    public.add_argument('--authorization-note',help='Record initial reuse authorization; subsequent runs reuse the local source authorization')
    public.add_argument('--regulation',choices=['M-A','M-B','M-C'],default='M-C')
    public.add_argument('--limit',type=int)
    public.add_argument('--request-interval',type=float,default=2.)
    lookup=sub.add_parser('query')
    lookup.add_argument('species')
    lookup.add_argument('--unit',choices=['unique_build','unique_composition','distinct_observed_configuration'],default='unique_build')
    lookup.add_argument('--teammate',nargs='+',default=[])
    lookup.add_argument('--without-teammate',nargs='+',default=[])
    lookup.add_argument('--given-move')
    lookup.add_argument('--move-pair',nargs=2)
    lookup.add_argument('--output',choices=['json','table'],default='table')
    report=sub.add_parser('coverage')
    for parser in (lookup,report):
        parser.add_argument('--population',choices=['community_published','tournament_published'],required=True)
        parser.add_argument('--regulation',required=True)
        parser.add_argument('--format',choices=['Doubles','Singles','Unknown'],default='Doubles')
        parser.add_argument('--identity-version',default=VERSION)
        parser.add_argument('--source',help='Select one source dataset; required for observed configurations')
    args=p.parse_args(argv)
    try:
        if args.command=='collect-submissions':
            from .submissions import collect as collect_public
            result,path=collect_public(args.database,authorization_note=args.authorization_note,
                regulation=args.regulation,limit=args.limit,interval=args.request_interval)
            print(encode(dict(status=result['status'],manifest=str(path),completed=len(result['completed']),errors=result['errors'],error=result.get('error'))))
            return 0 if result['status']=='complete' else 1
        if args.command=='collect-details':
            from .vgcmulticalc import collect as collect_details
            result,path=collect_details(args.database,regulation=args.regulation,revision=args.revision,
                limit=args.limit,interval=args.request_interval)
            print(encode(dict(status=result['status'],manifest=str(path),completed=len(result['completed']),errors=result['errors'],error=result.get('error'))))
            return 0 if result['status']=='complete' else 1
        if args.command=='collect':
            result,path=collect(args.database,args.source,limit=args.limit,from_file=args.from_file,
                receipt_file=args.receipt,force=args.force,interval=args.request_interval)
            print(encode(dict(status=result['status'],manifest=str(path),completed=len(result['completed']),
                errors=result['errors'],error=result.get('error'))))
            return 0 if result['status']=='complete' else 1
        if args.command=='coverage':
            print(encode(coverage(args.database,population=args.population,regulation=args.regulation,battle_format=args.format,version=args.identity_version,source=args.source)))
            return 0
        result=query(args.database,args.species,population=args.population,regulation=args.regulation,
            battle_format=args.format,unit=args.unit,teammates=args.teammate,exclude_teammates=args.without_teammate,given_move=args.given_move,move_pair=args.move_pair,version=args.identity_version,source=args.source)
        if args.output=='json':print(encode(result))
        else:
            print(f"Population: {args.population} | {args.regulation} {args.format} | estimator: {args.unit}")
            print(f"Distinct eligible designs: {result['total_eligible_designs']}; with species: {result['species_designs']}; with teammate context: {result['context_designs']}")
            print('Published-design corpus frequencies; not Ranked encounter probabilities. Small samples are uncertain.')
            print('Field | Canonical value | Count | Denominator | Observed frequency')
            print('--- | --- | ---: | ---: | ---:')
            for field,rows in result.get('field_distributions',{}).items():
                for row in rows:
                    print(f"{field} | {encode(row['value'])} | {row['numerator']} | {row['denominator']} | {row['estimate']}")
            if 'build_statistics' in result:print(result['build_statistics']['status'])
            for row in result.get('teammates',[]):
                r=row['frequency'];print(f"teammate | {row['canonical_id']} | {r['numerator']} | {r['denominator']} | {r['estimate']}")
            if result.get('status')!='observed_design_frequencies':print(result['status'])
            for link in result.get('source_links',[]):
                print(f"Source: {link['source_url']} | {link.get('attribution') or link['title']}")
        return 0
    except (OSError,ValueError,RuntimeError) as exc:
        print(encode(dict(status='error',diagnostics=[str(exc)])),file=sys.stderr);return 2


if __name__=='__main__':sys.exit(main())
