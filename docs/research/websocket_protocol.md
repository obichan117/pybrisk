# BRiSK WebSocket Binary Protocol Analysis

## Capture Details

- **Date**: 2026-03-11, lunchtime JST (12:15:25)
- **Duration**: ~90 seconds of live trading
- **Source**: `wss://sbi.brisk.jp/realtime/0?session={hex_token}`
- **Total frames**: 30,505 binary recv + 60 ping/pong + 5 sync frames
- **Total data**: 1,335,778 bytes (~1.34 MB)
- **Throughput**: ~338 frames/sec, ~14.8 KB/sec

## Transport Layer

The WebSocket sits inside a Socket.IO (Engine.IO) connection on namespace `/v2/user`.

**Connection sequence** (text frames from capture):

1. Client sends: `40/v2/user?api_key=...&visitor_id=...&session_id=...&tabId=...&url=...&_v=...`
2. Server responds: `0{"sid":"...","upgrades":[],"pingInterval":25000,"pingTimeout":5000}`
3. Server sends: `40` (connected) then `40/v2/user,` (namespace join)
4. Client sends: `42/v2/user,["userEvent",{"name":"startLive","data":{...}}]`
5. Binary data streaming begins

After `startLive`, all subsequent data is binary WebSocket frames.

## Message Types (byte 0 low nibble)

| Low nibble | Type | Count | Description |
|---|---|---|---|
| `0x9` | Stock data | 30,440 (99.8%) | Market data updates |
| `0x0` | Ping/pong | 60 (0.2%) | Heartbeat, 9 bytes each, client sends and server echoes |
| `0x8` | Sync | 5 (0.02%) | Periodic sync, 6 bytes: `38 04 00` + 3-byte counter |

## Issue ID Encoding

Stock identifiers (`issue_id`) are encoded as a **LE uint16 marker** where:

```
marker = (issue_id << 4) | 0x9
byte_0 = marker & 0xFF
byte_1 = (marker >> 8) & 0xFF
```

**Decoding**: `issue_id = LE_uint16(byte_0, byte_1) >> 4`

**Verification**: Cross-referenced with `POST /api/stocks_update` where the request body contains known `issue_ids` and the binary response uses the same encoding. Sequential scanning matches perfectly.

**Examples**:

| issue_id | marker (hex) | byte_0 | byte_1 | Stock code |
|---|---|---|---|---|
| 0 | `0x0009` | `09` | `00` | 1301 |
| 1 | `0x0019` | `19` | `00` | 1332 |
| 5 | `0x0059` | `59` | `00` | 1379 |
| 13 | `0x00d9` | `d9` | `00` | 1605 |
| 78 | `0x04e9` | `e9` | `04` | 1982 |
| 1589 | `0x6359` | `59` | `63` | 9984 (SoftBank) |

The low nibble `0x9` acts as a constant tag identifying issue_id markers throughout the binary stream. This is what causes byte 0 to always end in `9` (observed in 99.8% of frames).

## Issue ID to Stock Code Mapping

Derived from `/api/master/{hash}` (800,100 bytes):

- **Record count**: 4,445 records (covers all TSE-listed securities)
- **Record size**: 180 bytes fixed
- **Stock code offset**: bytes 50-53 within each record (ASCII, 4 chars)
- **Record layout**: 16-byte binary header + 164-byte ASCII (Shift-JIS for names)
- **issue_id = record index** (0-based)

The 16-byte header contains 4 LE uint32 values:

| Offset | Field | Example (SoftBank 9984) |
|---|---|---|
| 0 | unknown (flags?) | varies |
| 4 | base_price10 | 36320 (3,632.0 yen) |
| 8 | upper_limit10 | 43320 (4,332.0 yen) |
| 12 | lower_limit10 | 29320 (2,932.0 yen) |

## WASM Decoder Architecture

BRiSK uses an Emscripten-compiled C/C++ WASM module (`fita.{hash}.js` + `.wasm`, ~153 KB) for binary decoding.

### Data Flow

```
WebSocket frame (binary) → _pushWs() → _apiRecieved() → _qr_emplace() → qrm.emplace()
```

### Key WASM Exports (92 total)

