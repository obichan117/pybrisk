"""Hook BRiSK's WASM decoder to intercept decoded order book updates.

The WASM module calls _qr_emplace(stock, type, timestamp_low, timestamp_high,
price10, quantity_low, quantity_high, lotSize, frameNumber) for each decoded entry.
We intercept this function to capture decoded data with known field meanings.
"""

import json
import time
from pathlib import Path

import httpx
import websockets.sync.client as ws_client

CDP_PORT = 9222
FRAMES_DIR = Path("docs/research/ws_frames")
CAPTURE_SECONDS = 10


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

    def close(self):
        self.cdp.close()


def main():
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    targets = httpx.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()
    brisk_tab = next(t for t in targets if "sbi.brisk.jp/#" in t.get("url", ""))
    print(f"Connecting to: {brisk_tab['title']}")

    client = CDPClient(brisk_tab["webSocketDebuggerUrl"])

    # Inject a hook that wraps _qr_emplace to capture decoded data
    print("Injecting WASM decoder hook...")
    result = client.evaluate("""
        (() => {
            // Storage for captured updates
            window.__brisk_captures = [];
            window.__brisk_capture_active = true;
            window.__brisk_capture_count = 0;

            // Find the WASM module - it's exposed as CC or through Module
            // The _qr_emplace function is called from WASM env imports
            // We need to find and wrap it

            // Check if qrm object exists (it's used in _qr_emplace)
            if (typeof qrm === 'undefined') {
                return 'qrm not found - trying alternative approach';
            }

            // Wrap qrm.emplace
            const originalEmplace = qrm.emplace.bind(qrm);
            qrm.emplace = function(stock, type, timestamp, price10, quantity, lotSize, frameNumber) {
                if (window.__brisk_capture_active && window.__brisk_captures.length < 5000) {
                    window.__brisk_captures.push({
                        stock: stock,
                        type: type,
                        timestamp: timestamp,
                        price10: price10,
                        quantity: quantity,
                        lotSize: lotSize,
                        frameNumber: frameNumber,
                        captureTime: Date.now()
                    });
                    window.__brisk_capture_count++;
                }
                return originalEmplace(stock, type, timestamp, price10, quantity, lotSize, frameNumber);
            };

            return 'qrm.emplace hooked successfully';
        })()
    """)
    print(f"Hook result: {result}")

    if "not found" in str(result):
        # Try alternative: hook at the import level
        print("Trying alternative hook via Module imports...")
        result = client.evaluate("""
            (() => {
                window.__brisk_captures = [];
                window.__brisk_capture_active = true;

                // The _qr_emplace is defined as a global function in the WASM JS wrapper
                // It calls qrm.emplace. Let's find _qr_emplace
                if (typeof _qr_emplace !== 'undefined') {
                    const orig = _qr_emplace;
                    window._qr_emplace_original = orig;
                    // Can't easily replace since WASM calls it via import table
                    return '_qr_emplace exists but cannot wrap (WASM import)';
                }

                // Try accessing through the main Angular app bundle
                // The app must call apiRecieved or similar to feed data to WASM
                // Let's hook _apiRecieved instead
                if (typeof _apiRecieved !== 'undefined') {
                    return '_apiRecieved exists';
                }

                // Look for the CC module
                if (typeof CC !== 'undefined') {
                    const exports = Object.keys(CC).filter(k => k.startsWith('_'));
                    return 'CC module found, exports: ' + exports.slice(0, 20).join(', ');
                }

                return 'No hook point found';
            })()
        """)
        print(f"Alt hook result: {result}")

    # Alternative approach: use getStockView to READ the current decoded state
    print("\nReading decoded stock data via getStockView...")
    result = client.evaluate("""
        (() => {
            // Try to call WASM functions to get current stock data
            // These are Module-level exports
            try {
                // getStockPointer returns a pointer to the stock data in WASM heap
                // getStockView returns a view of stock data
                // getItaRows returns order book rows

                // First, check what functions are available
                const funcs = ['_getStockPointer', '_getStockView', '_getItaRows',
                    '_fitItaViewRowPrice10', '_getTickIndexToPrice10', '_getRenewalTick10',
                    '_getStockMaster', '_apiRecieved', '_getFrameNumbers'];

                const available = {};
                for (const f of funcs) {
                    available[f] = typeof Module?.[f] === 'function' ? 'yes' : 'no';
                }
                return available;
            } catch (e) {
                return 'Error: ' + e.message;
            }
        })()
    """)
    print(f"Available WASM functions: {json.dumps(result, indent=2)}")

    # Try to read stock data using WASM functions
    # issue_id for 7014 (the stock shown in zenita tab)
    print("\nTrying to read stock 7014 data from WASM memory...")
    result = client.evaluate("""
        (() => {
            try {
                // We need to find the issue_id for stock 7014
                // Let's try calling getStockPointer with various issue_ids
                // and then reading from WASM heap

                // First, get the module's HEAP views
                const HEAP32 = Module.HEAP32;
                const HEAPU32 = Module.HEAPU32;
                const HEAPU8 = Module.HEAPU8;

                if (!HEAP32) return 'No HEAP32';

                // Try getStockPointer for a few issue_ids
                const results = {};
                for (const iid of [0, 1, 78, 714, 937, 1116, 1202, 1589, 3384]) {
                    try {
                        const ptr = Module._getStockPointer(iid);
                        if (ptr && ptr > 0) {
                            // Read some data from the pointer
                            // The stock structure likely has price10 and other fields
                            const data = [];
                            for (let i = 0; i < 20; i++) {
                                data.push(HEAP32[(ptr >> 2) + i]);
                            }
                            results[iid] = {ptr: ptr, data: data};
                        }
                    } catch (e) {
                        results[iid] = 'error: ' + e.message;
                    }
                }
                return results;
            } catch (e) {
                return 'Error: ' + e.message;
            }
        })()
    """)
    print(f"Stock pointers: {json.dumps(result, indent=2)}")

    # Try getTickIndexToPrice10 to understand the tick-price mapping
    print("\nTrying tick-to-price10 mapping...")
    result = client.evaluate("""
        (() => {
            try {
                // For stock at issue_id 3384 (code 4258), base_price10 = 31050
                const iid = 3384;
                const results = {};
                for (let tick = 0; tick < 20; tick++) {
                    try {
                        const price10 = Module._getTickIndexToPrice10(iid, tick);
                        results[tick] = price10;
                    } catch(e) {
                        results[tick] = 'err: ' + e.message;
                        break;
                    }
                }
                return results;
            } catch(e) {
                return 'Error: ' + e.message;
            }
        })()
    """)
    print(f"Tick→Price10 for stock 4258: {json.dumps(result, indent=2)}")

    # Try getRenewalTick10
    print("\nTrying getRenewalTick10...")
    result = client.evaluate("""
        (() => {
            try {
                const results = {};
                for (const iid of [0, 78, 714, 1116, 1589, 3384]) {
                    results[iid] = Module._getRenewalTick10(iid);
                }
                return results;
            } catch(e) {
                return 'Error: ' + e.message;
            }
        })()
    """)
    print(f"RenewalTick10: {json.dumps(result, indent=2)}")

    # Try getItaRows to get order book
    print("\nTrying getItaRows...")
    result = client.evaluate("""
        (() => {
            try {
                const iid = 3384;  // stock 4258
                const ptr = Module._getItaRows(iid);
                if (!ptr || ptr <= 0) return 'no data';

                // Read order book rows from WASM heap
                const HEAP32 = Module.HEAP32;
                const rows = [];
                for (let i = 0; i < 40; i++) {  // read 40 int32 values
                    rows.push(HEAP32[(ptr >> 2) + i]);
                }
                return {ptr: ptr, first40_i32: rows};
            } catch(e) {
                return 'Error: ' + e.message;
            }
        })()
    """)
    print(f"ItaRows for 4258: {json.dumps(result, indent=2)}")

    client.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
