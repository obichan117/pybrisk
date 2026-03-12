# pybrisk Architecture & Data Pipeline

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    SBI BRiSK Platform                       │
│                                                             │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ REST API │  │  WebSocket   │  │   Browser Frontend    │ │
│  │ (JSON)   │  │  (Binary)    │  │   (Angular + WASM)    │ │
│  └─────┬────┘  └──────┬───────┘  └──────────┬────────────┘ │
└────────┼───────────────┼────────────────────┼───────────────┘
         │               │                    │
    ┌────▼────┐    ┌─────▼──────┐    ┌───────▼─────────┐
    │  httpx  │    │  Native    │    │   CDP / Playwright│
    │ session │    │  decoder   │    │   (fallback)     │
    └────┬────┘    └─────┬──────┘    └───────┬─────────┘
         │               │                    │
    ┌────▼───────────────▼────────────────────▼──────┐
    │                  pybrisk                        │
    │                                                 │
    │  Ticker ─── OHLC, JSFC, tick data              │
    │  Market ─── alerts, stock lists, info           │
    │  Stream ─── real-time order book + trades       │
    └─────────────────────────────────────────────────┘
```

## Data Channels

### Channel 1: REST API (implemented)

Direct HTTP requests to `https://sbi.brisk.jp/api/` and `https://api.brisk.jp/`.

| Endpoint | Data | Latency | Status |
|---|---|---|---|
| `/api/ohlc/{code}` | OHLC candles (5m/1d/1w/1m) | ~200ms | Working |
| `/api/jsfc/{code}` | Margin lending (JSFC) | ~200ms | Working |
| `/api/stocks_info` | Turnover, outstanding shares | ~300ms | Working |
| `/api/stock_lists` | IPO, NK225 constituent lists | ~200ms | Working |
| `/api/markets` | Market condition alerts | ~200ms | Working |
| `/api/frontend/watchlist` | User watchlist (read-only) | ~100ms | Working |
| `/api/master/{hash}` | Stock definitions (4445 stocks) | ~500ms | Parsed |
| `/api/snapshot/{hash}` | Full market state (29 MB) | ~2s | Format known |

### Channel 2: WebSocket Native Decoder (in progress)

Direct WebSocket connection with Python-side binary decoding.

```
Browser ← wss://sbi.brisk.jp/realtime/0?session={token} → pybrisk
                                                            │
                                                     binary_decoder.py
                                                            │
                                              ┌─────────────┼─────────────┐
                                              ▼             ▼             ▼
                                          trades       order book      depth
                                       (price+qty)    (tick index)    (levels)
```

**Status**: Binary format ~90% decoded. Needs live validation during market hours.

**Throughput**: ~338 frames/sec, ~14.8 KB/sec (observed during lunchtime session).

### Channel 3: CDP Fallback (ready to test)

Hook BRiSK's own WASM decoder via Chrome DevTools Protocol.

```
Chrome (BRiSK tab)
  │
  ├── qrm.emplace hook ──→ decoded trades/quotes (JSON)
  │                         {type, timestamp, price10, quantity, frame}
  │
  └── WASM memory read ──→ order book state, stock struct fields
```

**Script**: `scripts/cdp_live_reader.py` — streams decoded data as JSON-lines.

**Pros**: Uses BRiSK's battle-tested decoder, guaranteed correct output.
**Cons**: Requires Chrome running with BRiSK logged in, ~500ms polling latency.

### Channel 4: Playwright Browser Automation (planned)

For features with no backend API (write operations).

| Feature | Method | Status |
|---|---|---|
| Watchlist management (add/remove) | DOM automation | Planned |
| Custom alerts | DOM automation | Planned |
| Screenshot/export | Page capture | Planned |

## Binary Protocol Summary

### Frame Structure

```
WebSocket Frame
├── Stock Chunk 1
│   ├── Header (5-8 bytes)
│   │   ├── bits 0-3:   type (0x9 = stock data)
│   │   ├── bits 4-16:  issue_id (13 bits)
│   │   ├── bits 17-18: ts_extra_bytes (0-3)
│   │   └── bits 19-31: ts_delta_low (13 bits)
│   │   └── [ts_extra bytes]
│   │
│   └── Sub-entries
│       ├── Entry 1: [tag] [skip bytes] [field B?] [field C?] [field D?] [field E?]
│       ├── Entry 2: ...
│       └── Entry N: (tag bit 0 = 1 → last entry for this stock)
│
├── Stock Chunk 2
│   ├── Header ...
│   └── Sub-entries ...
│
└── Stock Chunk N ...
```

### Sub-Entry Tag Byte

