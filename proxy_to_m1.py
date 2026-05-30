"""Tiny reverse proxy: forward all requests to M1 API."""
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request

TARGET = "http://192.168.3.28:8600"

class Proxy(BaseHTTPRequestHandler):
    def do_GET(self): self._proxy("GET")
    def do_POST(self): self._proxy("POST")
    def do_DELETE(self): self._proxy("DELETE")
    def do_OPTIONS(self): self._proxy("OPTIONS")

    def _proxy(self, method):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(TARGET + self.path, data=body, method=method)
        for k, v in self.headers.items():
            if k.lower() not in ("host", "connection"):
                req.add_header(k, v)
        try:
            resp = urllib.request.urlopen(req, timeout=300)
            self.send_response(resp.status)
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(resp.read())
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(e).encode())

HTTPServer(("0.0.0.0", 8601), Proxy).serve_forever()
