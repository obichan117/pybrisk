"""Correlate raw WebSocket frames with decoded qrm output during live trading.

Run this during market hours (09:00-15:00 JST).
It simultaneously:
1. Captures raw binary WebSocket frames via CDP Network events
2. Hooks qrm.emplace to capture decoded output (type, timestamp, price10, quantity, frameNumber)
3. Correlates them by frameNumber to decode the binary format

Prerequisites:
- Chrome running with --remote-debugging-port=9222
- BRiSK Neo tab open and logged in
"""

import base64
import json
import struct
import time
from collections import defaultdict
from pathlib import Path

import httpx
import websockets.sync.client as ws_client

CDP_PORT = 9222
FRAMES_DIR = Path("docs/research/ws_frames")
CAPTURE_SECONDS = 30


class CDPClient:
    def __init__(self, ws_url):
        self.cdp = ws_client.connect(ws_url)
        self.msg_id = 0

    def send(self, method, params=None):
        self.msg_id += 1
        msg = {"id": self.msg_id, "method": method}
        if params:
            msg["params"] = params
        self.cdp.send(json.dumps(msg))
        return self.msg_id

    def recv_until(self, msg_id, timeout=15):
        self.cdp.socket.settimeout(timeout)
        while True:
            r = json.loads(self.cdp.recv())
            if "id" in r and r["id"] == msg_id:
                return r

    def evaluate(self, expr, await_promise=False):
        mid = self.send("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": await_promise,
        })
        r = self.recv_until(mid)
        result = r.get("result", {}).get("result", {})
        return result.get("value", result.get("description"))

    def recv_events(self, timeout=1.0):
        """Receive CDP events (non-blocking with timeout)."""
        events = []
        self.cdp.socket.settimeout(timeout)
        try:
            while True:
                raw = self.cdp.recv()
                msg = json.loads(raw)
                if "method" in msg:
                    events.append(msg)
        except TimeoutError:
            pass
        except Exception:
            pass
        return events

    def close(self):
        self.cdp.close()


def setup_wasm_access(client):
    """Expose WASM instance and memory via queryObjects."""
    client.send("Runtime.enable")
    client.recv_until(client.msg_id)

    # Find and store WASM instance
    mid = client.send("Runtime.evaluate", {
        "expression": "WebAssembly.Instance.prototype",
        "returnByValue": False,
    })
    r = client.recv_until(mid)
    proto_id = r.get("result", {}).get("result", {}).get("objectId")

    mid = client.send("Runtime.queryObjects", {"prototypeObjectId": proto_id})
    r = client.recv_until(mid)
    instances_id = r.get("result", {}).get("objects", {}).get("objectId")

    mid = client.send("Runtime.callFunctionOn", {
        "objectId": instances_id,
        "functionDeclaration": "function() { window.__wasm_instance = this[0]; return 'ok'; }",
        "returnByValue": True,
    })
    client.recv_until(mid)

    # Find and store WASM memory
    mid = client.send("Runtime.evaluate", {
        "expression": "WebAssembly.Memory.prototype",
        "returnByValue": False,
    })
    r = client.recv_until(mid)
    mem_proto_id = r.get("result", {}).get("result", {}).get("objectId")

    mid = client.send("Runtime.queryObjects", {"prototypeObjectId": mem_proto_id})
    r = client.recv_until(mid)
    mem_id = r.get("result", {}).get("objects", {}).get("objectId")

    mid = client.send("Runtime.callFunctionOn", {
        "objectId": mem_id,
        "functionDeclaration": "function() { window.__wasm_memory = this[0]; return 'ok'; }",
        "returnByValue": True,
    })
    client.recv_until(mid)

    print("WASM instance and memory exposed.")


def get_ptr_to_issue_map(client):
    """Get stock pointer -> issue_id mapping from WASM memory."""
    result = client.evaluate("""
        (() => {
            const view = new Int32Array(window.__wasm_memory.buffer);
            const TABLE_START = 63720216;
            const mapping = {};
            for (let i = 0; i < 4445; i++) {
                mapping[view[TABLE_START + i]] = i;
            }
            return mapping;
        })()
    """)
    return {int(k): v for k, v in result.items()} if isinstance(result, dict) else {}