| Function | Signature | Purpose |
|---|---|---|
| `_pushWs` | (ptr, len) | Feed raw WebSocket binary data |
| `_apiRecieved` | (ptr, len) | Feed REST binary data (stocks_update, snapshot) |
| `_pushBasePrice` | (ptr, len) | Feed base price data |
| `_getStockPointer` | (issue_id) → ptr | Get WASM heap pointer for stock struct |
| `_getStockView` | (stock_ptr) → ptr | Get view of stock data |
| `_getItaRows` | (stock_ptr) → ptr | Get order book depth rows |
| `_getRenewalTick10` | (issue_id) → tick10 | Get tick size in price10 units |
| `_getTickIndexToPrice10` | (issue_id, tick_idx) → price10 | Tick index to price conversion |
| `_getTickPrice10ToIndex` | (issue_id, price10) → idx | Price to tick index conversion |
| `_fitItaViewRowPrice10` | (stock_ptr) → price10 | Fit order book view row price |
| `_stockCount` | () → count | Returns 4445 (total stocks) |
| `_getDate` | () → YYYYMMDD | Returns trading date as integer |
| `_getSessionDone` | () → 0/1 | Whether trading session is complete |
| `_getFrameNumbers` | () → n | Current frame sequence number |
| `_initialize` | | Initialize WASM state |
| `_unserialize` | | Deserialize snapshot data |
| `_unserializeStock` | | Deserialize single stock |
| `_cloneStock` | | Clone stock state |

### WASM → JavaScript Callback

The WASM module calls this JavaScript function for each decoded entry:

```javascript
function _qr_emplace(stock, type, timestamp_low, timestamp_high,
                     price10, quantity_low, quantity_high, lotSize, frameNumber) {
    qrm.emplace(stock, type,
        uint32(timestamp_low) + uint32(timestamp_high) * 4294967296,  // 64-bit timestamp
        price10,
        uint32(quantity_low) + uint32(quantity_high) * 4294967296,    // 64-bit quantity
        lotSize, frameNumber);
}
```

### qrm Object (JavaScript)

The `qrm` global object stores decoded market data:

```javascript
class QRM {
    qrs = {};  // { stock_ptr: QREntry[] }

    emplace(stock_ptr, type, timestamp, price10, quantity_raw, lotSize, frameNumber) {
        entry.price10 = price10;
        entry.timestamp = timestamp;
        entry.quantity = quantity_raw * lotSize;
        entry.type = type;
        entry.frameNumber = frameNumber;
        this.qrs[stock_ptr].push(entry);
    }

    getQR(stock_ptr, beforeFrame)  // Get entries before frame number
    getLatestQR(stock_ptr)         // Get most recent entry
    size(stock_ptr)                // Entry count
    lastPrice10(stock_ptr)         // Last traded price × 10
}
```

### Decoded Field Semantics

| Field | Type | Description |
|---|---|---|
| `type` | int | 1 = buy trade, 2 = sell trade (hypothesis) |
| `timestamp` | uint64 | Nanoseconds since midnight JST (e.g., 32400000000000 = 09:00:00.000) |
| `price10` | int32 | Price × 10 (e.g., 52900 = 5,290.0 yen) |
| `quantity` | uint64 | Shares traded (already multiplied by lotSize) |
| `frameNumber` | int32 | Sequence number of the WebSocket frame |

### Stock Pointer Table in WASM Memory

The WASM memory contains a contiguous array of 4445 int32 stock pointers at byte offset **254880864** (int32 index 63720216):

```
memory[254880864 + issue_id * 4] = stock_pointer
```

Where `stock_pointer` is the key used in `qrm.qrs` and passed to `_qr_emplace`. This table maps `issue_id → stock_pointer` and was verified to match all 4445 entries in `qrm.qrs`.

## Binary Frame Format (from WASM decompilation)

The format was decoded by decompiling `fita.wasm` (437 KB, 68K lines of pseudocode).

### Frame Header (4+ bytes)

The first 4 bytes are read as a **LE uint32**:

```
bits 0-3:   frame_type (0x9 = stock data, 0x0 = ping, 0x8 = sync)
bits 4-16:  issue_id (13 bits, max 8191)
bits 17-18: ts_extra_bytes (0-3, how many extra bytes for timestamp delta)
bits 19-31: ts_delta_low (13 bits of timestamp delta)
```

Total header size = `5 + ts_extra_bytes` bytes.

**Timestamp delta reconstruction** (corrected from WASM analysis):
```
delta = bits[19:31]  // 13 low bits from header
// WASM always reads ts_extra+1 extra bytes, starting at shift 12 (not 13!)
for i in 0..ts_extra_bytes:  // inclusive, reads ts_extra+1 bytes total
    delta |= extra_byte[i] << (12 + i*8)
running_timestamp += delta  // nanoseconds since midnight JST
```

Note: The shift starts at 12, creating a 1-bit overlap with bit 12 of the header value.
This is harmless because the values are OR'd together.

### Sub-Entry Tag Byte

