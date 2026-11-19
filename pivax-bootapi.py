#!/usr/bin/env python3
"""PiVAX boot-API -- send_keys/read_screen bridge for the PiVAX Hacker
Replicant (see README.md for the full picture). A small stdlib-only HTTP
server that exposes exactly two actions per machine on an existing `screen`
session, with a machine name in the URL path:

  GET  /api/vax/screen    -> {"text": "..."} hardcopy of the 'vax' screen session
  POST /api/vax/keys       body {"text": "..."} -> types into that same session

NOTE on the namespaced path shape: this script is written to serve more
than one co-located simulator from a single process -- the `SESSIONS` dict
below maps a machine name in the URL (e.g. "vax") to the actual `screen`
session name it should drive. The original internal deployment this was
adapted from happened to run a second, unrelated simulator (an HP3000) on
the same physical host, so the script kept a machine-namespace in the path
rather than hardcoding a single flat `/api/screen` + `/api/keys`. For a
single-machine PiVAX setup you only need the "vax" entry in SESSIONS --
delete any others. Kept this way (instead of flattening the path) so the
same script is a drop-in template if you ever add a second simulator next
to your PiVAX later.

Deliberately limited to reading and typing in the already-visible terminal
session (the same session your own web console attaches to): no shell, no
filesystem access beyond that. Runs as whichever user owns the `screen`
session. Listens on :8092, CORS open -- this is meant to be reachable from
the chat backend only; don't expose it to the public internet without
adding your own auth layer.
"""
import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# Map of <machine name in the URL> -> <screen session name>. Trim this down
# to just the machine(s) you actually run; for a single-machine PiVAX setup,
# keep only "vax".
SESSIONS = {"vax": "vax"}
HARDCOPY_TMPL = "/tmp/pivax-bootapi-hardcopy-{}.txt"


def send_keys(machine, text):
    session = SESSIONS[machine]
    literal = text.replace("\\r", "\r").replace("\\n", "\r")
    subprocess.run(["screen", "-S", session, "-X", "stuff", literal],
                   capture_output=True, timeout=10, check=True)


def read_screen(machine):
    session = SESSIONS[machine]
    hardcopy = HARDCOPY_TMPL.format(machine)
    try:
        os.remove(hardcopy)
    except OSError:
        pass
    subprocess.run(["screen", "-S", session, "-X", "hardcopy", hardcopy],
                   capture_output=True, timeout=10, check=True)
    for _ in range(10):
        if os.path.exists(hardcopy):
            break
        time.sleep(0.1)
    try:
        with open(hardcopy, errors="replace") as f:
            return f.read()
    except OSError:
        return "(could not read hardcopy)"


class Handler(BaseHTTPRequestHandler):
    def _respond(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def _parse_machine(self, path):
        parts = path.strip("/").split("/")
        # expected: api/<machine>/<action>
        if len(parts) != 3 or parts[0] != "api" or parts[1] not in SESSIONS:
            return None, None
        return parts[1], parts[2]

    def do_GET(self):
        path = urlparse(self.path).path
        machine, action = self._parse_machine(path)
        if machine and action == "screen":
            try:
                self._respond(200, {"text": read_screen(machine)})
            except Exception as e:
                self._respond(500, {"error": str(e)})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        machine, action = self._parse_machine(path)
        if machine and action == "keys":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._respond(400, {"error": "invalid JSON"})
                return
            text = payload.get("text", "")
            if not isinstance(text, str) or not text:
                self._respond(400, {"error": "'text' (string) is required"})
                return
            try:
                send_keys(machine, text)
                self._respond(200, {"ok": True})
            except Exception as e:
                self._respond(500, {"error": str(e)})
        else:
            self._respond(404, {"error": "not found"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8092), Handler).serve_forever()
