"""Decode BRiSK binary WebSocket frames based on WASM reverse engineering.

Binary format (from WASM decompilation of fita.wasm):

Frame structure:
  [4B header_le32] [0-3B timestamp_extra] [optional fields...] [sub-entries...]

Header (first 4 bytes as LE uint32):
  bits 0-3:   frame_type (0x9 = stock data, 0x0 = ping, 0x8 = sync)
  bits 4-16:  issue_id (13 bits, max 8191)
  bits 17-18: timestamp_extra_bytes (0-3 extra bytes for timestamp)
  bits 19+:   timestamp_delta_low_bits

  Total header size = 5 + timestamp_extra_bytes

Timestamp delta reconstruction:
  delta = bits[19:] | (extra_byte[0] << 12) | (extra_byte[1] << 20) | ...
  running_timestamp += delta  (nanoseconds since midnight)

Sub-entry tag byte:
  bit 0:    last entry in frame
  bit 1:    has price+qty field (book order with tick index + quantity)
  bit 2:    has depth field (book state: toggle, level deltas)
  bit 3:    has field D (1-byte tag, unknown purpose)
  bit 4:    has field E (1-byte tag, unknown purpose)
  bits 5-7: skip size for field A (marker/continuation)

Price+qty field (2-byte tag):
  byte 0 (tag): bits 0-2 = price_bytes (pb), bits 3-5 = qty_bytes (qb)
  byte 1: second tag byte (metadata, not used for price+qty)
  bytes 2..2+pb: signed tick index (LE, two's complement)
  bytes 2+pb..2+pb+qb: unsigned quantity (LE)
  Total size = (pb + 2) + qb

Depth field (2-byte uint16 LE tag):
  Same size formula but interpreted as depth/toggle metadata.
  bit 4: toggle flag, bits 1-3: field_468_delta, bits 6-8: field_472_delta
"""

import json
import struct
from pathlib import Path

FRAMES_DIR = Path("docs/research/ws_frames")


# === Tick Table: tick_index <-> price10 conversion ===
#
# TSE uses variable tick sizes depending on price range.
# The WASM decoder uses tick indices (integer) internally and converts
# to price10 (price * 10) using f_jh(). We replicate that logic here.
#
# Each band: (upper_bound_price10, tick_size_price10)
# Bands are cumulative — tick_index 0 = price10 0.

STANDARD_TSE_BANDS = [
    (30000, 10),        # < 3,000 yen:   1 yen tick
    (50000, 50),        # < 5,000 yen:   5 yen tick
    (300000, 100),      # < 30,000 yen:  10 yen tick
    (500000, 500),      # < 50,000 yen:  50 yen tick
    (3000000, 1000),    # < 300,000 yen: 100 yen tick
    (5000000, 5000),    # < 500,000 yen: 500 yen tick
    (30000000, 10000),  # < 3M yen:      1,000 yen tick
    (50000000, 50000),  # < 5M yen:      5,000 yen tick
    (300000000, 100000),  # < 30M yen:   10,000 yen tick
    (500000000, 500000),  # < 50M yen:   50,000 yen tick
]


def _build_tick_table(bands):
    """Precompute tick table from band definitions.

    Returns list of (band_start_tick, band_start_price10, tick_size_price10, virtual_offset).
    virtual_offset is precomputed so that: price10 = tick_size * (tick_index - virtual_offset).
    """
    table = []
    cumulative_ticks = 0
    cumulative_price10 = 0
    for upper_price10, tick_size in bands:
        ticks_in_band = (upper_price10 - cumulative_price10) // tick_size
        virtual_offset = cumulative_ticks - cumulative_price10 // tick_size
        table.append((cumulative_ticks, cumulative_price10, tick_size, virtual_offset))
        cumulative_ticks += ticks_in_band
        cumulative_price10 = upper_price10
    return table


# Precomputed standard TSE tick table
_TSE_TICK_TABLE = _build_tick_table(STANDARD_TSE_BANDS)


def tick_index_to_price10(tick_index, table=None):
    """Convert a tick index to price10 using the tick table.

    Replicates WASM f_jh(): searches backward through precomputed bands,
    returns tick_size * (tick_index - virtual_offset).
    """
    if table is None:
        table = _TSE_TICK_TABLE
    # Search backward (like WASM f_jh)
    for i in range(len(table) - 1, -1, -1):
        band_start_tick, _, tick_size, virtual_offset = table[i]
        if band_start_tick <= tick_index:
            return tick_size * (tick_index - virtual_offset)
    return 0