After the header, sub-entries follow. Each starts with a **tag byte**:

```
bit 0:    is_last (last entry in frame)
bit 1:    has_field_B (order book depth update)
bit 2:    has_field_C (price + quantity = trade/quote)
bit 3:    has_field_D (additional data)
bit 4:    has_field_E (additional data)
bits 5-7: field_A_skip (bytes to skip for marker/continuation, 0-7)
```

**Previously observed "type bytes"** (0x23, 0x43, 0x45, etc.) are actually **sub-entry tag bytes** with this encoding:

| Tag | Binary | Skip | Fields | Last |
|---|---|---|---|---|
| `0x23` | `00100011` | 1 | B | yes |
| `0x25` | `00100101` | 1 | C | yes |
| `0x43` | `01000011` | 2 | B | yes |
| `0x45` | `01000101` | 2 | C | yes |
| `0x65` | `01100101` | 3 | C | yes |
| `0x22` | `00100010` | 1 | B | no |
| `0x46` | `01000110` | 2 | B,C | no |

### Field Size Encoding

Each field's size is self-describing:

- **Fields B, C** (2+ bytes): `size = (tag_uint16 & 7) + 2 + ((tag_uint16 >> 3) & 7)`
- **Fields D, E** (1+ byte): `size = (tag_byte & 7) + 1 + ((tag_byte >> 3) & 7)`

### Field C: Price + Quantity (Trade/Quote Data)

The most important field. Uses a **2-byte tag** (same as field B). Byte layout:

```
tag byte 0: bits 0-2 = price_delta_bytes (P, 0-7)
            bits 3-5 = quantity_bytes (Q, 0-7)
tag byte 1: (part of tag, not used for size calculation)
bytes 2..2+P: signed price delta (LE, two's complement, in tick units)
bytes 2+P..2+P+Q: unsigned quantity (LE)
total size = 2 + P + Q  (matches field B formula: (low3 + 2) + high3)
```

**Price conversion**: The signed delta is in tick units, converted to absolute price10 via the tick table: `price10 = getTickIndexToPrice10(issue_id, base_tick + delta)`.

**Quantity**: Raw quantity, multiplied by `lotSize` (stored in stock struct) to get shares.

**Trade type** is NOT in the binary — it's derived by the WASM decoder by comparing the decoded price against stored bid/ask prices: `type = (price > ask) ? 2 : (price < bid) ? 1 : 0`.

### Field B: Order Book Depth Update

Contains bid/ask depth level changes. First 2 bytes as LE uint16:

```
bit 4: toggle flag (flips a boolean state)
bits 1-3: value A delta (3 bits, applied to byte field at stock+468)
bits 6-8: value B delta (3 bits, applied to int field at stock+472)
bit 9: has extended data (if set, 4 more bytes follow with int32 value)
```

### Multi-Stock Frames (CRITICAL)

A single WebSocket frame contains data for **multiple stocks**. Each stock has its own
header (4+ bytes) followed by sub-entries. The `is_last` flag (bit 0) marks the last
sub-entry **for that stock**, then the next stock's header follows immediately.

```
WS frame = [stock1_header][stock1_sub_entries][stock2_header][stock2_sub_entries]...
```

**Validation**: Of 30,440 stock data frames captured:
- 16,749 (55%) contain a single stock
- 6,862 (23%) contain 2 stocks
- 2,736 (9%) contain 3 stocks
- Up to 9 stocks observed in a single frame
- The same stock can appear multiple times in a frame (different timestamps)