def install_emplace_hook(client):
    """Hook qrm.emplace to capture decoded entries with frame correlation."""
    result = client.evaluate("""
        (() => {
            // Reset captures
            window.__brisk_decoded = [];
            window.__brisk_decode_active = true;

            // Check if already hooked
            if (window.__brisk_original_emplace) {
                // Re-hook with the original
                qrm.emplace = function(stock, type, timestamp, price10, quantity_raw, lotSize, frameNumber) {
                    if (window.__brisk_decode_active && window.__brisk_decoded.length < 100000) {
                        window.__brisk_decoded.push({
                            stock, type, timestamp, price10,
                            quantity: quantity_raw * lotSize,
                            lotSize, frameNumber,
                            captureTime: performance.now()
                        });
                    }
                    return window.__brisk_original_emplace.call(qrm, stock, type, timestamp, price10, quantity_raw, lotSize, frameNumber);
                };
                return 'Re-hooked qrm.emplace';
            }

            // First time hook
            window.__brisk_original_emplace = qrm.__proto__.emplace;
            qrm.emplace = function(stock, type, timestamp, price10, quantity_raw, lotSize, frameNumber) {
                if (window.__brisk_decode_active && window.__brisk_decoded.length < 100000) {
                    window.__brisk_decoded.push({
                        stock, type, timestamp, price10,
                        quantity: quantity_raw * lotSize,
                        lotSize, frameNumber,
                        captureTime: performance.now()
                    });
                }
                return window.__brisk_original_emplace.call(qrm, stock, type, timestamp, price10, quantity_raw, lotSize, frameNumber);
            };
            return 'Hooked qrm.emplace';
        })()
    """)
    return result


