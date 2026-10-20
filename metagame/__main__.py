"""Current Pokémon Champions Ranked statistics application cache and offline queries."""
import argparse
import json
from pathlib import Path
import sys
from . import PILOT
from .common import encode
from .ingest import ingest
from .query import query, table, completeness
from .store import Store, prepare_root, locked

DEFAULT_ROOT = Path(__file__).resolve().parents[1]/'.cache/metagame/current-ranked'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=DEFAULT_ROOT)
    commands = parser.add_subparsers(dest='command', required=True)
    acquire = commands.add_parser('refresh', help='Refresh current documented API data; default nine-species pilot')
    acquire.add_argument('--species', nargs='+', default=list(PILOT))
    acquire.add_argument('--format', choices=['Doubles','Singles'], default='Doubles')
    acquire.add_argument('--refresh-hours', type=float, default=24.)
    acquire.add_argument('--retention-days', type=float, default=7.)
    acquire.add_argument('--max-versions', type=int, choices=[1,2,3], default=2)
    acquire.add_argument('--request-interval', type=float, default=2.)
    acquire.add_argument('--force', action='store_true', help='Conditional revalidation before freshness interval expires')
    lookup = commands.add_parser('query', help='Read SQLite only; no network or refresh')
    lookup.add_argument('species')
    lookup.add_argument('--teammate')
    lookup.add_argument('--format', choices=['Doubles','Singles'], default='Doubles')
    lookup.add_argument('--output', choices=['table','json'], default='table')
    lookup.add_argument('--top', type=int, default=5)
    lookup.add_argument('--max-age-hours', type=float, default=24.)
    commands.add_parser('coverage')
    commands.add_parser('snapshots')
    prune = commands.add_parser('prune', help='Apply bounded retention to this owned application cache only')
    prune.add_argument('--retention-days', type=float, default=7.)
    prune.add_argument('--max-versions', type=int, choices=[1,2,3], default=2)
    args = parser.parse_args(argv)
    try:
        if args.command=='refresh':
            result, path = ingest(args.cache, species=args.species, battle_format=args.format,
                refresh_seconds=args.refresh_hours*3600, interval=args.request_interval,
                retention_days=args.retention_days, max_versions=args.max_versions, force=args.force)
            print(encode(dict(status=result['status'], manifest=str(path), completed=len(result['completed']),
                             errors=result['errors'], http_requests=result['http_requests'])))
            return 0 if result['status']=='complete' else 1
        if args.command=='query':
            result = query(args.cache, args.species, teammate=args.teammate, battle_format=args.format, max_age_seconds=args.max_age_hours*3600)
            print(encode(result) if args.output=='json' else table(result, args.top))
            return 1 if result['status']=='not_cached' else 0
        if args.command=='coverage':
            print(encode(completeness(args.cache)))
        elif args.command=='snapshots':
            db = Store(args.cache, readonly=True)
            try:
                print(encode(db.snapshots()))
            finally:
                db.close()
        elif args.command=='prune':
            root = prepare_root(args.cache)
            with locked(root):
                db = Store(root)
                try:
                    print(encode(db.prune(retention_days=args.retention_days, max_versions=args.max_versions)))
                finally:
                    db.close()
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(encode(dict(status='error', diagnostics=[str(exc)])), file=sys.stderr)
        return 2


if __name__=='__main__':
    sys.exit(main())
