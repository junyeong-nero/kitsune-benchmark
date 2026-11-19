from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from secrets import token_urlsafe
from threading import Thread
from urllib.parse import parse_qs

from testset.pages import PAGES


def render(task):
    return (f'<!doctype html><meta charset=utf-8><title>{task}</title><h1>{task.title()}</h1>'
            '<style>body{font:18px system-ui;max-width:48em;margin:3em auto}label,details{display:block;margin:1em 0}th,td{padding:.4em}</style>'
            f'<form method="post">{PAGES[task]}</form>')


@contextmanager
def fixture(task):
    path = '/' + token_urlsafe(18)
    submissions = []
    page = render(task).encode()

    class Handler(BaseHTTPRequestHandler):
        def reply(self, body):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != path:
                return self.send_error(404)
            self.reply(page)

        def do_POST(self):
            if self.path != path:
                return self.send_error(404)
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8192:
                return self.send_error(400)
            values = parse_qs(self.rfile.read(length).decode(), keep_blank_values=True)
            submissions.append({k: sorted(v) if k == 'channels' or len(v) != 1 else v[0] for k, v in values.items()})
            self.reply(b'<title>Receipt</title><h1>Recorded</h1>')

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        thread = Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05})
        thread.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}{path}', submissions
        finally:
            server.shutdown()
            thread.join()
