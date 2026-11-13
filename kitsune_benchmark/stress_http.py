"""Minimal synchronous loopback Streamable HTTP MCP client for load testing.

One persistent HTTP connection and independent MCP session per worker. No redirects,
proxies, retry, automatic reconnect or resume. Supports JSON and finite POST SSE
responses, with an absolute response deadline and bounded body size.
"""
import hashlib
import http.client
import json
import time

from .stress import Client


class HTTPClient(Client):
    def __init__(self, port, timeout):
        self.timeout = timeout
        self.serial = 0
        self.session = None
        self.protocol = '2024-11-05'
        self.connection = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
        self.close_error = None

    def _exchange(self, message=None, method='POST'):
        deadline = time.monotonic() + self.timeout
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream',
                   'Host': f'localhost:{self.connection.port}',
                   'MCP-Protocol-Version': self.protocol}
        if self.session:
            headers['Mcp-Session-Id'] = self.session
        self.connection.timeout = self.timeout
        if self.connection.sock:
            self.connection.sock.settimeout(self.timeout)
        self.connection.request(method, '/mcp', body=json.dumps(message) if message is not None else None,
                                headers=headers)
        if self.connection.sock:
            self.connection.sock.settimeout(max(.001, deadline - time.monotonic()))
        response = self.connection.getresponse()
        token = response.getheader('Mcp-Session-Id')
        if token:
            if self.session and self.session != token:
                raise ValueError('MCP session changed unexpectedly')
            self.session = token
        body = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('HTTP MCP response deadline')
            if self.connection.sock:
                self.connection.sock.settimeout(remaining)
            chunk = response.read1(65536)
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > 4 * 1024 * 1024:
                raise ValueError('HTTP MCP response exceeded 4 MiB')
        if not 200 <= response.status < 300:
            raise ValueError(f'HTTP MCP status {response.status}: ' + bytes(body[:256]).decode('utf-8', errors='replace'))
        if not message or 'id' not in message:
            return None
        return decode_response(bytes(body), response.getheader('Content-Type', ''), message['id'])

    def send(self, message):
        self._exchange(message)

    def request(self, method, params):
        self.serial += 1
        return self._exchange({'jsonrpc': '2.0', 'id': self.serial, 'method': method, 'params': params})

    def initialize(self):
        result = super().initialize()
        if not self.session:
            raise ValueError('Server did not create an independent MCP session')
        self.protocol = self.metadata.get('protocolVersion', self.protocol)
        self.session_hash = hashlib.sha256(self.session.encode()).hexdigest()
        return result

    def close(self):
        if self.session:
            self.timeout = min(self.timeout, 2)
            try:
                self._exchange(method='DELETE')
            except (OSError, ValueError, http.client.HTTPException) as exc:
                self.close_error = type(exc).__name__
            finally:
                self.session = None
        self.connection.close()


def decode_response(body, content_type, request_id):
    if 'text/event-stream' in content_type:
        events = body.decode('utf-8').replace('\r\n', '\n').split('\n\n')
        messages = []
        for event in events:
            data = '\n'.join(line[5:].lstrip(' ') for line in event.split('\n') if line.startswith('data:'))
            if data:
                messages.append(json.loads(data))
    elif 'application/json' in content_type:
        messages = [json.loads(body)]
    else:
        raise ValueError('Unsupported HTTP MCP content type')
    matched = [m for m in messages if isinstance(m, dict) and m.get('id') == request_id
               and ('result' in m or 'error' in m)]
    if len(matched) != 1:
        raise ValueError('HTTP MCP response ID mismatch or duplicate response')
    return matched[0]
