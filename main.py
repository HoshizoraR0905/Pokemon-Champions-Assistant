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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--image', type=Path)
    inputs.add_argument('--video', type=Path)
    parser.add_argument('--annotated', type=Path, help='Image output path or video annotation directory')
    parser.add_argument('--interval',type=float,default=1.0,help='Video sampling interval in seconds')
    parser.add_argument('--max-frames',type=int)
    parser.add_argument('--language',default='chi_sim+eng')
    parser.add_argument('--no-knowledge',action='store_true',help='Use raw OCR acceptance only (baseline)')
    parser.add_argument('--verified-team',type=Path,help='Explicitly verified team JSON; see README')
    args = parser.parse_args()
    try:
        if args.no_knowledge and args.verified_team:
            raise ValueError('--verified-team requires knowledge recognition')
        resolver = None if args.no_knowledge else EntityResolver()
        context = RecognitionContext(resolver.knowledge if resolver else None)
        if args.verified_team:
            context.load_verified(args.verified_team,resolver.knowledge)
        recognizer = Recognizer(OCR(args.language),knowledge=not args.no_knowledge,resolver=resolver,context=context)
        tracker = Tracker()
        frames = [load_image(args.image)] if args.image else video_frames(args.video,args.interval,args.max_frames)
        for frame in frames:
            result = recognizer.recognize(frame)
            events = tracker.update(result)
            output = result.to_dict()
            output['events'] = [asdict(e) for e in events]
            output['own_team'] = {k:{f:asdict(v) for f,v in c.items()} for k,c in tracker.team.items()}
            print(json.dumps(output, ensure_ascii=False, indent=2 if args.image else None))
            if args.annotated:
                path = args.annotated if args.image else args.annotated / f'frame_{frame.index:08d}.png'
                annotate(frame,result,path)
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc),file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
