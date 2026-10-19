"""Compatibility verifier for the historical v4 outputs.

The former source-specific v3-to-v4 migration is archived. This command verifies
existing immutable outputs only; it does not reuse them under changed sources.
"""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from scripts.report_entry_hud import verify_saved_run


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',required=True)
    args=p.parse_args()
    print(json.dumps(verify_saved_run(BattleArtifacts(args.battle),'m238-entry-hud-v4')))


if __name__=='__main__':main()
