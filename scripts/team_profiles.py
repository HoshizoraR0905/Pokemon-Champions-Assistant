"""Register/list/export verified local builds, separately from battle evidence."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from team_configuration import TeamConfiguration
from team_configuration.profiles import TeamProfiles


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, default=ROOT/'.cache/team-profiles')
    sub = p.add_subparsers(dest='action', required=True)
    register = sub.add_parser('register')
    register.add_argument('profile_id'); register.add_argument('--configuration', type=Path, required=True)
    register.add_argument('--reviewer', required=True); register.add_argument('--label', default='')
    sub.add_parser('list')
    export = sub.add_parser('export')
    export.add_argument('profile_id'); export.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); profiles = TeamProfiles(a.directory)
    if a.action == 'register':
        print(profiles.register(a.profile_id, TeamConfiguration.load(a.configuration), reviewer=a.reviewer, label=a.label))
    elif a.action == 'list':
        print(json.dumps(profiles.list(), ensure_ascii=False, indent=2))
    else:
        if a.output.exists():
            raise FileExistsError(a.output)
        profiles.load(a.profile_id).save(a.output)
        print(a.output)


if __name__ == '__main__':
    main()
