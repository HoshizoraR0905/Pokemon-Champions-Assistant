from functools import partial
from http.server import ThreadingHTTPServer
import threading
import urllib.request
import urllib.error
import pytest
from scripts.serve_visual_review import ReviewHandler


def test_local_review_video_ranges_and_escape_guard(tmp_path):
    (tmp_path/'video.mp4').write_bytes(b'0123456789')
    (tmp_path/'escape').symlink_to('/etc/hosts')
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(ReviewHandler,directory=str(tmp_path)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        for header,expected in [('bytes=2-5',b'2345'),('bytes=-3',b'789'),('bytes=8-',b'89')]:
            with opener.open(urllib.request.Request(base+'/video.mp4',headers={'Range':header})) as r:
                assert r.status==206 and r.read()==expected
                assert r.headers['Accept-Ranges']=='bytes'
        for path,code in [('/escape',403),('/video.mp4',416)]:
            with pytest.raises(urllib.error.HTTPError) as exc:
                opener.open(urllib.request.Request(base+path,headers={'Range':'bytes=30-40'}))
            assert exc.value.code==code
    finally:server.shutdown();server.server_close();thread.join()
