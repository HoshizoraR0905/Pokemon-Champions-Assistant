"""Localhost-only static review server with single HTTP byte ranges for MP4 seeking."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import re
import shutil

ROOT=Path(__file__).resolve().parents[1]


class ReviewHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        path=Path(self.translate_path(self.path)).resolve()
        if not path.is_relative_to(Path(self.directory).resolve()):
            self.send_error(403,'Outside review root');return None
        self._range_remaining=None
        header=self.headers.get('Range')
        if not header or not path.is_file():return super().send_head()
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
        size=path.stat().st_size
        if not match or not any(match.groups()):
            self.send_error(416,'Unsupported byte range');return None
        first,last=match.groups()
        start=int(first) if first else max(0,size-int(last))
        end=min(int(last),size-1) if first and last else size-1
        if start>=size or start>end:
            self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return None
        stream=path.open('rb');stream.seek(start);self._range_remaining=end-start+1
        self.send_response(206);self.send_header('Content-Type',self.guess_type(str(path)))
        self.send_header('Accept-Ranges','bytes');self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length',str(self._range_remaining));self.end_headers();return stream

    def copyfile(self,source,outputfile):
        remaining=self._range_remaining
        if remaining is None:return super().copyfile(source,outputfile)
        while remaining:
            block=source.read(min(64*1024,remaining))
            if not block:break
            outputfile.write(block);remaining-=len(block)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8766);a=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),partial(ReviewHandler,directory=str(ROOT)))
    print(f'http://127.0.0.1:{a.port}/.cache/m34-visual-v21/review.html',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
