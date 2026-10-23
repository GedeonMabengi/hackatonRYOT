"""Run: py test_agent.py  (offline; uses a local fake MCP server)"""
import json, os, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import agent

MODE = {"sse": False, "fail": False}


class Fake(BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert self.headers["Authorization"] == "Bearer k"
        if MODE["fail"]:
            resp = {"jsonrpc": "2.0", "id": req["id"], "error": {"code": -1, "message": "boom"}}
        else:
            resp = {"jsonrpc": "2.0", "id": req["id"], "result": {"content": [{"type": "text", "text": "ok"}]}}
        body = json.dumps(resp)
        if MODE["sse"]:
            body = "event: message\ndata: " + body + "\n\n"
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *a):
        pass


srv = HTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.chdir(tempfile.mkdtemp())
os.environ["RYO_MCP_URL"] = f"http://127.0.0.1:{srv.server_port}/"

# no key -> NO_DATA, no network
os.environ.pop("RYO_MCP_KEY", None)
assert agent.log_trade()["decision"]["action"] == "NO_DATA"

os.environ["RYO_MCP_KEY"] = "k"
assert agent.log_trade()["decision"]["action"] == "REVIEW"       # plain JSON
MODE["sse"] = True
assert agent.log_trade()["decision"]["action"] == "REVIEW"       # SSE framing
MODE["fail"] = True
assert agent.log_trade()["decision"]["action"] == "NO_DATA"      # JSON-RPC error
srv.shutdown()
assert agent.log_trade()["decision"]["action"] == "NO_DATA"      # server down
assert agent.replay()

# tampering must be caught
lines = open(agent.JOURNAL).read().splitlines()
for bad in (lines[:1] + lines[2:],                                   # deleted row
            [lines[0].replace("NO_DATA", "REVIEW")] + lines[1:]):    # edited row
    open(agent.JOURNAL, "w").write("\n".join(bad) + "\n")
    try:
        agent.replay()
        raise SystemExit("tampering not detected")
    except ValueError:
        pass
print("all tests passed")
