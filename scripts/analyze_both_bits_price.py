"""Analyze price data specifically from both-bit entries (the only ones f_fh processes).

With the confirmed swap:
- Both-bit entries: bit 1 field → price+qty processing, bit 2 field → depth processing
- Single-bit entries: no-ops in f_fh (data goes to ring buffer f_eh)
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

# Collect both-bit entries with price data in bit 1 field
both_with_price = []  # (iid, code, pb, qb, tick_off1, tick_off2, qty, raw)

for frame_info in frames:
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
        code = issue_to_code.get(str(iid), "????")
        for se in chunk.get("sub_entries", []):
            if not (se.get("has_price_qty") and se.get("has_depth")):
                continue  # Only both-bit entries
            if "price_qty" not in se:
                continue

            pq = se["price_qty"]
            off = se["price_qty_offset"]
            pb = pq["price_bytes"]
            qb = pq["qty_bytes"]

            if pb == 0:
                continue  # No price data

            raw = data[off:off + pq["total_size"]]

            # Read at offset 1 (what f_fh does)
            tick_off1 = read_le_signed(data, off + 1, pb)
            # Read at offset 2 (alternative)
            tick_off2 = read_le_signed(data, off + 2, pb) if off + 2 + pb <= len(data) else None
            qty = pq["quantity"]

            both_with_price.append((iid, code, pb, qb, tick_off1, tick_off2, qty, raw))

print(f"Both-bit entries with price data (pb>0): {len(both_with_price)}")
print()

# Show all entries with their tick index → price10 conversion
for iid, code, pb, qb, t1, t2, qty, raw in both_with_price[:50]:
    p10_1 = tick_index_to_price10(t1) if t1 >= 0 else f"NEG({t1})"
    p10_2 = tick_index_to_price10(t2) if t2 is not None and t2 >= 0 else f"NEG({t2})"
    t2_str = f"{t2:>8d}" if t2 is not None else "    None"
    print(f"  {code} (iid={iid:>4d}) pb={pb} qb={qb} "
          f"@1={t1:>8d} p10={str(p10_1):>12s}  "
          f"@2={t2_str} p10={str(p10_2):>12s}  "
          f"qty={qty:>6d} raw={raw.hex()}")

# Distribution of pb values across ALL both-bit entries
print(f"\n=== Tag distribution for ALL both-bit entries (bit 1 field) ===")
from collections import Counter
tag_counts = Counter()
for frame_info in frames:
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
        for se in chunk.get("sub_entries", []):
            if not (se.get("has_price_qty") and se.get("has_depth")):
                continue
            if "price_qty" not in se:
                continue
            pq = se["price_qty"]
            tag_counts[f"pb={pq['price_bytes']} qb={pq['qty_bytes']}"] += 1

for tag, count in tag_counts.most_common():
    print(f"  {tag}: {count}")
