"""Read-only RYO MCP research, deterministic practice decisions, and hash-chained replay.

Run ``py agent.py`` to request live evidence and append one receipt. Replay an existing
journal without network access with ``py agent.py replay``.
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

JOURNAL = "journal.jsonl"
DEFAULT_MCP_URL = "https://app-ryochan.com/api/mcp"
TOOL = "market_overview"
GENESIS = "0" * 64


def _rpc(url, key, method, params=None, request_id=1):
    body = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method,
                       **({"params": params} if params is not None else {})}).encode()
    request = urllib.request.Request(url, body, {
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
        "Authorization": "Bearer " + key,
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8")
    # Streamable HTTP responses may use SSE; extract the JSON-RPC data event.
    if raw.lstrip().startswith("{"):
        return json.loads(raw)
    for line in raw.splitlines():
        if line.startswith("data:"):
            try:
                data = json.loads(line[5:].strip())
                if isinstance(data, dict) and "id" in data:
                    return data
            except json.JSONDecodeError:
                continue
    raise ValueError("MCP returned no JSON-RPC response")


def get_evidence(symbol=None):
    """Call RYO's read-only market_overview tool; errors are evidence, never prices."""
    key = os.environ.get("RYO_MCP_KEY")
    url = os.environ.get("RYO_MCP_URL", DEFAULT_MCP_URL)
    symbol = (symbol or os.environ.get("RYO_SYMBOL", "BTC")).upper()
    called_at = time.time()
    params = {"symbol": symbol}
    provenance = {"endpoint": url, "tool": TOOL, "parameters": params,
                  "requested_at": called_at, "transport": "MCP Streamable HTTP"}
    if not key:
        return {"status": "unavailable", "symbol": symbol, "provenance": provenance,
                "error": "RYO_MCP_KEY is not set; no market data was requested."}
    try:
        answer = _rpc(url, key, "tools/call", {"name": TOOL, "arguments": params})
        if "error" in answer:
            raise ValueError("MCP error: " + json.dumps(answer["error"], sort_keys=True))
        result = answer.get("result", {})
        if result.get("isError"):
            raise ValueError("Tool error: " + json.dumps(result.get("content", []), sort_keys=True))
        return {"status": "ok", "symbol": symbol, "provenance": provenance,
                "response": result}
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        return {"status": "unavailable", "symbol": symbol, "provenance": provenance,
                "error": f"{type(exc).__name__}: {exc}"}


def decide(ev):
    """Pure function from a stored evidence envelope to a deterministic decision."""
    if ev.get("status") != "ok":
        return {"action": "NO_DATA", "reasoning": ev.get("error", "Evidence unavailable"),
                "rule": "require_successful_source"}
    return {"action": "REVIEW", "reasoning":
            "RYO market overview captured. No price series is assumed; inspect the stored source response before forming a practice trade.",
            "rule": "market_overview_requires_review"}


def digest(ev, dec, previous_hash):
    payload = {"evidence": ev, "decision": dec, "previous_hash": previous_hash}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def log_trade():
    ev = get_evidence()
    dec = decide(ev)
    previous_hash = last_hash()
    entry = {"ts": time.time(), "evidence": ev, "decision": dec,
             "previous_hash": previous_hash}
    entry["hash"] = digest(ev, dec, previous_hash)
    with open(JOURNAL, "a", encoding="utf-8") as journal:
        journal.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
    return entry


def last_hash():
    previous = GENESIS
    if not os.path.exists(JOURNAL):
        return previous
    with open(JOURNAL, encoding="utf-8") as journal:
        for line in journal:
            if line.strip():
                previous = json.loads(line)["hash"]
    return previous


def replay():
    """Validate decisions and hash links, including legacy unchained journal rows."""
    previous = GENESIS
    if not os.path.exists(JOURNAL):
        return True
    with open(JOURNAL, encoding="utf-8") as journal:
        for number, line in enumerate(journal, 1):
            if not line.strip():
                continue
            entry = json.loads(line)
            decision = decide(entry["evidence"])
            if decision != entry["decision"]:
                raise ValueError(f"decision mismatch at line {number}")
            # Older rows predate hash chaining; preserve compatibility for replay.
            if "previous_hash" not in entry:
                if digest_legacy(entry["evidence"], decision) != entry["hash"]:
                    raise ValueError(f"legacy hash mismatch at line {number}")
                previous = entry["hash"]
                continue
            if entry["previous_hash"] != previous:
                raise ValueError(f"chain link mismatch at line {number}")
            if digest(entry["evidence"], decision, previous) != entry["hash"]:
                raise ValueError(f"hash mismatch at line {number}")
            previous = entry["hash"]
    return True


def digest_legacy(ev, dec):
    return hashlib.sha256(json.dumps([ev, dec], sort_keys=True).encode()).hexdigest()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "replay":
        replay()
        print("replay OK")
    else:
        print(json.dumps(log_trade(), indent=2, ensure_ascii=False))