```
bit 0:    is_last (1 = last entry for this stock)
bit 1:    has_field_B (depth update)
bit 2:    has_field_C (price + quantity)
bit 3:    has_field_D
bit 4:    has_field_E
bits 5-7: skip_bytes (0-7, for marker/continuation data)
```

### Field B/C Format (2-byte tag)

```
byte 0: tag
  ├── bits 0-2: price_bytes (pb, 0-7)
  └── bits 3-5: qty_bytes (qb, 0-7)
byte 1: metadata (used by depth processing)
bytes 2..2+pb:      signed tick index (LE, two's complement)
bytes 2+pb..2+pb+qb: unsigned quantity (LE)
total size = pb + 2 + qb
```

### WASM Processing Pipeline

```
Raw WS frame
  │
  ▼
f_xg/205 (per-stock processor)
  │
  ▼
f_yg/206 (iterator) ──→ parse header, loop sub-entries
  │                      SWAP: bit1→buf+8, bit2→buf+4
  ▼
f_zg/207 (dispatcher)
  ├──→ f_eh/212 (ring buffer) ── stores ALL entries ──→ [consumer TBD]
  └──→ f_fh/213 (field processor)
       ├── buf+4 (was bit1) → depth: f_lh/219 (order book update)
       └── buf+8 (was bit2) → price: f_jh/217 (tick→price10) → qrm.emplace
```

**Key insight**: Single-bit entries are no-ops in f_fh. The ring buffer f_eh handles
ALL entries and feeds an unidentified consumer — this is likely the primary path for
most market data.

## Feature Matrix

| Feature | REST API | WebSocket | CDP | Playwright |
|---|---|---|---|---|
| OHLC candles | Yes | — | — | — |
| Margin lending (JSFC) | Yes | — | — | — |
| Stock info (turnover) | Yes | — | — | — |
| Market alerts | Yes | — | — | — |
| Watchlist (read) | Yes | — | — | — |
| Watchlist (write) | — | — | — | Planned |
| Real-time trades | — | In progress | Ready | — |
| Order book depth | — | In progress | Partial | — |
| Full tick data | — | In progress | Ready | — |
| Chart rendering | — | — | — | Lightweight Charts |

## Authentication Flow

```
SBI Securities login (browser)
  │
  ▼
Cookie: JSESSIONID, ... ──→ sbi.brisk.jp
  │
  ▼
GET /api/frontend/boot
  └── api_token, csrf_token, tfx_token
       │
       ▼
  GET /api/app/boot
    └── ws_url (session token), master_hash, snapshot_hash
         │
         ├── GET /api/master/{hash}     → stock definitions
         ├── GET /api/snapshot/{hash}   → market state
         └── WSS /realtime/0?session=.. → live stream
```

**pybrisk authentication**: Uses Playwright to automate SBI Securities login, then extracts session cookies for httpx requests.

## Tick Price Conversion

Prices are stored as **tick indices** in the binary stream. Conversion uses per-stock tick tables:

```
tick_index  ──→  tick_table lookup  ──→  price10 (price × 10)
                 (cumulative sum)
```

Example (Standard TSE table):

| Price Range | Tick Size | Tick Indices |
|---|---|---|
| 0 - 3,000 yen | 1 yen | 0 - 3,000 |
| 3,000 - 5,000 | 5 yen | 3,000 - 3,400 |
| 5,000 - 30,000 | 10 yen | 3,400 - 5,900 |
| 30,000 - 50,000 | 50 yen | 5,900 - 6,300 |
| 50,000 - 300,000 | 100 yen | 6,300 - 8,800 |
| 300,000 - 500,000 | 500 yen | 8,800 - 9,200 |
| 500,000 - 3,000,000 | 1,000 yen | 9,200 - 11,700 |
| 3,000,000 - 5,000,000 | 5,000 yen | 11,700 - 12,100 |
| 5,000,000 - 30,000,000 | 10,000 yen | 12,100 - 14,600 |
| 30,000,000+ | 50,000 yen | 14,600+ |

## Scripts Reference

| Script | Purpose | When to run |
|---|---|---|
| `cdp_live_reader.py` | Stream live data via CDP hook | Market hours |
| `correlate_ws_decode.py` | Capture raw + decoded for correlation | Market hours |
| `binary_decoder.py` | Python binary frame decoder | Anytime (offline analysis) |
| `hook_wasm_decoder.py` | Hook WASM functions via CDP | Market hours |
| `validate_tick_deltas.py` | Validate tick accumulation for known stocks | Offline |
| `validate_offset2.py` | Validate offset 2 tick indices | Offline |
| `field_format_summary.py` | Compare offset 1 vs 2 statistics | Offline |
| `analyze_both_bits_price.py` | Analyze both-bit entries | Offline |