def price10_to_tick_index(price10, table=None):
    """Convert price10 to tick index (reverse of tick_index_to_price10)."""
    if table is None:
        table = _TSE_TICK_TABLE
    for i in range(len(table) - 1, -1, -1):
        _, band_start_price10, tick_size, virtual_offset = table[i]
        if band_start_price10 <= price10:
            return virtual_offset + price10 // tick_size
    return 0


def decode_issue_id(b0: int, b1: int) -> int:
    """Decode issue_id from 2-byte marker."""
    return ((b0 | (b1 << 8)) >> 4) & 0x1FFF


def read_le_uint(data: bytes, offset: int, count: int) -> int:
    """Read count bytes as little-endian unsigned integer."""
    val = 0
    for i in range(count):
        if offset + i < len(data):
            val |= data[offset + i] << (i * 8)
    return val


def read_le_signed(data: bytes, offset: int, count: int) -> int:
    """Read count bytes as little-endian signed integer (two's complement)."""
    val = read_le_uint(data, offset, count)
    if count > 0 and count < 4:
        sign_bit = 1 << (count * 8 - 1)
        if val & sign_bit:
            val -= 1 << (count * 8)
    return val


def decode_frame_header(data: bytes):
    """Decode the frame header (first 4+ bytes).

    Returns: (issue_id, timestamp_delta, header_size, flags)
    """
    if len(data) < 4:
        return None

    header = struct.unpack_from("<I", data, 0)[0]

    frame_type = header & 0xF
    if frame_type != 0x9:
        return None  # Not a stock data frame

    issue_id = (header >> 4) & 0x1FFF
    ts_extra_bytes = (header >> 17) & 0x3
    ts_delta_low = header >> 19

    # Read extra timestamp bytes (WASM always reads ts_extra+1 bytes, shift starts at 12)
    ts_delta = ts_delta_low
    shift = 12
    for i in range(ts_extra_bytes + 1):
        if 4 + i < len(data):
            ts_delta |= data[4 + i] << shift
            shift += 8

    header_size = 5 + ts_extra_bytes

    # Extract flags from the first byte
    flags = data[0] if len(data) > 0 else 0

    return {
        "issue_id": issue_id,
        "ts_delta": ts_delta,
        "header_size": header_size,
        "has_price_qty": bool(header & 0x2),
        "has_depth": bool(header & 0x4),
        "has_field_d": bool(header & 0x8),
    }


def decode_field_size(data: bytes, offset: int) -> int:
    """Decode a variable-length field size from a 2-byte value.

    The encoding: low 3 bits + high 3 bits combined.
    """
    if offset >= len(data):
        return 0
    b = data[offset]
    low3 = b & 7
    high3 = (b >> 3) & 7
    return low3 + high3 + 1  # Total bytes including the tag


def decode_price_qty(data: bytes, offset: int):
    """Decode price+quantity field from sub-entry.

    Both bit 1 and bit 2 sub-entry fields use the same binary format:
      2-byte tag (bytes 0-1), followed by price and quantity data.

    Layout:
      byte 0:   tag — bits 0-2 = price_bytes (pb), bits 3-5 = qty_bytes (qb)
      byte 1:   second tag byte (used by depth processing, ignored for price+qty)
      bytes 2..2+pb:     signed tick index (LE, two's complement)
      bytes 2+pb..2+pb+qb: unsigned quantity (LE)

    Total field size = (pb + 2) + qb.

    The tick index is an absolute book level position, converted to price10
    via tick_index_to_price10().
    """
    if offset >= len(data):
        return None

    tag = data[offset]
    price_bytes = tag & 0x7
    qty_bytes = (tag >> 3) & 0x7

    tick_index = 0
    if price_bytes > 0:
        tick_index = read_le_signed(data, offset + 2, price_bytes)

    quantity = 0
    if qty_bytes > 0:
        quantity = read_le_uint(data, offset + 2 + price_bytes, qty_bytes)

    total_size = (price_bytes + 2) + qty_bytes

    return {
        "tick_index": tick_index,
        "quantity": quantity,
        "total_size": total_size,
        "price_bytes": price_bytes,
        "qty_bytes": qty_bytes,
    }


