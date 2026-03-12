"""Extract tick tables - final v3. Simplified, all parsing in JS, correct field order."""

import json
import httpx
from websockets.sync.client import connect

CDP_PORT = 9222


class CDPClient:
    def __init__(self, ws_url):
        self.cdp = connect(ws_url)
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

    def evaluate(self, expr):
        mid = self.send("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": False,
        })
        r = self.recv_until(mid)
        result = r.get("result", {}).get("result", {})
        return result.get("value", result.get("description"))

    def close(self):
        self.cdp.close()


def find_brisk_tab():
    resp = httpx.get(f"http://localhost:{CDP_PORT}/json")
    tabs = resp.json()
    for tab in tabs:
        if "sbi.brisk.jp/#" in tab.get("url", ""):
            return tab["webSocketDebuggerUrl"]
    raise RuntimeError("BRiSK tab not found")


def setup_wasm_access(client):
    client.send("Runtime.enable")
    client.recv_until(client.msg_id)
    for proto_expr, store_fn in [
        ("WebAssembly.Instance.prototype",
         "function() { window.__wasm_instance = this[0]; return 'ok'; }"),
        ("WebAssembly.Memory.prototype",
         "function() { window.__wasm_memory = this[0]; return 'ok'; }"),
    ]:
        mid = client.send("Runtime.evaluate", {
            "expression": proto_expr, "returnByValue": False,
        })
        r = client.recv_until(mid)
        proto_id = r["result"]["result"]["objectId"]
        mid = client.send("Runtime.queryObjects", {"prototypeObjectId": proto_id})
        r = client.recv_until(mid)
        obj_id = r["result"]["objects"]["objectId"]
        mid = client.send("Runtime.callFunctionOn", {
            "objectId": obj_id,
            "functionDeclaration": store_fn,
            "returnByValue": True,
        })
        client.recv_until(mid)


