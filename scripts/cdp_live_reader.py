"""Stream live market data from BRiSK via CDP (Chrome DevTools Protocol).

Hooks qrm.emplace in the BRiSK WASM decoder to capture all decoded market events
and outputs them as JSON-lines to stdout. This is the CDP fallback for when native
binary decoding isn't ready yet.

Run during market hours (09:00-15:00 JST).

Prerequisites:
  1. Launch Chrome with CDP enabled:
       /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
         --remote-debugging-port=9222 --user-data-dir=/tmp/brisk-chrome
  2. Open BRiSK Neo in the browser and log in
  3. Run this script:
       uv run python scripts/cdp_live_reader.py [--duration 60] [--output output.jsonl]

Output format (one JSON object per line):
  {"ts": "2026-03-12T09:00:01.234", "issue_id": 937, "code": "6740",
   "type": 1, "price10": 1060, "quantity": 100, "frame": 12345}
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import websockets.sync.client as ws_client

CDP_PORT = 9222
FRAMES_DIR = Path("docs/research/ws_frames")


class CDPClient:
    """Minimal CDP WebSocket client."""

    def __init__(self, ws_url: str):
        self.cdp = ws_client.connect(ws_url)
        self.msg_id = 0

    def send(self, method: str, params: dict | None = None) -> int:
        self.msg_id += 1
        msg = {"id": self.msg_id, "method": method}
        if params:
            msg["params"] = params
        self.cdp.send(json.dumps(msg))
        return self.msg_id

    def recv_until(self, msg_id: int, timeout: float = 15):
        self.cdp.socket.settimeout(timeout)
        while True:
            r = json.loads(self.cdp.recv())
            if "id" in r and r["id"] == msg_id:
                return r

    def evaluate(self, expr: str, await_promise: bool = False):
        mid = self.send("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": await_promise,
        })
        r = self.recv_until(mid)
        result = r.get("result", {}).get("result", {})
        return result.get("value", result.get("description"))

    def close(self):
        self.cdp.close()


def connect_to_brisk() -> CDPClient:
    """Find BRiSK tab and connect via CDP."""
    targets = httpx.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()
    brisk_tab = next(
        (t for t in targets if "sbi.brisk.jp/#" in t.get("url", "")), None
    )
    if not brisk_tab:
        print("ERROR: No BRiSK tab found!", file=sys.stderr)
        print("  1. Launch Chrome with --remote-debugging-port=9222", file=sys.stderr)
        print("  2. Open https://sbi.brisk.jp and log in", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to: {brisk_tab['title']}", file=sys.stderr)
    client = CDPClient(brisk_tab["webSocketDebuggerUrl"])
    client.send("Runtime.enable")
    client.recv_until(client.msg_id)
    return client


def setup_wasm_access(client: CDPClient):
    """Expose WASM memory via queryObjects for pointer->issue_id mapping."""
    for proto_name, global_name in [
        ("WebAssembly.Instance", "__wasm_instance"),
        ("WebAssembly.Memory", "__wasm_memory"),
    ]:
        mid = client.send("Runtime.evaluate", {
            "expression": f"{proto_name}.prototype",
            "returnByValue": False,
        })
        r = client.recv_until(mid)
        proto_id = r["result"]["result"]["objectId"]

        mid = client.send("Runtime.queryObjects", {"prototypeObjectId": proto_id})
        r = client.recv_until(mid)
        objects_id = r["result"]["objects"]["objectId"]

        mid = client.send("Runtime.callFunctionOn", {
            "objectId": objects_id,
            "functionDeclaration": f"function() {{ window.{global_name} = this[0]; return 'ok'; }}",
            "returnByValue": True,
        })
        client.recv_until(mid)

    print("WASM instance and memory exposed", file=sys.stderr)


def load_mappings(client: CDPClient) -> None:
    """Build stock_ptr -> {issue_id, code} mapping inside the browser.

    Uses _getStockPointer WASM export to get the correct pointer for each issue_id.
    Stores the mapping as window.__brisk_ptr_map so the hook can resolve
    stock pointers to issue_id/code without round-tripping to Python.
    """
    # Load issue_id -> code from local file
    iid_to_code = {}
    code_path = FRAMES_DIR / "issue_id_to_code.json"
    if code_path.exists():
        iid_to_code = json.loads(code_path.read_text())

    # Inject the code map and build ptr -> {iid, code} in browser
    client.evaluate(f"window.__brisk_code_map = {json.dumps(iid_to_code)};")

    count = client.evaluate("""
        (() => {
            const codes = window.__brisk_code_map;
            const getPtr = window.__wasm_instance.exports._getStockPointer;
            const m = {};
            // Use try/catch per stock to handle uninitialized entries
            for (let i = 0; i < 4445; i++) {
                try {
                    const ptr = getPtr(i);
                    if (ptr && ptr > 0) {
                        m[ptr] = [i, codes[String(i)] || '????'];
                    }
                } catch(e) {}
            }
            window.__brisk_ptr_map = m;
            return Object.keys(m).length;
        })()
    """)
    print(f"Loaded {count} stock mappings (in browser)", file=sys.stderr)


def install_hook(client: CDPClient):
    """Install qrm.emplace hook that buffers decoded entries with resolved stock info.

    The stock pointer passed to qrm.emplace differs from _getStockPointer values.
    We build a reverse mapping: for each _getStockPointer(i) we know the issue_id,
    and qrm stores data keyed by that pointer. The emplace `stock` param is a
    different pointer, but after emplace runs, qrm.qrs[stock] exists — so we
    can build the mapping by checking which _getStockPointer(i) matches.

    Simpler approach: use _getStockPointer in reverse — read the stock struct at
    the emplace pointer to find the stock code, or just let emplace run and read
    the result from qrm to get the mapping.

    Simplest: build a ptr->issue_id lookup from qrm.qrs keys (which match
    _getStockPointer output) and also maintain a runtime cache mapping the
    emplace stock param to the qrm.qrs key it ultimately stores under.
    """
    result = client.evaluate("""
        (() => {
            window.__brisk_buf = [];
            window.__brisk_active = true;

            // Build reverse map: qrm.qrs key (= _getStockPointer ptr) -> issue_id
            const codes = window.__brisk_code_map || {};
            const getPtr = window.__wasm_instance.exports._getStockPointer;
            const qrsKeyToIid = {};
            for (let i = 0; i < 4445; i++) {
                try {
                    const ptr = getPtr(i);
                    if (ptr && ptr > 0) {
                        qrsKeyToIid[ptr] = [i, codes[String(i)] || '????'];
                    }
                } catch(e) {}
            }

            // Runtime cache: emplace stock param -> [iid, code]
            const emplaceCache = {};

            function hookFn(stock, type, ts, price10, qty_raw, lot, frame) {
                if (window.__brisk_active) {
                    let info = emplaceCache[stock];
                    if (!info) {
                        // After original emplace, qrm.qrs will have an entry.
                        // Find which qrm.qrs key got this entry by checking
                        // all keys for a matching frameNumber.
                        // Optimization: just check if stock matches any qrsKeyToIid key directly
                        info = qrsKeyToIid[stock];
                        if (!info) {
                            // The stock param might differ from _getStockPointer.
                            // Try reading stock code from WASM memory at stock+564 (4 bytes ASCII)
                            try {
                                const mem = new Uint8Array(window.__wasm_memory.buffer);
                                const codeBytes = mem.slice(stock + 564, stock + 568);
                                const code = String.fromCharCode(...codeBytes).trim();
                                // Find issue_id by code
                                let iid = -1;
                                for (const [k, v] of Object.entries(codes)) {
                                    if (v === code) { iid = parseInt(k); break; }
                                }
                                info = [iid, code || '????'];
                            } catch(e) {
                                info = [-1, '????'];
                            }
                        }
                        emplaceCache[stock] = info;
                    }
                    window.__brisk_buf.push([info[0], info[1], type, ts, price10, qty_raw * lot, frame, Date.now()]);
                }
                return window.__brisk_orig_emplace.call(qrm, stock, type, ts, price10, qty_raw, lot, frame);
            }

            if (window.__brisk_orig_emplace) {
                qrm.emplace = hookFn;
                return 're-hooked (' + Object.keys(qrsKeyToIid).length + ' ptrs)';
            }

            window.__brisk_orig_emplace = qrm.__proto__.emplace;
            qrm.emplace = hookFn;
            return 'hooked (' + Object.keys(qrsKeyToIid).length + ' ptrs)';
        })()
    """)
    print(f"Hook: {result}", file=sys.stderr)


def drain_buffer(client: CDPClient) -> list:
    """Drain buffered entries from browser and return as list."""
    data = client.evaluate("""
        (() => {
            const buf = window.__brisk_buf;
            window.__brisk_buf = [];
            return buf;
        })()
    """)
    return data if isinstance(data, list) else []


def stream_data(client: CDPClient, duration: int, output):
    """Main streaming loop: drain buffer every 500ms, write JSONL."""
    now_str = datetime.now().strftime("%H:%M:%S")
    print(f"Streaming started at {now_str} for {duration}s...", file=sys.stderr)

    stop = time.time() + duration
    total = 0
    poll_interval = 0.5

    while time.time() < stop:
        time.sleep(poll_interval)
        entries = drain_buffer(client)
        if not entries:
            continue

        for entry in entries:
            iid, code, etype, ts_raw, price10, quantity, frame, wall_ms = entry

            # ts_raw: nanoseconds since midnight JST from WASM decoder
            # wall_ms: Date.now() epoch millis (fallback for display)
            if ts_raw > 1e12:
                # Nanoseconds since midnight
                ts_s = ts_raw / 1e9
            elif ts_raw > 1e9:
                # Microseconds since midnight
                ts_s = ts_raw / 1e6
            else:
                # Fallback: use wall clock
                dt = datetime.fromtimestamp(wall_ms / 1000)
                ts_s = dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6

            hours = int(ts_s // 3600)
            minutes = int((ts_s % 3600) // 60)
            secs = ts_s % 60
            ts_str = f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

            record = {
                "ts": ts_str,
                "issue_id": iid,
                "code": code,
                "type": etype,
                "price10": price10,
                "quantity": quantity,
                "frame": frame,
            }
            output.write(json.dumps(record) + "\n")
            total += 1

        output.flush()

    print(f"Done. Total entries: {total}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Stream BRiSK live data via CDP")
    parser.add_argument("--duration", type=int, default=60,
                        help="Capture duration in seconds (default: 60)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output file path (default: stdout)")
    args = parser.parse_args()

    client = connect_to_brisk()
    setup_wasm_access(client)
    load_mappings(client)
    install_hook(client)

    # Wait briefly and check data flow
    time.sleep(2)
    count = client.evaluate("window.__brisk_buf?.length || 0")
    print(f"Entries after 2s warmup: {count}", file=sys.stderr)

    if count == 0:
        print("No data flowing. Is the market open (09:00-15:00 JST)?", file=sys.stderr)
        client.evaluate("window.__brisk_active = false;")
        client.close()
        sys.exit(1)

    # Drain warmup entries
    drain_buffer(client)

    # Stream
    output = open(args.output, "w") if args.output else sys.stdout
    try:
        stream_data(client, args.duration, output)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
    finally:
        client.evaluate("window.__brisk_active = false;")
        client.close()
        if args.output:
            output.close()


if __name__ == "__main__":
    main()
