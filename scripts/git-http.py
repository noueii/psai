#!/usr/bin/env python3
"""Maintainer-only: serve the bare git repos in a folder over smart HTTP on localhost (git http-backend), so the
consumer-install proof can install from a git URL the way users install from GitHub, with no network.
Usage: git-http.py <folder> [--port 8765]     then: git clone http://127.0.0.1:8765/<name>.git
"""
import os
import subprocess
import sys
from wsgiref.simple_server import WSGIRequestHandler, make_server


class Quiet(WSGIRequestHandler):
    def log_message(self, *a):
        pass


def app(root):
    def handle(environ, start):
        env = {k: v for k, v in environ.items() if isinstance(v, str)}
        env.update(GIT_PROJECT_ROOT=root, GIT_HTTP_EXPORT_ALL="1", PATH=os.environ["PATH"])
        body = environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH") or 0))
        out = subprocess.run(["git", "http-backend"], input=body, env=env, capture_output=True).stdout
        head, _, data = out.partition(b"\r\n\r\n")
        if not _:
            head, _, data = out.partition(b"\n\n")
        status, headers = "200 OK", []
        for line in head.decode(errors="replace").splitlines():
            k, _, v = line.partition(":")
            if k.lower() == "status":
                status = v.strip()
            elif k:
                headers.append((k, v.strip()))
        start(status, headers)
        return [data]
    return handle


if __name__ == "__main__":
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
    make_server("127.0.0.1", port, app(os.path.realpath(sys.argv[1])), handler_class=Quiet).serve_forever()
