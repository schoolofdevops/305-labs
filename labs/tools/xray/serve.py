#!/usr/bin/env python3
"""LLM Stack X-Ray — local adapter.

Serves the static X-Ray page AND proxies /ollama/* to the learner's local
Ollama server. One origin for both, so the page needs no tokens and no CORS —
the same trick kubectl proxy uses for the Kubernetes API.

Python stdlib only. No dependencies.
"""
import http.server
import json
import os
import urllib.error
import urllib.request

PORT = int(os.environ.get("PORT", "8010"))
OLLAMA = os.environ.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434").rstrip("/")
DIR = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def log_message(self, *args):  # keep the terminal quiet; the page shows state
        pass

    def do_GET(self):
        if self.path.startswith("/ollama/"):
            self._proxy("GET")
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/ollama/"):
            self._proxy("POST")
        else:
            self.send_error(405)

    def _proxy(self, method):
        url = OLLAMA + self.path[len("/ollama"):]
        body = None
        if method == "POST":
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else None
        req = urllib.request.Request(
            url, data=body, method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                self.send_response(resp.status)
                self.send_header(
                    "Content-Type",
                    resp.headers.get("Content-Type", "application/json"),
                )
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                # Ollama streams NDJSON — forward line by line so the page
                # sees tokens the moment the server emits them.
                for line in resp:
                    try:
                        self.wfile.write(line)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return  # client hit Stop; drop the stream quietly
        except urllib.error.HTTPError as e:
            payload = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload or json.dumps({"error": str(e)}).encode())
        except (urllib.error.URLError, ConnectionError) as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(
                {"error": f"Ollama unreachable at {OLLAMA} — is it running?",
                 "detail": str(e)}
            ).encode())


def main():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"LLM Stack X-Ray serving on http://127.0.0.1:{PORT}/  (proxy → {OLLAMA})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
