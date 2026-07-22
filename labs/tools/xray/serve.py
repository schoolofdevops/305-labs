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
LLAMACPP = os.environ.get("LLAMACPP_URL", "http://127.0.0.1:8080").rstrip("/")
APP = os.environ.get("APP_URL", "http://127.0.0.1:8001").rstrip("/")
REGISTRY = os.environ.get("REGISTRY_URL", "http://127.0.0.1:5100").rstrip("/")
# K8s lens (M8): the page reaches the cluster through a learner-started
# `kubectl proxy --kubeconfig labs/opsmate/k8s/kubeconfig --port 8011` — the
# same same-origin trick, one hop further.
K8S = os.environ.get("K8S_PROXY_URL", "http://127.0.0.1:8011").rstrip("/")
# Traces lens (M10): Phoenix reached through the learner's port-forward
# (`kubectl port-forward svc/phoenix 16006:6006`).
PHOENIX = os.environ.get("PHOENIX_URL", "http://127.0.0.1:16006").rstrip("/")
# Spend lens (M12): the LiteLLM gateway. The master key is injected SERVER-SIDE
# here — the page never holds a credential (same reason kubectl proxy needs no
# token in the page). Override for a non-default key/port.
LITELLM = os.environ.get("LITELLM_URL", "http://127.0.0.1:4000").rstrip("/")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-master-smoke")
EVALS_DIR = os.environ.get(
    "EVALS_DIR",
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", "..", "opsmate", "evals")),
)
TRAIN_DIR = os.environ.get(
    "TRAIN_DIR",
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", "..", "opsmate", "train")),
)
DIR = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def log_message(self, *args):  # keep the terminal quiet; the page shows state
        pass

    PROXIES = (("/ollama/", "OLLAMA"), ("/llamacpp/", "LLAMACPP"), ("/app/", "APP"),
               ("/registry/", "REGISTRY"), ("/k8s/", "K8S"), ("/phoenix/", "PHOENIX"),
               ("/litellm/", "LITELLM"))

    def _route(self):
        for prefix, name in self.PROXIES:
            if self.path.startswith(prefix):
                return prefix, {"OLLAMA": OLLAMA, "LLAMACPP": LLAMACPP, "APP": APP,
                                "REGISTRY": REGISTRY, "K8S": K8S, "PHOENIX": PHOENIX,
                                "LITELLM": LITELLM}[name]
        return None, None

    def do_GET(self):
        if self.path.startswith("/evals/"):
            self._serve_local_file(EVALS_DIR, "/evals/", (".json",))
        elif self.path.startswith("/train/"):
            self._serve_local_file(TRAIN_DIR, "/train/", (".json", ".jsonl"))
        elif self._route()[0]:
            self._proxy("GET")
        else:
            super().do_GET()

    def _serve_local_file(self, base_dir, prefix, exts):
        # Serve result files (Evals lens M5, Train lens M6) from the opsmate
        # dirs. Filename only — no path traversal.
        name = os.path.basename(self.path[len(prefix):])
        path = os.path.join(base_dir, name)
        if not (name.endswith(exts) and os.path.isfile(path)):
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(
                {"error": f"{name} not found — run the module's steps first"}).encode())
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type",
                         "application/json" if name.endswith(".json") else "text/plain")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self._route()[0]:
            self._proxy("POST")
        else:
            self.send_error(405)

    def _proxy(self, method):
        prefix, base = self._route()
        url = base + self.path[len(prefix) - 1:]
        body = None
        if method == "POST":
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else None
        headers = {"Content-Type": "application/json"}
        if prefix == "/litellm/":
            # Server-side credential injection (Spend lens, M12): the browser
            # page never sees the master key.
            headers["Authorization"] = f"Bearer {LITELLM_KEY}"
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                self.send_response(resp.status)
                self.send_header(
                    "Content-Type",
                    resp.headers.get("Content-Type", "application/json"),
                )
                if resp.headers.get("Docker-Content-Digest"):
                    self.send_header("Docker-Content-Digest",
                                     resp.headers["Docker-Content-Digest"])
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