This was validated against the WASM decoder which processes each chunk via `f_yg`
(iterator for one stock's header+sub-entries) called repeatedly by the dispatcher.

### The `08 04 00` Pattern (Decoded)

`0x08` as a sub-entry tag byte = `00001000`:
- bit 0 = 0 → not last
- bit 1 = 0 → no field B
- bit 2 = 0 → no field C
- bit 3 = 1 → has field D
- bits 5-7 = 0 → skip 0

Field D: `0x04` → size = (4 & 7) + 1 + ((4 >> 3) & 7) = 5 + 0 = 5. But only `04 00` follows (2 bytes). This is a **zero-value field D entry** — likely an empty depth level marker.

## Frame Size Distribution

| Size range | Count | Description |
|---|---|---|
| 7-10 bytes | 12,477 | Single sub-entry updates (one tick) |
| 11-30 bytes | 9,682 | 2-3 sub-entries per frame |
| 31-100 bytes | 5,200 | Small batch (3-10 updates) |
| 101-1000 bytes | 2,800 | Medium batch |
| 1000+ bytes | 281 | Large batch (many stocks) |
| 10171 bytes | 1 | Largest observed frame |

**Median frame**: 16 bytes. **Mean frame**: 44 bytes.

## Heartbeat Mechanism

**Ping/Pong** (type `0x0`):

- 9 bytes: `f0` + 8 bytes monotonically increasing value
- Sent by client every ~2.5 seconds
- Server echoes the exact same 9 bytes back
- The 8-byte payload appears to be a nanosecond timestamp

**Sync frames** (type `0x8`):

- 6 bytes: `38 04 00` + 3-byte LE counter
- Sent by server approximately every 18-24 seconds (5 total in 90s capture)
- Counter increments by exactly 3,748,743 between consecutive frames
- Purpose unknown (possibly server-side sequence checkpoint)

## Most Active Stocks During Capture

| issue_id | Code | Frames | Name |
|---|---|---|---|
| 78 | 1982 | 1,571 | Hinichi HD |
| 84 | 2108 | 681 | - |
| 79 | 2001 | 528 | Nisshin Seifun |
| 937 | 6740 | 524 | JDI |
| 3848 | 1570 | 406 | - |
| 641 | 5074 | 381 | - |
| 1202 | 7974 | 285 | Nintendo |
| 1589 | 9984 | 203 | SoftBank Group |
| 1485 | 9434 | 193 | SoftBank Corp |

## Shared Binary Format

The same binary encoding is used across three endpoints:

1. **WebSocket stream** (`/realtime/0`) - incremental real-time updates
2. **REST delta** (`/api/stocks_update/{series}`) - batch catch-up updates
3. **Snapshot** (`/api/snapshot/{hash}`) - full market state (29 MB)

All three use the same issue_id markers, type bytes, and sub-entry structure. The WebSocket stream is the incremental version of the snapshot, achieving the claimed **1/20 compression ratio** through delta encoding.

## WASM Internal Processing (confirmed via WAT bytecode)

### Function Call Chain

```
_pushWs (export)
  → f_xg/205 (stock-level processor, per stock chunk)
    → f_yg/206 (iterator: parse header + sub-entries)
      → f_zg/207 (dispatcher: calls f_eh + f_fh per sub-entry)
        → f_eh/212 (ring buffer: stores ALL raw sub-entry data)
        → f_fh/213 (field processor: price+qty → f_jh → qrm.emplace)
          → f_jh/217 (tick index → price10 conversion)
          → f_lh/219 (order book depth update)
```

### Buffer Swap (confirmed in WAT)

The iterator `f_yg` stores sub-entry field pointers with a **cross-wire**:

| f_yg stores | Buffer offset | f_fh reads as |
|---|---|---|
| bit 1 data (field B) | `buf+8` (local 8) | bit 2 check → price+qty processing |
| bit 2 data (field C) | `buf+4` (local 9) | bit 1 check → depth processing |

This means **bit 1 in the sub-entry tag = depth data**, and **bit 2 = price+qty data** after the swap. Both-bit entries get both fields processed. Single-bit entries are **no-ops in f_fh** — their data goes only through the ring buffer `f_eh`.

### f_fh Price Reading Bug

`f_fh` reads the tick index at **offset 1** from the field start (`h+1`), but the correct offset is **2** (2-byte tag format). This produces incorrect tick indices. Empirical validation:

| Metric | Offset 1 | Offset 2 |
|---|---|---|
| Values in valid range (0-15000) | ~84% | **99.3%** |
| Per-stock paired cancellation (sum→0) | ~45% | **75%** |
| Known price match (±5%) | 0% | **~80%** |

### Ring Buffer f_eh

`f_eh` stores ALL sub-entry raw data (both single-bit and both-bit entries) into a circular buffer. This is the **primary data processing path**. The consumer of this ring buffer has not yet been identified in the WASM — finding it is a remaining task.

### Tick Tables

4 tick tables extracted from WASM data section (saved in `docs/research/ws_frames/tick_tables.json`):

| Table | Bands | Usage |
|---|---|---|
| `standard_tse` | 10 | Default for most stocks |
| `topix100_fine` | 10 | TOPIX 100 components |
| `standard_upper` | 8 | Upper price range |
| `topix100_renewal` | 32 | TOPIX 100 renewal ticks |

Standard TSE example: `<3000¥→1¥ tick`, `<5000¥→5¥`, `<30000¥→10¥`, etc.

Per-stock tick table selection is at stock struct offset 668 (`a[167]`).

### Stock Struct Layout (18,000 bytes per stock)

Key offsets:

| Offset | Field | Notes |
|---|---|---|
| 0 | flex_version | Always 18000 |
| 16 | lotSize | 100 for standard TSE |
| 248 | self_ptr | = stock_ptr |
| 256 | running_timestamp_ns | int64, ns since midnight |
| 264 | last_frame_number | int32 |
| 268 | last_price10 | int32, = `a[67]` |
| 304/312 | running_volume/turnover | int64 |
| 468/472 | depth_level state | field B targets |
| 564 | stock_code_ascii | 4 bytes |
| 572/576/580 | base/upper/lower price10 | from master |
| 656 | trading_date | YYYYMMDD int32 |
| 668 | tick_table_ptr | `a[167]` |

Full layout: `docs/research/ws_frames/stock_struct_layout.json`

## Resolved Questions

1. **Master record header**: The 16-byte binary header contains `[unknown_u32, base_price10, upper_limit10, lower_limit10]`. Confirmed by finding base_price10 values that match expected stock prices.

2. **WASM decoder identified**: The binary protocol is decoded by an Emscripten WASM module. The decoded output is `(type, timestamp_ns, price10, quantity, frameNumber)` per entry. The WASM module calls JavaScript `qrm.emplace()` for each decoded entry.

3. **Issue ID to stock pointer mapping**: Found the complete mapping table in WASM memory at byte offset 254880864. All 4445 entries verified against `qrm.qrs` keys.

4. **Buffer swap confirmed**: WAT bytecode proves f_yg swaps bit 1 → buf+8 and bit 2 → buf+4. f_fh reads them crossed, so bit 1 = depth, bit 2 = price+qty.

5. **2-byte tag format**: Fields B and C both use a 2-byte tag. Price data starts at byte 2 (not byte 1). Offset 2 gives 99.3% valid tick indices vs ~84% for offset 1.

6. **Single-bit entries**: No-ops in f_fh. All data goes through f_eh ring buffer for processing elsewhere.

7. **Trade type derivation**: Type field is NOT encoded in the binary — WASM compares decoded price against stored bid/ask to determine buy (2) vs sell (1).

## Open Questions

1. **Ring buffer consumer**: f_eh stores data for ALL entries, but the function that reads from this buffer hasn't been identified. This is the primary remaining WASM analysis task.

2. **Snapshot format**: The 29 MB snapshot likely uses `_apiRecieved` entry point — same binary format but full state rather than deltas.

3. **Live validation**: Need to run `scripts/cdp_live_reader.py` or `scripts/correlate_ws_decode.py` during market hours to cross-validate our decoder against the WASM's actual output.

## Key Formulas for Implementation

```python
# Encode issue_id to marker bytes
def encode_issue_id(issue_id: int) -> bytes:
    marker = (issue_id << 4) | 0x9
    return marker.to_bytes(2, 'little')

# Decode marker bytes to issue_id
def decode_issue_id(b0: int, b1: int) -> int:
    return ((b0 | (b1 << 8)) >> 4)

# Check if a byte is an issue_id marker start
def is_marker_byte(b: int) -> bool:
    return (b & 0xF) == 0x9

# Check if a byte is a type marker
def is_type_byte(b: int) -> bool:
    return (b & 0xF) in (3, 4, 5) and (b >> 4) >= 2

# Master record: issue_id -> stock code
def get_stock_code(master_data: bytes, issue_id: int) -> str:
    offset = issue_id * 180 + 50
    return master_data[offset:offset+4].decode('ascii').strip()

# Master record: issue_id -> price limits
def get_price_limits(master_data: bytes, issue_id: int) -> dict:
    import struct
    offset = issue_id * 180
    _, base10, upper10, lower10 = struct.unpack('<IIII', master_data[offset:offset+16])
    return {'base_price10': base10, 'upper_limit10': upper10, 'lower_limit10': lower10}

# Decoded qrm entry structure
# {type: int, timestamp: int (ns since midnight), price10: int,
#  quantity: int (shares), frameNumber: int}
```

## Next Steps

1. **Live validation** (immediate): Run `scripts/cdp_live_reader.py` during market hours to stream decoded data via CDP qrm.emplace hook. Verify output matches expected prices for known stocks.

2. **Correlation capture**: Run `scripts/correlate_ws_decode.py` during market hours to simultaneously capture raw WS frames + decoded qrm output. Match by `frameNumber` to validate our binary decoder.

3. **Ring buffer consumer**: Find the WASM function that reads from f_eh's circular buffer. This is needed to understand how single-bit-only entries get processed into qrm.emplace calls.

4. **Native decoder**: Once validated, implement the binary decoder in Python (basis exists in `scripts/binary_decoder.py`) for direct WebSocket consumption without CDP dependency.