def capture_and_correlate(client, ptr_to_issue, seconds=CAPTURE_SECONDS):
    """Capture WS frames and decoded data simultaneously."""
    # Load issue_id -> code mapping
    code_map_path = FRAMES_DIR / "issue_id_to_code.json"
    issue_to_code = {}
    if code_map_path.exists():
        issue_to_code = json.loads(code_map_path.read_text())

    # Enable network capture
    mid = client.send("Network.enable")
    client.recv_until(mid)

    # Clear decoded captures
    client.evaluate("window.__brisk_decoded = []; window.__brisk_decode_active = true;")

    # Capture raw frames
    print(f"Capturing for {seconds}s...")
    raw_frames = []
    frame_seq = 0
    stop = time.time() + seconds

    while time.time() < stop:
        events = client.recv_events(timeout=0.5)
        for ev in events:
            if ev.get("method") == "Network.webSocketFrameReceived":
                payload = ev["params"].get("response", {}).get("payloadData", "")
                try:
                    data = base64.b64decode(payload)
                    raw_frames.append((frame_seq, data))
                    frame_seq += 1
                except Exception:
                    pass

    # Stop capture
    client.evaluate("window.__brisk_decode_active = false;")

    # Get decoded data
    decoded = client.evaluate("""
        (() => {
            const d = window.__brisk_decoded;
            return d.map(e => ({
                stock: e.stock,
                type: e.type,
                timestamp: e.timestamp,
                price10: e.price10,
                quantity: e.quantity,
                lotSize: e.lotSize,
                frameNumber: e.frameNumber
            }));
        })()
    """)

    print(f"Captured {len(raw_frames)} raw frames, {len(decoded) if decoded else 0} decoded entries")

    if not decoded or not raw_frames:
        print("No data captured! Is the market open?")
        return

    # Group decoded entries by frameNumber
    decoded_by_frame = defaultdict(list)
    for entry in decoded:
        fn = entry["frameNumber"]
        issue_id = ptr_to_issue.get(entry["stock"], -1)
        entry["issue_id"] = issue_id
        entry["code"] = issue_to_code.get(str(issue_id), "????")
        decoded_by_frame[fn].append(entry)

    # Get current frame number from WASM
    current_frame = client.evaluate(
        "window.__wasm_instance.exports._getFrameNumbers()"
    )
    print(f"Current WASM frame number: {current_frame}")

    # Correlate: find which raw frames correspond to which frameNumbers
    # The raw_frames list is in capture order. The frameNumber in decoded entries
    # tells us which WASM frame number the entry came from. Since WASM increments
    # frame number for each WS frame it processes, we can match them.

    # Find the frame number range
    frame_nums = sorted(decoded_by_frame.keys())
    if not frame_nums:
        print("No decoded entries with frame numbers!")
        return

    print(f"\nDecoded frame number range: {frame_nums[0]} - {frame_nums[-1]}")
    print(f"Total unique frame numbers: {len(frame_nums)}")
    print(f"Total decoded entries: {len(decoded)}")

    # Analyze the correlation
    print("\n=== CORRELATION ANALYSIS ===\n")

    # Show first 20 frames with both raw and decoded data
    # We need to figure out the offset between raw_frames index and frameNumber
    # The first raw frame might not be the first frame number

    # Attempt to find offset: if we assume raw_frames[0] corresponds to some frameNumber,
    # try to match by checking if the issue_id in the decoded data matches the marker in raw bytes
    print("Attempting to align raw frames with decoded frames...")

    best_offset = None
    best_matches = 0

    for offset in range(min(100, len(raw_frames))):
        matches = 0
        for i in range(min(50, len(raw_frames) - offset)):
            fn = frame_nums[0] + i if frame_nums[0] + i in decoded_by_frame else None
            if fn is None:
                continue
            raw_idx = i + offset
            if raw_idx >= len(raw_frames):
                break
            _, raw_data = raw_frames[raw_idx]
            if len(raw_data) < 2:
                continue
            # Check if the first issue_id in raw data matches decoded
            raw_issue_id = ((raw_data[0] | (raw_data[1] << 8)) >> 4)
            decoded_issues = {e["issue_id"] for e in decoded_by_frame[fn]}
            if raw_issue_id in decoded_issues:
                matches += 1
        if matches > best_matches:
            best_matches = matches
            best_offset = offset

    if best_offset is not None:
        print(f"Best offset: raw_frames[{best_offset}] = frameNumber {frame_nums[0]} ({best_matches} matches)")
    else:
        print("Could not determine offset. Showing first 20 decoded frames anyway.")
        best_offset = 0

    # Show correlated data
    print(f"\n{'='*80}")
    print(f"{'Frame':>6} {'IssueID':>8} {'Code':>6} {'Type':>5} {'Price10':>8} {'Qty':>8} {'RawHex'}")
    print(f"{'='*80}")

    shown = 0
    for i, fn in enumerate(frame_nums[:100]):
        raw_idx = best_offset + (fn - frame_nums[0])
        entries = decoded_by_frame[fn]

        raw_hex = ""
        if 0 <= raw_idx < len(raw_frames):
            _, raw_data = raw_frames[raw_idx]
            raw_hex = raw_data[:40].hex()

        for j, e in enumerate(entries):
            marker = ""
            if j == 0:
                marker = f"F{fn}"
            print(f"{marker:>6} {e['issue_id']:>8} {e['code']:>6} {e['type']:>5} "
                  f"{e['price10']:>8} {e['quantity']:>8} "
                  f"{raw_hex if j == 0 else ''}")
            shown += 1

        if shown >= 50:
            break

    # Save correlation data
    correlation = {
        "capture_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "raw_frame_count": len(raw_frames),
        "decoded_count": len(decoded),
        "frame_number_range": [frame_nums[0], frame_nums[-1]],
        "offset": best_offset,
        "samples": [],
    }

    for fn in frame_nums[:200]:
        raw_idx = best_offset + (fn - frame_nums[0])
        raw_hex = ""
        if 0 <= raw_idx < len(raw_frames):
            _, raw_data = raw_frames[raw_idx]
            raw_hex = raw_data.hex()

        correlation["samples"].append({
            "frameNumber": fn,
            "raw_hex": raw_hex,
            "decoded": [
                {
                    "issue_id": e["issue_id"],
                    "code": e["code"],
                    "type": e["type"],
                    "timestamp": e["timestamp"],
                    "price10": e["price10"],
                    "quantity": e["quantity"],
                    "lotSize": e["lotSize"],
                }
                for e in decoded_by_frame[fn]
            ],
        })

    out_path = FRAMES_DIR / "ws_decode_correlation.json"
    out_path.write_text(json.dumps(correlation, indent=2))
    print(f"\nSaved correlation data to {out_path}")

    # Analyze the binary encoding
    print("\n=== BINARY ENCODING ANALYSIS ===\n")
    analyze_encoding(correlation["samples"])


