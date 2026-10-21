import argparse,json
from pathlib import Path
from .offline import run


def main():
    p=argparse.ArgumentParser(description='Reconstruct one cached battle; no OCR or damage inference')
    p.add_argument('--battle',type=int,choices=range(5,10),required=True)
    p.add_argument('--annotations',type=Path);p.add_argument('--builds',type=Path)
    p.add_argument('--historical-reviews',type=Path)
    a=p.parse_args()
    read=lambda path:json.loads(path.read_text()) if path else None
    print(json.dumps(run(a.battle,annotations=read(a.annotations),build_records=read(a.builds),historical_reviews=a.historical_reviews),ensure_ascii=False))


if __name__=='__main__':main()
