"""Local images and prerecorded video. JSON on stdout; errors on stderr."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from capture import load_image, video_frames
from recognition import Recognizer, annotate
from recognition.ocr import OCR
from tracking import Tracker
from recognition.context import RecognitionContext
from recognition.entities import EntityResolver
from recognition.paddle_ocr import create_ocr
from team_configuration import TeamConfiguration


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--image', type=Path)
    inputs.add_argument('--images', nargs='+', type=Path, help='Collect configuration from several screenshots')
    inputs.add_argument('--video', type=Path)
    parser.add_argument('--annotated', type=Path, help='Image output path or video annotation directory')
    parser.add_argument('--interval',type=float,default=1.0,help='Video sampling interval in seconds')
    parser.add_argument('--max-frames',type=int)
    parser.add_argument('--language',default='chi_sim+eng')
    parser.add_argument('--ocr',choices=['auto','paddle-v6','paddle-v5','tesseract'],default='auto')
    parser.add_argument('--verbose',action='store_true',help='Print full diagnostic JSON')
    parser.add_argument('--json-out',type=Path,help='Write full machine-readable JSON')
    parser.add_argument('--no-icons',action='store_true',help='Disable local visual matching')
    parser.add_argument('--no-knowledge',action='store_true',help='Use raw OCR acceptance only (baseline)')
    parser.add_argument('--verified-team',type=Path,help='Explicitly verified team JSON; see README')
    parser.add_argument('--collect-team',action='store_true',help='Accumulate configuration in data/teams/my_team.json')
    parser.add_argument('--team-out',type=Path,default=Path('data/teams/my_team.json'))
    parser.add_argument('--team-id',default='my_team')
    parser.add_argument('--team-summary',action='store_true',help='Display saved team and missing fields')
    parser.add_argument('--team-corrections',type=Path,help='Apply manually reviewed JSON corrections')
    args = parser.parse_args()
    try:
        collecting = args.collect_team or bool(args.images)
        if not (args.image or args.images or args.video or args.team_summary or args.team_corrections):
            parser.error('provide --image, --images, --video, --team-summary, or --team-corrections')
        if args.team_corrections and not args.team_out.exists():
            raise ValueError(f'Team file does not exist: {args.team_out}')
        if args.no_knowledge and args.verified_team:
            raise ValueError('--verified-team requires knowledge recognition')
        if collecting and args.no_knowledge:
            raise ValueError('Team collection requires canonical knowledge recognition')
        resolver = None if args.no_knowledge else EntityResolver()
        team = None
        if collecting or args.team_summary or args.team_corrections:
            team = (TeamConfiguration.load(args.team_out,resolver.knowledge if resolver else None)
                    if args.team_out.exists() else TeamConfiguration(resolver.knowledge if resolver else None,
                                                                     team_id=args.team_id))
        if args.team_corrections:
            corrections = json.loads(args.team_corrections.read_text(encoding='utf-8'))
            if not isinstance(corrections, list):
                raise ValueError('Corrections must be a JSON array')
            for correction in corrections:
                team.correct(correction['instance_id'], correction['field'],
                             value=correction.get('value'),canonical_id=correction.get('canonical_id'),
                             reviewer=correction['reviewer'],note=correction.get('note',''))
            team.save(args.team_out)
        if not (args.image or args.images or args.video):
            if team: print(team.summary())
            return 0
        context = RecognitionContext(resolver.knowledge if resolver else None)
        if args.verified_team:
            context.load_verified(args.verified_team,resolver.knowledge)
        recognizer = Recognizer(create_ocr(args.ocr,args.language),knowledge=not args.no_knowledge,
                                resolver=resolver,context=context,icons=not args.no_icons)
        tracker = Tracker()
        frames = ([load_image(path) for path in args.images] if args.images else
                  [load_image(args.image)] if args.image else
                  video_frames(args.video,args.interval,args.max_frames))
        for frame in frames:
            result = recognizer.recognize(frame)
            if team and collecting and team.ingest(result):
                team.save(args.team_out)
            events = tracker.update(result)
            output = result.to_dict()
            output['events'] = [asdict(e) for e in events]
            output['own_team'] = {k:{f:asdict(v) for f,v in c.items()} for k,c in tracker.team.items()}
            if args.json_out:
                args.json_out.parent.mkdir(parents=True,exist_ok=True)
                with args.json_out.open('a',encoding='utf-8') as f:
                    f.write(json.dumps(output,ensure_ascii=False)+'\n')
            if args.verbose:
                print(json.dumps(output,ensure_ascii=False,indent=2 if args.image else None))
            else:
                print(f'{result.screen} · {frame.source}' + (f' · frame {frame.index}' if args.video else ''))
                for p in result.pokemon:
                    label=p.species.value or 'unresolved'
                    status=p.species.resolution.status if p.species.resolution else 'unresolved'
                    print(f'  {p.slot}: {label} ({status})')
                for move in result.moves:
                    print(f'  move {move.slot}: {move.name.value or "unresolved"}')
                if result.warnings:print('  warnings: '+'; '.join(result.warnings))
            if args.annotated:
                path = args.annotated if args.image else args.annotated / f'frame_{frame.index:08d}.png'
                annotate(frame,result,path)
        if team and (collecting or args.team_summary):
            print(team.summary())
        return 0
    except (ValueError, OSError, ImportError, RuntimeError) as exc:
        print(str(exc),file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
