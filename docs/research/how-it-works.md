# How pybrisk Works

A layered explanation from "what does it do" to "how does the binary protocol work", in increasing order of complexity.

---

## Level 1: What is this?

**pybrisk** is a Python library that pulls market data from [SBI BRiSK](https://sbi.brisk.jp), a real-time full order book viewer for the Tokyo Stock Exchange.

BRiSK is a browser app — you log in through SBI Securities, and it shows you live prices, order books, charts, and alerts for all ~4,400 TSE-listed stocks. pybrisk lets you access that same data from Python.

```python
import pybrisk

pybrisk.login("username", "password")

# Historical candles
df = pybrisk.Ticker("7203").ohlc("1d")

# Market-wide alerts
alerts = pybrisk.Market().alerts()
```

---

## Level 2: Where does the data come from?

BRiSK has **four data channels**. pybrisk uses different ones depending on the data type:

```
                        BRiSK Platform
                             │
            ┌────────────────┼────────────────┐
            │                │                │
       ① REST API       ② WebSocket      ③ Browser
       (JSON over        (proprietary      (the web app
        HTTPS)            binary stream)    running in
                                            Chrome)
```

| Channel | What it gives you | How pybrisk uses it |
|---|---|---|
| **① REST API** | OHLC, margin data, alerts, stock info, watchlist | Direct HTTP calls via `httpx`. Working today. |
| **② WebSocket** | Real-time trades, quotes, order book depth | Connects to `wss://sbi.brisk.jp/realtime/...`. In progress — binary decoder ~90% done. |
| **③ Browser** | Anything the web app can do (watchlist editing, etc.) | Two sub-approaches: **CDP** and **Playwright**. See below. |

### What's the difference between CDP and Playwright?

Both involve Chrome, but they work at completely different levels:

| | CDP | Playwright |
|---|---|---|
| **Full name** | Chrome DevTools Protocol | Playwright browser automation |
| **What it does** | Hooks into JavaScript functions running inside the page | Clicks buttons, fills forms, reads the DOM |
| **Analogy** | Attaching a debugger to a running program | A robot using the UI like a human would |
| **Used for** | Reading decoded market data from BRiSK's own WASM decoder | Writing to watchlists (no API exists) |
| **Touches the DOM?** | No — intercepts JS function calls | Yes — interacts with HTML elements |
| **Latency** | ~500ms (polling interval) | ~1-2s (page interaction) |

**CDP is not scraping.** It connects to Chrome's debugging interface and runs JavaScript inside the page. We use it to intercept the output of BRiSK's own binary decoder — so we get the same decoded data the browser displays, guaranteed correct.

---

## Level 3: How does authentication work?

BRiSK doesn't have its own login. It piggybacks on SBI Securities:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  SBI Securities │────→│   sbi.brisk.jp  │────→│    pybrisk      │
│  login (browser)│     │   sets cookies  │     │  extracts       │
│                 │     │                 │     │  cookies +      │
│  username/pass  │     │  Cookie: ...    │     │  API token      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**Step by step:**

1. Playwright opens a browser, logs into SBI Securities
2. Navigates to BRiSK — the redirect sets session cookies on `sbi.brisk.jp`
3. pybrisk extracts those cookies and closes the browser
4. `GET /api/frontend/boot` (cookie auth) → returns a PASETO `api_token`
5. All subsequent API calls use `Authorization: Bearer {api_token}`

After step 3, no browser is needed for REST API calls.

---

## Level 4: How does the REST API work?

Standard JSON-over-HTTPS. The interesting part is the boot sequence:

```
frontend/boot  ──→  api_token, csrf_token
                         │
app/boot  ──→  ws_url, master_hash, snapshot_hash
                    │          │            │
                    │    master/{hash}   snapshot/{hash}
                    │    (stock defs)    (full state, 29 MB)
                    │
              WebSocket connection
```

**Content-addressable storage**: Master and snapshot URLs contain a SHA-256 hash. The server tells you the current hash via `app/boot`, and the data is cached with `max-age=86400`.

**Price encoding**: All prices are `price10` = price × 10 (integer). This avoids floating-point issues. A stock at ¥3,418.5 is stored as `34185`.

---

## Level 5: How does the WebSocket stream work?

This is where it gets interesting. BRiSK streams real-time data over a WebSocket as **proprietary binary frames**. The browser decodes them using a **compiled C/C++ WASM module** (`fita.wasm`, ~153 KB).

### Why binary?

Efficiency. During active trading, BRiSK sends ~338 frames/second at ~15 KB/sec. If this were JSON, it would be 20× larger. The binary format uses:

- **Delta encoding**: Only changes are sent, not full state
- **Variable-width integers**: Small values use fewer bytes
- **Tick indices instead of prices**: Prices are stored as integer positions in a tick table, not as yen values

### The normal flow (in the browser)

```
Server ──binary──→ WebSocket ──→ WASM decoder ──→ JavaScript ──→ UI
                                  (fita.wasm)      (qrm.emplace)
```

The WASM module calls a JavaScript function `qrm.emplace()` for each decoded event:

```javascript
qrm.emplace(stock_ptr, type, timestamp_ns, price10, quantity, lotSize, frameNumber)
```

This is the single point where binary becomes structured data. Everything the browser displays comes from here.

### How pybrisk gets this data (two approaches)

**Approach A — CDP hook (working now, ~500ms latency):**

```
Server ──binary──→ Chrome/WASM ──→ qrm.emplace() ──→ our JS hook ──→ Python
                                         ↑
                               we intercept here via CDP
```

We connect to Chrome's debugging port, inject a hook into `qrm.emplace`, and poll the buffered results. BRiSK's own decoder does all the hard work.

**Approach B — Native Python decoder (in progress, ~0ms latency):**

```
Server ──binary──→ Python WebSocket ──→ binary_decoder.py ──→ structured data
                                              ↑
                              our reimplementation of fita.wasm
```

We reverse-engineered the WASM binary format and reimplemented the decoder in Python. No browser needed. But the format is complex and not fully validated yet.

---

## Level 6: How does the binary frame format work?

Each WebSocket message can contain data for **multiple stocks**. The structure is:

```
┌─────────────────────────────────────────────────────────┐
│                    WebSocket Frame                       │
│                                                         │
│  ┌─── Stock Chunk (issue_id=937, JDI) ───────────────┐ │
│  │ Header: 4 bytes LE uint32 + timestamp bytes        │ │
│  │   bits 0-3:   0x9 (stock data marker)              │ │
│  │   bits 4-16:  issue_id (937)                       │ │
│  │   bits 17-18: extra timestamp bytes (0-3)          │ │
│  │   bits 19-31: timestamp delta (13 bits)            │ │
│  │                                                     │ │
│  │ Sub-entry 1: [tag byte] [skip] [price+qty field]   │ │
│  │ Sub-entry 2: [tag byte] [skip] [depth field]       │ │
│  │ Sub-entry 3: [tag byte=last] [skip] [both fields]  │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─── Stock Chunk (issue_id=1589, SoftBank) ─────────┐ │
│  │ Header ...                                         │ │
│  │ Sub-entry 1 (last) ...                             │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Sub-entry tag byte

Each sub-entry starts with a tag that says what data follows:

```
bit 0:    is_last    (1 = last entry for this stock)
bit 1:    has_depth  (order book depth update)
bit 2:    has_price  (price + quantity = trade/quote)
bit 3:    has_D      (additional field)
bit 4:    has_E      (additional field)
bits 5-7: skip       (0-7 extra bytes before fields)
```

### Price + quantity fields

The most important field. Self-describing size via a 2-byte tag:

```
byte 0: tag
  └── bits 0-2: price_bytes (P), bits 3-5: qty_bytes (Q)
byte 1: metadata
bytes 2..2+P:       signed tick index (little-endian)
bytes 2+P..2+P+Q:   unsigned quantity (little-endian)
```

The **tick index** is not a price — it's a position in a tick table. To get the actual price:

```
tick_index 5923  ──→  tick table lookup  ──→  price10 = 29730  ──→  ¥2,973.0
```

### Why tick indices instead of prices?

TSE tick sizes vary by price level. A stock at ¥2,973 has a ¥10 tick; a stock at ¥500 has a ¥1 tick. By using a tick index (uniform integer spacing), the binary format can:

1. Use fewer bytes (tick indices are smaller than price10 values)
2. Represent price levels uniformly regardless of the tick regime
3. Support signed deltas that mean "N ticks away" consistently

---

## Level 7: How was the binary format reverse-engineered?

BRiSK's WASM module (`fita.wasm`) is the only documentation of the binary format. We took it apart:

### Step 1: Decompile the WASM

```bash
wasm-decompile fita.wasm -o fita_decompiled.c    # 68,000 lines of pseudocode
wasm2wat fita.wasm -o fita.wat                     # 200,000 lines of WebAssembly text
```

### Step 2: Trace the call chain

Starting from the export `_pushWs`, followed function calls:

```
_pushWs → f_xg/205 → f_yg/206 → f_zg/207 → f_fh/213 → f_jh/217
  (export)  (per-stock)  (iterator)  (dispatch)  (process)  (tick→price)
```

### Step 3: Discover the buffer swap

This was the hardest part. The iterator `f_yg` stores field pointers with a **cross-wire**:

```
f_yg stores bit 1 data at buf+8, bit 2 data at buf+4
f_fh reads  buf+4 as "depth",    buf+8 as "price+qty"
```

So what the sub-entry tag calls "bit 1" (depth) ends up being processed as price data, and vice versa. This was confirmed by reading the WAT bytecode directly.

### Step 4: Find the price reading offset

The WASM function `f_fh` reads the tick index at **offset 1** from the field start. But the correct offset is **2** (because the tag is 2 bytes, not 1). Empirical validation:

| | Offset 1 (f_fh does this) | Offset 2 (correct) |
|---|---|---|
| Valid tick range | 84% | **99.3%** |
| Known price match | 0% | **~80%** |

This means f_fh has a bug (or reads a different format than we think). The ring buffer `f_eh` is likely the actual primary processing path.

### Step 5: Capture + correlate during live trading

`scripts/correlate_ws_decode.py` simultaneously captures:
- Raw binary WebSocket frames (via CDP Network events)
- Decoded output from `qrm.emplace` (via CDP JS hook)

Matching by `frameNumber` lets us map raw bytes to decoded fields — ground truth for validating our Python decoder.

---

## Glossary

| Term | Meaning |
|---|---|
| **issue_id** | Internal stock identifier (0-4444), derived from position in master data |
| **stock_ptr** | WASM heap pointer to an 18,000-byte stock struct |
| **price10** | Price × 10 as integer (¥3,418.5 = 34185) |
| **tick_index** | Integer position in the tick table; converts to price10 via lookup |
| **lotSize** | Trading unit, typically 100 shares |
| **qrm** | JavaScript object that stores decoded market data (`qrm.qrs[stock_ptr]`) |
| **CDP** | Chrome DevTools Protocol — debug interface to control/inspect Chrome |
| **WASM** | WebAssembly — compiled C/C++ running in the browser at near-native speed |
| **PASETO** | Token format (like JWT but encrypted); used for all BRiSK auth tokens |
| **f_yg, f_fh, ...** | Internal WASM function names from decompilation |
