from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer

from services.saas.db import connect_database, initialize_database
from services.saas.http_service import SaasHttpApp
from services.saas.runtime import RuntimeConfig, load_runtime_config


def create_http_server(config: RuntimeConfig) -> HTTPServer:
    conn = connect_database(config.database_path)
    initialize_database(conn)
    app = SaasHttpApp(
        conn,
        min_submit_credit_minutes=config.min_submit_credit_minutes,
    )
    server = HTTPServer(
        (config.api_host, config.api_port),
        _handler_for(app),
    )
    server.saas_connection = conn
    return server


def _handler_for(app: SaasHttpApp):
    class SaasRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._dispatch()

        def do_POST(self):
            self._dispatch()

        def do_DELETE(self):
            self._dispatch()

        def _dispatch(self):
            length = int(self.headers.get("Content-Length", "0"))
            response = app.handle(
                self.command,
                self.path,
                headers=dict(self.headers.items()),
                body=self.rfile.read(length) if length else b"",
            )
            self.send_response(response.status_code)
            for key, value in response.headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

        def log_message(self, format, *args):
            return

    return SaasRequestHandler


def main(argv: list[str] | None = None) -> int:
    server = create_http_server(load_runtime_config())
    try:
        server.serve_forever()
    finally:
        server.server_close()
        connection = getattr(server, "saas_connection", None)
        if connection is not None:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
