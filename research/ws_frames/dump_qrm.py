#!/usr/bin/env python3
"""Connect to Chrome CDP, extract qrm market data, map to stock codes, save."""

import json
import httpx
import websockets.sync.client as ws_client

CDP_PORT = 9222
ISSUE_ID_TO_CODE_PATH = "/Users/soshimizutani/dev/pybrisk/docs/research/ws_frames/issue_id_to_code.json"
OUTPUT_PATH = "/Users/soshimizutani/dev/pybrisk/docs/research/ws_frames/decoded_trades.json"
WASM_PTR_TABLE_INDEX = 63720216
PTR_TABLE_SIZE = 4445
TOP_N = 30

# Step 0: Load issue_id -> code mapping
with open(ISSUE_ID_TO_CODE_PATH) as f:
    issue_id_to_code = json.load(f)

# Step 1: Find BRiSK tab
resp = httpx.get(f"http://localhost:{CDP_PORT}/json")
targets = resp.json()
brisk_target = None
for t in targets:
    if "sbi.brisk.jp/#" in t.get("url", ""):
        brisk_target = t
        break

if not brisk_target:
    for t in targets:
        if "brisk" in t.get("url", "").lower():
            brisk_target = t
            break

if not brisk_target:
    print("Available targets:")
    for t in targets:
        print(f"  {t.get('url', 'no-url')} - {t.get('title', 'no-title')}")
    raise RuntimeError("BRiSK tab not found")

ws_url = brisk_target["webSocketDebuggerUrl"]
print(f"Found BRiSK tab: {brisk_target.get('title', '')} -> {brisk_target.get('url', '')}")

# Step 2: Connect via CDP websocket
msg_id = 0


def cdp_eval(ws, expression, await_promise=False):
    global msg_id
    msg_id += 1
    params = {"expression": expression, "returnByValue": True}
    if await_promise:
        params["awaitPromise"] = True
    ws.send(json.dumps({"id": msg_id, "method": "Runtime.evaluate", "params": params}))
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == msg_id:
            if "error" in resp:
                raise RuntimeError(f"CDP error: {resp['error']}")
            result = resp.get("result", {}).get("result", {})
            if result.get("subtype") == "error":
                raise RuntimeError(f"JS error: {result.get('description', result)}")
            return result.get("value")


with ws_client.connect(ws_url, max_size=100 * 1024 * 1024) as ws:
    # Step 2a: Get pointer table from WASM memory
    print("Reading WASM pointer table...")
    ptr_js = (
        "(() => {"
        "  const mem = window.__wasm_memory;"
        "  if (!mem) return null;"
        "  const i32 = new Int32Array(mem.buffer);"
        f"  const start = {WASM_PTR_TABLE_INDEX};"
        f"  const size = {PTR_TABLE_SIZE};"
        "  const result = {};"
        "  for (let i = 0; i < size; i++) {"
        "    const issueId = i32[start + i];"
        "    if (issueId > 0) {"
        "      result[i] = issueId;"
        "    }"
        "  }"
        "  return result;"
        "})()"
    )
    ptr_table = cdp_eval(ws, ptr_js)
    if ptr_table is None:
        raise RuntimeError("WASM memory not available or pointer table empty")

    print(f"Pointer table: {len(ptr_table)} non-zero entries")

    # Build ptr -> issue_id mapping
    ptr_to_issue_id = {int(k): v for k, v in ptr_table.items()}

    # Step 2b: Get qrm.qrs keys and entry counts
    print("Reading qrm.qrs overview...")
    overview_js = (
        "(() => {"
        "  if (!window.qrm || !window.qrm.qrs) return null;"
        "  const result = {};"
        "  for (const [ptr, entries] of Object.entries(qrm.qrs)) {"
        "    result[ptr] = entries.length;"
        "  }"
        "  return result;"
        "})()"
    )
    overview = cdp_eval(ws, overview_js)
    if overview is None:
        raise RuntimeError("qrm.qrs not available")

    total_entries = sum(overview.values())
    stocks_with_data = len(overview)
    print(f"qrm.qrs: {stocks_with_data} stock pointers, {total_entries} total entries")

    # Step 2c: Find top N most active by entry count
    sorted_ptrs = sorted(overview.items(), key=lambda x: x[1], reverse=True)
    top_ptrs = sorted_ptrs[:TOP_N]

    print(f"\nTop {TOP_N} most active stocks:")
    for ptr_str, count in top_ptrs:
        ptr_int = int(ptr_str)
        issue_id = ptr_to_issue_id.get(ptr_int, "?")
        code = issue_id_to_code.get(str(issue_id), "?")
        print(f"  ptr={ptr_str} issue_id={issue_id} code={code} entries={count}")

    # Step 2d: Fetch all entries for top N stocks in batches
    print("\nFetching entries for top stocks...")
    stocks_data = {}

    BATCH_SIZE = 5
    top_ptr_keys = [p[0] for p in top_ptrs]

    for batch_start in range(0, len(top_ptr_keys), BATCH_SIZE):
        batch = top_ptr_keys[batch_start : batch_start + BATCH_SIZE]
        batch_js_list = ",".join(str(b) for b in batch)
        fetch_js = (
            "(() => {"
            "  const ptrs = [" + batch_js_list + "];"
            "  const result = {};"
            "  for (const ptr of ptrs) {"
            "    const entries = qrm.qrs[ptr];"
            "    if (entries) {"
            "      result[ptr] = entries.map(e => ({"
            "        type: e.type,"
            "        timestamp: e.timestamp,"
            "        price10: e.price10,"
            "        quantity: e.quantity,"
            "        frameNumber: e.frameNumber"
            "      }));"
            "    }"
            "  }"
            "  return result;"
            "})()"
        )
        batch_result = cdp_eval(ws, fetch_js)
        if batch_result:
            for ptr_str, entries in batch_result.items():
                ptr_int = int(ptr_str)
                issue_id = ptr_to_issue_id.get(ptr_int, None)
                code = (
                    issue_id_to_code.get(str(issue_id), None) if issue_id else None
                )

                if code:
                    stocks_data[code] = {
                        "issue_id": issue_id,
                        "code": code,
                        "entries": entries,
                    }
                else:
                    key = f"ptr_{ptr_str}"
                    stocks_data[key] = {
                        "issue_id": issue_id,
                        "code": None,
                        "ptr": ptr_int,
                        "entries": entries,
                    }
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(top_ptr_keys) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Fetched batch {batch_num}/{total_batches}")

# Step 3: Build output
output = {"capture_date": "2026-03-11", "stocks": stocks_data}

with open(OUTPUT_PATH, "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\nSaved to {OUTPUT_PATH}")

# Step 4: Summary stats
print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"Total entries across all stocks: {total_entries}")
print(f"Stocks with data in qrm.qrs:    {stocks_with_data}")
print(f"Stocks dumped (top {TOP_N}):        {len(stocks_data)}")
dumped_entries = sum(len(s["entries"]) for s in stocks_data.values())
print(f"Entries dumped:                  {dumped_entries}")
print(f"\nMost active stocks (by entry count):")
for i, (ptr_str, count) in enumerate(sorted_ptrs[:20], 1):
    ptr_int = int(ptr_str)
    issue_id = ptr_to_issue_id.get(ptr_int, "?")
    code = issue_id_to_code.get(str(issue_id), "?")
    print(f"  {i:2d}. {code:>6s} (issue_id={str(issue_id):>5s}) - {count:,} entries")
