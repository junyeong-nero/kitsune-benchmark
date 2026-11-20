"""Give Aside a unique loopback tab to attach to before signing in."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from secrets import token_urlsafe
from threading import Thread


@contextmanager
def launch():
    path = '/' + token_urlsafe(18)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != path:
                return self.send_error(404)
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'<!doctype html><title>Benchmark task</title>')

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        thread = Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05})
        thread.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}{path}'
        finally:
            server.shutdown()
            thread.join()
