"""Validate tick delta accumulation for known stocks.

For entries with BOTH bits set, bit 1 = price+qty, bit 2 = depth.
For single-bit entries, data goes through ring buffer (f_eh) — same format.

This script accumulates tick deltas and converts to price10 to see if
the resulting values match known stock prices.
"""
import json
from scripts.binary_decoder import (
    decode_frame, read_le_signed, read_le_uint,
    tick_index_to_price10, price10_to_tick_index,
)

issue_to_code = json.loads(open("docs/research/ws_frames/issue_id_to_code.json").read())
summary = json.loads(open("docs/research/ws_frames/capture_summary.json").read())
frames = summary.get("frames", summary.get("sample_frames", []))
if not frames:
    hex_previews = summary.get("hex_previews", [])
    frames = [{"hex": h} for h in hex_previews] if hex_previews else []

# Known stocks: (iid, code, expected_price10)
KNOWN = [
    (937, "6740", 1060),    # ~106 yen
    (13, "1605", 60900),    # 6090 yen
    (1202, "7974", 38880),  # 3888 yen
    (1589, "9984", 27590),  # 2759 yen
    (78, "2620", None),     # unknown
]

# Collect all entries per stock, preserving order
stock_entries = {}  # iid -> [(frame_idx, bit_type, field_data, raw_bytes)]

for fi, frame_info in enumerate(frames):
    hex_data = frame_info.get("hex", "")
    if not hex_data:
        continue
    data = bytes.fromhex(hex_data)
    try:
        result = decode_frame(data)
    except Exception:
        continue
    if not result or result.get("type") != "stock_data":
        continue

    for chunk in result.get("chunks", []):
        iid = chunk["issue_id"]
        if iid not in stock_entries:
            stock_entries[iid] = []
        for se in chunk.get("sub_entries", []):
            # Extract bit 1 field (price+qty data)
            if se.get("has_price_qty") and "price_qty" in se:
                pq = se["price_qty"]
                off = se["price_qty_offset"]
                raw = data[off:off + pq["total_size"]]
                stock_entries[iid].append((fi, "pq", pq, raw))

            # Extract bit 2 field (depth data — but try reading as price+qty too)
            if se.get("has_depth") and "depth_update" in se:
                du = se["depth_update"]
                off = se["depth_update_offset"]
                raw = data[off:off + du["total_size"]]
                # Also decode as price+qty format for comparison
                tag = data[off]
                pb = tag & 7
                qb = (tag >> 3) & 7
                p_off1 = read_le_signed(data, off + 1, pb) if pb > 0 else 0
                q_off1 = read_le_uint(data, off + 1 + pb, qb) if qb > 0 else 0
                pq_equiv = {
                    "price_delta_ticks": p_off1,
                    "quantity": q_off1,
                    "price_bytes": pb,
                    "qty_bytes": qb,
                }
                stock_entries[iid].append((fi, "dp", pq_equiv, raw))


for iid, code, expected_p10 in KNOWN:
    entries = stock_entries.get(iid, [])
    if not entries:
        print(f"\n{code} (iid={iid}): no entries")
        continue

    pq_entries = [e for e in entries if e[1] == "pq"]
    dp_entries = [e for e in entries if e[1] == "dp"]

    print(f"\n{'='*60}")
    print(f"{code} (iid={iid}): {len(pq_entries)} pq + {len(dp_entries)} dp entries")
    if expected_p10:
        exp_tick = price10_to_tick_index(expected_p10)
        print(f"  Expected: price10={expected_p10} (tick_index≈{exp_tick})")

    # Show first 15 entries with deltas
    all_entries = sorted(entries, key=lambda e: e[0])  # by frame order
    print(f"\n  First entries (offset 1 = f_fh reading):")

    running_tick = 0
    for fi, btype, pq, raw in all_entries[:20]:
        delta = pq["price_delta_ticks"]
        qty = pq.get("quantity", 0)
        pb = pq.get("price_bytes", 0)
        qb = pq.get("qty_bytes", 0)

        if delta != 0:
            running_tick += delta
            price10 = tick_index_to_price10(abs(running_tick)) if running_tick != 0 else 0
            print(f"    f={fi:>4d} {btype} pb={pb} qb={qb} delta={delta:>8d} "
                  f"accum={running_tick:>8d} price10={price10:>8d} "
                  f"raw={raw.hex()}")

    # Summary: distribution of delta sizes for bit 1 (price+qty) entries
    pq_deltas = [e[2]["price_delta_ticks"] for e in pq_entries if e[2]["price_bytes"] > 0]
    dp_deltas = [e[2]["price_delta_ticks"] for e in dp_entries if e[2]["price_bytes"] > 0]

    if pq_deltas:
        pos = sum(1 for d in pq_deltas if d > 0)
        neg = sum(1 for d in pq_deltas if d < 0)
        zero = sum(1 for d in pq_deltas if d == 0)
        min_d, max_d = min(pq_deltas), max(pq_deltas)
        print(f"\n  PQ deltas: pos={pos} neg={neg} zero={zero} range=[{min_d}, {max_d}]")

    if dp_deltas:
        pos = sum(1 for d in dp_deltas if d > 0)
        neg = sum(1 for d in dp_deltas if d < 0)
        zero = sum(1 for d in dp_deltas if d == 0)
        min_d, max_d = min(dp_deltas), max(dp_deltas)
        print(f"  DP deltas: pos={pos} neg={neg} zero={zero} range=[{min_d}, {max_d}]")

    # Check if deltas come in pairs (typical for order book: add+remove)
    all_deltas = [e[2]["price_delta_ticks"] for e in all_entries if e[2]["price_bytes"] > 0]
    total = sum(all_deltas)
    print(f"  Total sum of all deltas: {total}")