def decode_depth_update(data: bytes, offset: int):
    """Decode depth/book update field (sub-entry bit 2 / "field C").

    Despite bit 2 in the sub-entry tag, this is processed as depth update by WASM
    due to the buffer swap in f_yg/f_fh.

    Format (uint16 LE tag):
      bytes 0-1: uint16 LE tag
        bit 4 (0x10): toggle flag (flips a boolean at stock+296)
        bits 1-3: value delta for field at stock+468
        bits 6-8: value delta for field at stock+472
        bit 9 (0x200): if set, 4-byte signed int follows at offset 2
      bytes 2..end: optional 4-byte signed value (if bit 9 set)

    Stream size = (low3 + 2) + high3 where low3 = byte0 & 7, high3 = (byte0 >> 3) & 7.
    """
    if offset + 1 >= len(data):
        return None

    tag16 = struct.unpack_from("<H", data, offset)[0]
    byte0 = data[offset]

    # Stream size uses same formula as price+qty
    low3 = byte0 & 0x7
    high3 = (byte0 >> 3) & 0x7
    total_size = (low3 + 2) + high3

    toggle = bool(tag16 & 0x10)
    field_468_delta = (tag16 >> 1) & 0x7
    field_472_delta = (tag16 >> 6) & 0x7
    has_extended = bool(tag16 & 0x200)

    extended_value = 0
    if has_extended and offset + 2 + 4 <= len(data):
        extended_value = struct.unpack_from("<i", data, offset + 2)[0]

    return {
        "toggle": toggle,
        "field_468_delta": field_468_delta,
        "field_472_delta": field_472_delta,
        "has_extended": has_extended,
        "extended_value": extended_value,
        "total_size": total_size,
        "raw_tag16": tag16,
    }


def decode_sub_entries(data: bytes, start: int):
    """Decode sub-entries from the binary stream.

    Each sub-entry has:
      byte 0: flags | (field_a_skip << 5)
      [field A]: skip bytes (continuation/marker data)
      [bit 1 field]: if bit 1 — price+qty (WASM swaps: iterator stores at buf[8],
                     processor reads from buf[8] for price+qty logic)
      [bit 2 field]: if bit 2 — depth update (iterator stores at buf[4],
                     processor reads from buf[4] for depth logic)
      [field D]: if bit 3
      [field E]: if bit 4
    """
    entries = []
    pos = start

    while pos < len(data):
        if pos >= len(data):
            break

        tag = data[pos]
        field_a_size = (tag >> 5) & 0x7
        has_price_qty = bool(tag & 0x2)   # bit 1 → price+qty (after WASM swap)
        has_depth = bool(tag & 0x4)       # bit 2 → depth update (after WASM swap)
        has_field_d = bool(tag & 0x8)
        has_field_e = bool(tag & 0x10)
        is_last = bool(tag & 0x1)

        entry = {
            "offset": pos,
            "tag": tag,
            "field_a_size": field_a_size,
            "has_price_qty": has_price_qty,
            "has_depth": has_depth,
            "has_d": has_field_d,
            "has_e": has_field_e,
            "is_last": is_last,
        }

        # Advance past field A
        field_pos = pos + field_a_size

        # Bit 1 field: price + quantity (1-byte semantic tag, 2-byte stream tag)
        if has_price_qty and field_pos < len(data):
            pq = decode_price_qty(data, field_pos)
            if pq:
                entry["price_qty"] = pq
                entry["price_qty_offset"] = field_pos
                field_pos += pq["total_size"]

        # Bit 2 field: depth/book update (uint16 LE tag)
        if has_depth and field_pos < len(data):
            du = decode_depth_update(data, field_pos)
            if du:
                entry["depth_update"] = du
                entry["depth_update_offset"] = field_pos
                field_pos += du["total_size"]

        # Field D (1-byte tag)
        if has_field_d and field_pos < len(data):
            d_byte = data[field_pos]
            d_size = ((d_byte & 0x7) + 1) + ((d_byte >> 3) & 0x7)
            entry["field_d_offset"] = field_pos
            entry["field_d_size"] = d_size
            field_pos += d_size

        # Field E (1-byte tag)
        if has_field_e and field_pos < len(data):
            e_byte = data[field_pos]
            e_size = ((e_byte & 0x7) + 1) + ((e_byte >> 3) & 0x7)
            entry["field_e_offset"] = field_pos
            entry["field_e_size"] = e_size
            field_pos += e_size

        entry["total_size"] = field_pos - pos
        entries.append(entry)

        if is_last:
            break
        # Guard against infinite loop: if no progress was made, stop
        if field_pos <= pos:
            break
        pos = field_pos

    return entries


