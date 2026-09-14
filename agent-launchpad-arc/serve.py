#!/usr/bin/env python3
"""Tiny local server to run the AgentLaunchpad explorer in a browser.

Bypasses Arc RPC CORS by proxying /rpc on the same origin.
  python3 serve.py   -> http://localhost:8666
Then open http://localhost:8666  (read-only explorer; it never signs anything).

Requires frontend/config.js  — generate it first:  python3 gen_frontend.py
"""
import json, os, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DEP = json.load(open(os.path.join(HERE, "deployment.json")))
ARC = DEP["rpc"]


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(open(os.path.join(HERE, "index.html"), "rb").read(), "text/html")
        if self.path == "/config.js":
            return self._send(open(os.path.join(HERE, "config.js"), "rb").read(), "text/javascript")
        self.send_response(404); self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        import requests
        try:
            r = requests.post(ARC, data=body, headers={"Content-Type": "application/json",
                                                       "User-Agent": "Mozilla/5.0 AgentLaunchpadExplorer"},
                              timeout=20)
            return self._send(r.content)
        except Exception as e:
            return self._send(json.dumps({"error": str(e)}).encode(), "text/json")

    def log_message(self, *a): pass


print("AgentLaunchpad explorer -> http://localhost:8666")
HTTPServer(("0.0.0.0", 8666), H).serve_forever()
