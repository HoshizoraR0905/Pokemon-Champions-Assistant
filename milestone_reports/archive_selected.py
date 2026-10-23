"""Copy selected substantive reports, preserving originals and resolving links.

This is document packaging only. No study, evidence or cache is regenerated.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
SELECTION=[
 ('M3.1.2_Stat_Feasibility','reports/M3.1.2-champions-stat-feasibility.md',
  'Exact joint stat feasibility under pinned Champions rules; historical implementation and conditional mechanics validation.'),
 ('M3.2.2_Battle11_Speed','docs/m3.2.2-battle11-speed-report.md',
  'Evidence-linked, time-causal Speed inference case study. Historical source counts predate the occurrence-preserving M3.4.4/M3.5.1 selection.'),
 ('M3.5.1_Build_Similarity','reports/M3.5.1-build-similarity.md',
  'Completed offline SP/moveset association and unsupervised clustering experiment; mixed predictive findings, no accepted tactical taxonomy.'),
]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipts=[]
    for folder,source,context in SELECTION:
        original=ROOT/source; destination=HERE/'Previous_Milestones'/folder
        destination.mkdir(parents=True,exist_ok=True)
        copied=[]
        def link(match):
            bang,title,target=match.groups()
            if target.startswith(('https:','http:','#')):return match.group(0)
            path=(original.parent/target).resolve()
            if bang:
                if not path.exists():raise ValueError('Missing archive image '+str(path))
                if '.cache' in path.parts:
                    new=destination/'figures'/path.name;new.parent.mkdir(exist_ok=True)
                    shutil.copyfile(path,new);copied.append(dict(file=str(new.relative_to(HERE)),source=str(path.relative_to(ROOT)),sha256=sha(new)))
                    return f'![{title}](figures/{path.name})'
            if '.cache' in path.parts:
                return title+' (`'+str(path.relative_to(ROOT))+'`; optional local diagnostic, not distributed)'
            return f'{bang}[{title}]({os.path.relpath(path,destination)})'
        body=re.sub(r'(!?)\[([^\]]*)\]\(([^)]+)\)',link,original.read_text())
        header=f'> Archived research snapshot. {context} Original: `{source}`. Original files are preserved. Relative links are adjusted; cached numerical diagnostics are described as optional local artifacts. No independent acceptance is asserted.\n\n'
        archive=destination/'report.md';archive.write_text(header+body)
        receipts.append(dict(source=source,source_sha256=sha(original),archive=str(archive.relative_to(HERE)),archive_sha256=sha(archive),context=context,images=copied))
    (HERE/'Previous_Milestones/archive-provenance.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n')
    print('Archived',len(receipts),'selected reports; originals unchanged.')


if __name__=='__main__':main()
