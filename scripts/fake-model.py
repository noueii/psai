#!/usr/bin/env python3
"""Maintainer-only: a fake model server on localhost for the consumer-install proof. It answers the Anthropic
Messages API (/v1/messages) and the OpenAI Chat Completions API (/v1/chat/completions), streaming or not, always
with the text "ok", and saves every request body as <log dir>/<n>.json. The proof then greps those requests for the
nudge and the skills, so it shows what each tool really sends to a model, with no credentials and no network.
Usage: fake-model.py <log dir> [--port 8766]
"""
import itertools
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = os.path.realpath(sys.argv[1]) if len(sys.argv) > 1 else sys.exit(__doc__)
COUNT = itertools.count(1)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            return self.send(200, json.dumps({"object": "list", "data": [{"id": "fake-1", "object": "model"}]}))
        self.send(404, "{}")

    def do_HEAD(self):
        self.send(200, "")

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            req = json.loads(raw or b"{}")
        except ValueError:
            req = {"raw": raw.decode(errors="replace")}
        with open(os.path.join(LOG, f"{next(COUNT)}.json"), "w") as f:
            json.dump({"path": self.path, "body": req}, f)
        stream = bool(req.get("stream"))
        if "/messages" in self.path and "count_tokens" in self.path:
            return self.send(200, json.dumps({"input_tokens": 1}))
        if "/messages" in self.path:
            msg = {"id": "msg_fake", "type": "message", "role": "assistant", "model": req.get("model", "fake"),
                   "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn", "stop_sequence": None,
                   "usage": {"input_tokens": 1, "output_tokens": 1}}
            if not stream:
                return self.send(200, json.dumps(msg))
            ev = [("message_start", {"type": "message_start", "message": dict(msg, content=[], stop_reason=None)}),
                  ("content_block_start", {"type": "content_block_start", "index": 0,
                                           "content_block": {"type": "text", "text": ""}}),
                  ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                           "delta": {"type": "text_delta", "text": "ok"}}),
                  ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                  ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                                     "usage": {"output_tokens": 1}}),
                  ("message_stop", {"type": "message_stop"})]
            return self.send(200, "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in ev), "text/event-stream")
        base = {"id": "chatcmpl-fake", "created": 0, "model": req.get("model", "fake")}
        if not stream:
            return self.send(200, json.dumps(dict(base, object="chat.completion", choices=[
                {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})))
        chunks = [dict(base, object="chat.completion.chunk", choices=[{"index": 0, "delta": {"role": "assistant", "content": "ok"}, "finish_reason": None}]),
                  dict(base, object="chat.completion.chunk", choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}],
                       usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})]
        return self.send(200, "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n", "text/event-stream")


if __name__ == "__main__":
    os.makedirs(LOG, exist_ok=True)
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8766
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