def main():
    ws_url = find_brisk_tab()
    client = CDPClient(ws_url)
    setup_wasm_access(client)

    # Step 1: Get raw int32 dump of the tick table region
    raw_dump = client.evaluate("""
        (() => {
            var view = new Int32Array(window.__wasm_memory.buffer);
            var data = {};
            for (var j = 4855; j < 4995; j++) {
                data[j] = view[j];
            }
            return data;
        })()
    """)

    # Step 2: Parse tables from raw dump
    # Tables are in the region 4863..4989
    # Format: [tick_size_price10, upper_bound_price10] pairs, -1 terminated
    tables = []
    current_entries = []
    table_start = 4863
    # Parse tables: scan int32 values one at a time.
    # -1 is a single-value terminator, entries are pairs [tick_size_price10, upper_bound_price10].
    # We accumulate values and group into pairs between terminators.
    #
    # Table 0: pure [tick, bound] pairs
    # Tables 1-3: first pair is a header, remaining are [tick, bound] pairs
    j = 4863
    pair_buffer = []
    while j < 4990:
        v = raw_dump.get(str(j))
        if v is None:
            break
        if v == -1:
            # Flush pair_buffer into entries
            # Format: [tick_size_price10, upper_bound_price10] pairs
            for k in range(0, len(pair_buffer) - 1, 2):
                # Memory format: [upper_bound_price10, tick_size_price10]
                current_entries.append({
                    "upper_bound_price10": pair_buffer[k],
                    "tick_size_price10": pair_buffer[k + 1],
                    "upper_bound_yen": pair_buffer[k] / 10.0,
                    "tick_size_yen": pair_buffer[k + 1] / 10.0,
                })
            if current_entries:
                tables.append({
                    "start_int32": table_start,
                    "end_int32": j,
                    "entries": current_entries,
                })
            current_entries = []
            pair_buffer = []
            table_start = j + 1
            j += 1
            continue
        pair_buffer.append(v)
        j += 1

    # Print parsed tables
    print(f"\nTotal tables parsed: {len(tables)}")
    for i, table in enumerate(tables):
        entries = table["entries"]
        print(f"\nTable {i} ({len(entries)} entries, int32[{table['start_int32']}..{table['end_int32']}]):")
        for e in entries:
            print(f"  price < {e['upper_bound_yen']:>14,.1f} yen  ->  tick = {e['tick_size_yen']:>10,.1f} yen")

    # Step 3: Identify tables
    # Table 0 (10 entries): Standard TSE tick table
    # Verify: tick 1.0 at bound 3000, tick 5.0 at bound 5000, etc.
    # Table 1: Another table starting after first -1
    # Table 2: After second -1
    # Table 3 (32 entries): TOPIX100 renewal tick table

    # Name tables based on content analysis
    # Known TSE tick table types:
    # - Standard: 10 entries, starts at bound 3000 yen
    # - Fine (TOPIX100 pre-renewal): 11 entries, starts at bound 100000 yen with tick 1000
    # - Standard subset: 9 entries, starts at bound 10000 yen
    # - TOPIX100 renewal: 32 entries, detailed fine-grained ticks
    table_ids = {}
    table_descriptions = {}
    for i, table in enumerate(tables):
        entries = table["entries"]
        n = len(entries)
        if not entries:
            table_ids[i] = f"empty_{i}"
            table_descriptions[i] = "Empty table"
            continue
        first_bound = entries[0]["upper_bound_yen"]
        first_tick = entries[0]["tick_size_yen"]

        # Memory format: pair[0]=upper_bound_price10, pair[1]=tick_size_price10
        # Table 0: first_bound=3000.0, first_tick=1.0
        # Table 1: first_bound=100000.0, first_tick=1000.0 (header)
        # Table 2: first_bound=10000.0, first_tick=10000.0 (header)
        # Table 3: first_bound=10000.0, first_tick=200.0 (header)
        if n == 10 and first_bound == 3000.0 and first_tick == 1.0:
            table_ids[i] = "standard_tse"
            table_descriptions[i] = "Standard TSE tick table (most stocks). 10 price bands."
        elif first_bound == 100000.0 and first_tick == 1000.0:
            table_ids[i] = "topix100_fine"
            table_descriptions[i] = "TOPIX100 fine tick table. First entry is header/preamble, entries 2-10 are the actual tick bands with finer 0.1-yen tick resolution."
        elif n <= 10 and first_bound == 10000.0 and first_tick == 10000.0:
            table_ids[i] = "standard_upper"
            table_descriptions[i] = "Upper-range standard tick table. First entry is header/preamble, remaining entries cover 30000+ yen range."
        elif n >= 20:
            table_ids[i] = "topix100_renewal"
            table_descriptions[i] = "TOPIX100 renewal tick table (fine-grained, 32 price bands). First entry is header/preamble."
        else:
            table_ids[i] = f"table_{i}"
            table_descriptions[i] = f"Unknown table ({n} entries)"

    # Step 4: Get stock metadata
    stock_meta = client.evaluate("""
        (() => {
            var w = window.__wasm_instance.exports;
            var view = new Int32Array(window.__wasm_memory.buffer);
            var TABLE_START = 63720216;
            var ids = [0, 13, 78, 937, 1202, 1589];
            var codes = ["1301", "1605", "1982", "6740", "7974", "9984"];
            var stocks = {};
            for (var i = 0; i < ids.length; i++) {
                var ptr = view[TABLE_START + ids[i]];
                stocks[codes[i]] = {
                    issue_id: ids[i],
                    stock_ptr: ptr,
                    struct_size_bytes: view[ptr/4],
                    offset_149_value: view[ptr/4 + 149]
                };
            }
            var renewalTick10 = null;
            try { renewalTick10 = w._getRenewalTick10(0); } catch(e) {}
            return {
                stock_count: w._stockCount(),
                renewal_tick10_issue0: renewalTick10,
                ptr_table_base_int32: TABLE_START,
                stocks: stocks
            };
        })()
    """)

    print(f"\nStock count: {stock_meta.get('stock_count')}")
    print(f"RenewalTick10 (issue 0): {stock_meta.get('renewal_tick10_issue0')}")
    for code, info in stock_meta.get("stocks", {}).items():
        print(f"  {code}: {info}")

    client.close()

    # Build final output
    output = {
        "description": "Tick tables extracted from BRiSK WASM module (fita3-cpp/fita.cc)",
        "extraction_method": "Direct WASM data section memory read via Chrome CDP",
        "notes": {
            "price10": "price10 = price_yen * 10 (0.1 yen precision)",
            "format": "In WASM memory: [upper_bound_price10, tick_size_price10] int32 pairs, -1 terminated. Tables 1-3 have a header/preamble as their first pair entry where the pair order may be reversed.",
            "wasm_region": "int32 offsets 4863-4989 (byte offsets 19452-19956)",
            "wasm_exports_tested": [
                "_getTickIndexToPrice10(issue_id, tick_index) - aborts at tick >= 2 when stock data not loaded",
                "_getTickPrice10ToIndex(issue_id, price10) - aborts for most price values",
                "_getRenewalTick10(issue_id) - returns 50 for issue_id=0 only",
                "_getStockPointer(issue_id) - returns valid ptr only for loaded stocks",
                "_getStockView(issue_id) - requires loaded stock data",
                "_getStockMaster(issue_id) - requires loaded stock data",
                "_stockCount() - returns 4445",
            ],
        },
        "tables": {},
        "stock_metadata": stock_meta,
    }

    for i, table in enumerate(tables):
        name = table_ids.get(i, f"table_{i}")
        desc = table_descriptions.get(i, "")
        output["tables"][name] = {
            "description": desc,
            "wasm_int32_range": [table["start_int32"], table["end_int32"]],
            "num_entries": len(table["entries"]),
            "entries": table["entries"],
        }

    out_path = "/Users/soshimizutani/dev/pybrisk/docs/research/ws_frames/tick_tables.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