def decode_stock_chunk(data: bytes, offset: int):
    """Decode one stock's data chunk (header + sub-entries) starting at offset.

    Returns: (chunk_dict, next_offset) or (None, offset).
    """
    if offset + 4 > len(data):
        return None, offset

    header = struct.unpack_from("<I", data, offset)[0]
    frame_type = header & 0xF
    if frame_type != 0x9:
        return None, offset

    issue_id = (header >> 4) & 0x1FFF
    ts_extra_bytes = (header >> 17) & 0x3
    ts_delta_low = header >> 19

    # Read extra timestamp bytes (WASM always reads ts_extra+1 bytes starting at offset+4)
    ts_delta = ts_delta_low
    shift = 12  # WASM starts at shift 12, not 13
    for i in range(ts_extra_bytes + 1):
        if offset + 4 + i < len(data):
            ts_delta |= data[offset + 4 + i] << shift
            shift += 8

    header_size = 5 + ts_extra_bytes
    sub_start = offset + header_size

    # For frame_type 0x9, bit 3 is always set, so we always decode sub-entries
    sub_entries = decode_sub_entries(data, sub_start)

    # Find where this chunk ends
    if sub_entries:
        last = sub_entries[-1]
        next_offset = last["offset"] + last["total_size"]
    else:
        next_offset = sub_start

    chunk = {
        "issue_id": issue_id,
        "ts_delta": ts_delta,
        "header_size": header_size,
        "sub_entries": sub_entries,
        "chunk_start": offset,
        "chunk_end": next_offset,
    }
    return chunk, next_offset


def decode_frame(data: bytes):
    """Fully decode a binary WebSocket frame (may contain multiple stocks)."""
    if len(data) < 4:
        return None

    # Check frame type
    frame_type = data[0] & 0xF
    if frame_type == 0x0:
        return {"type": "ping", "size": len(data)}
    if frame_type == 0x8:
        return {"type": "sync", "size": len(data)}
    if frame_type != 0x9:
        return {"type": "unknown", "tag": frame_type, "size": len(data)}

    # Decode all stock chunks within the frame
    chunks = []
    pos = 0
    while pos + 4 <= len(data):
        chunk, next_pos = decode_stock_chunk(data, pos)
        if chunk is None or next_pos <= pos:
            break
        chunks.append(chunk)
        pos = next_pos

    if not chunks:
        return None

    result = {
        "type": "stock_data",
        "chunks": chunks,
        "issue_id": chunks[0]["issue_id"],
        "ts_delta": chunks[0]["ts_delta"],
        "header_size": chunks[0]["header_size"],
        "consumed": pos,
        "raw_hex": data.hex(),
    }

    # Backward compat: flatten sub_entries from first chunk
    if chunks[0]["sub_entries"]:
        result["sub_entries"] = chunks[0]["sub_entries"]

    return result


def main():
    """Test decoder on captured data."""
    # Load captured frames
    summary_path = FRAMES_DIR / "capture_summary.json"
    if not summary_path.exists():
        print(f"No capture data at {summary_path}")
        print("Run correlate_ws_decode.py during market hours first.")
        return

    summary = json.loads(summary_path.read_text())

    # Load issue_id -> code mapping
    code_map_path = FRAMES_DIR / "issue_id_to_code.json"
    issue_to_code = {}
    if code_map_path.exists():
        issue_to_code = json.loads(code_map_path.read_text())

    # Decode sample frames
    frames = summary.get("frames", summary.get("sample_frames", []))
    if not frames:
        # Try hex previews
        hex_previews = summary.get("hex_previews", [])
        frames = [{"hex": h} for h in hex_previews[:50]] if hex_previews else []

    print(f"Decoding {len(frames)} sample frames...\n")

    for i, frame_info in enumerate(frames[:30]):
        hex_data = frame_info.get("hex", "")
        if not hex_data:
            continue

        data = bytes.fromhex(hex_data)
        result = decode_frame(data)

        if not result:
            continue

        if result["type"] == "stock_data":
            code = issue_to_code.get(str(result["issue_id"]), "????")
            print(f"Frame {i}: {code} (iid={result['issue_id']}) "
                  f"ts_delta={result['ts_delta']} "
                  f"header={result['header_size']}B "
                  f"total={len(data)}B")
            print(f"  hex: {result['raw_hex']}")

            if "sub_entries" in result:
                for j, se in enumerate(result["sub_entries"]):
                    parts = []
                    if se.get("has_price_qty") and "price_qty" in se:
                        pq = se["price_qty"]
                        p10 = tick_index_to_price10(pq['tick_index']) if pq['tick_index'] >= 0 else 0
                        parts.append(f"tick={pq['tick_index']} "
                                     f"price10={p10} "
                                     f"qty={pq['quantity']}")
                    if se.get("has_depth") and "depth_update" in se:
                        du = se["depth_update"]
                        parts.append(f"depth(tag=0x{du['raw_tag16']:04x})")
                    detail = ", ".join(parts) if parts else "no fields"
                    print(f"  sub[{j}]: tag=0x{se['tag']:02x} "
                          f"last={se['is_last']} {detail}")
        else:
            print(f"Frame {i}: {result['type']} ({len(data)}B)")


if __name__ == "__main__":
    main()