def analyze_encoding(samples):
    """Analyze the binary encoding from correlated samples."""
    for sample in samples[:20]:
        raw = bytes.fromhex(sample["raw_hex"]) if sample["raw_hex"] else b""
        decoded = sample["decoded"]
        fn = sample["frameNumber"]

        if not raw or not decoded:
            continue

        print(f"\n--- Frame {fn} ({len(raw)} bytes, {len(decoded)} entries) ---")
        print(f"  Raw: {raw.hex()}")

        for entry in decoded:
            iid = entry["issue_id"]
            marker = ((iid << 4) | 0x9).to_bytes(2, "little")
            marker_hex = marker.hex()

            # Find this marker in the raw data
            pos = raw.find(marker)
            if pos >= 0:
                # Show context around the marker
                context = raw[pos:pos + 20]
                print(f"  [{entry['code']}] iid={iid} marker@{pos} type={entry['type']} "
                      f"price10={entry['price10']} qty={entry['quantity']} "
                      f"lots={entry['lotSize']}")
                print(f"    bytes: {context.hex()}")

                # Try to find price10 encoded in the surrounding bytes
                p10 = entry["price10"]
                if p10 > 0:
                    p10_bytes_le16 = struct.pack("<H", p10 & 0xFFFF)
                    p10_bytes_le32 = struct.pack("<I", p10 & 0xFFFFFFFF)
                    for needle, desc in [(p10_bytes_le16, "u16LE"), (p10_bytes_le32, "u32LE")]:
                        idx = raw.find(needle, pos + 2)
                        if idx >= 0 and idx < pos + 20:
                            print(f"    ** price10={p10} found as {desc} at offset {idx} **")

                # Try to find quantity
                qty = entry["quantity"]
                if 0 < qty < 65536:
                    qty_le16 = struct.pack("<H", qty & 0xFFFF)
                    idx = raw.find(qty_le16, pos + 2)
                    if idx >= 0 and idx < pos + 20:
                        print(f"    ** qty={qty} found as u16LE at offset {idx} **")


def main():
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    targets = httpx.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()
    brisk_tab = next(
        (t for t in targets if "sbi.brisk.jp/#" in t.get("url", "")), None
    )
    if not brisk_tab:
        print("No BRiSK tab found! Open Chrome with --remote-debugging-port=9222")
        return

    print(f"Connecting to: {brisk_tab['title']}")
    client = CDPClient(brisk_tab["webSocketDebuggerUrl"])

    # Setup
    setup_wasm_access(client)
    ptr_to_issue = get_ptr_to_issue_map(client)
    print(f"Loaded {len(ptr_to_issue)} stock pointer mappings")

    # Install hook
    hook_result = install_emplace_hook(client)
    print(f"Hook: {hook_result}")

    # Check if data is flowing
    time.sleep(2)
    count = client.evaluate("window.__brisk_decoded?.length || 0")
    print(f"Decoded entries after 2s: {count}")

    if count == 0:
        print("\nNo data flowing. Market may be closed (09:00-15:00 JST).")
        print("The hook is installed. Run this script again during market hours.")
        client.close()
        return

    # Capture and correlate
    capture_and_correlate(client, ptr_to_issue)

    client.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
