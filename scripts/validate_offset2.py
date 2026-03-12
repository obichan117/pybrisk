"""Validate offset 2 tick indices for both-bit entries against known stock prices."""
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

# Collect tick indices per stock from both-bit entries
stock_ticks = {}  # iid -> list of (tick_index, qty, field_type)

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
        if iid not in stock_ticks:
            stock_ticks[iid] = []
        for se in chunk.get("sub_entries", []):
            # Bit 1 field (price+qty)
            if se.get("has_price_qty") and "price_qty" in se:
                pq = se["price_qty"]
                if pq["price_bytes"] > 0:
                    stock_ticks[iid].append((pq["tick_index"], pq["quantity"], "pq"))

            # Also try reading bit 2 field as price+qty format
            if se.get("has_depth") and "depth_update" in se:
                du = se["depth_update"]
                off = se["depth_update_offset"]
                tag = data[off]
                pb = tag & 7
                qb = (tag >> 3) & 7
                if pb > 0 and off + 2 + pb <= len(data):
                    tick = read_le_signed(data, off + 2, pb)
                    qty = read_le_uint(data, off + 2 + pb, qb) if qb > 0 else 0
                    stock_ticks[iid].append((tick, qty, "dp"))

# Show stocks with known prices
KNOWN = [
    (937, "6740", 1060),
    (13, "1605", 60900),
    (1202, "7974", 38880),
    (1589, "9984", 27590),
]

for iid, code, expected_p10 in KNOWN:
    ticks = stock_ticks.get(iid, [])
    if not ticks:
        print(f"\n{code} (iid={iid}): no tick data")
        continue

    exp_tick = price10_to_tick_index(expected_p10)
    pq_ticks = [t for t in ticks if t[2] == "pq" and t[0] > 0]
    dp_ticks = [t for t in ticks if t[2] == "dp" and t[0] > 0]

    print(f"\n{'='*60}")
    print(f"{code} (iid={iid}): expected price10={expected_p10} tick≈{exp_tick}")
    print(f"  PQ entries with positive tick: {len(pq_ticks)}")
    print(f"  DP entries with positive tick: {len(dp_ticks)}")

    # Show unique tick indices and their prices
    from collections import Counter
    all_positive = [t[0] for t in ticks if t[0] > 0]
    if all_positive:
        tick_counts = Counter(all_positive)
        print(f"  Unique positive tick indices:")
        for tick, count in tick_counts.most_common(10):
            p10 = tick_index_to_price10(tick)
            match = " ← MATCH!" if abs(p10 - expected_p10) < expected_p10 * 0.05 else ""
            print(f"    tick={tick:>6d} → price10={p10:>8d} "
                  f"({p10/10:.1f} yen) count={count}{match}")

# Show top stocks by entry count
print(f"\n{'='*60}")
print(f"Top stocks by positive tick count:")
stock_counts = [(iid, len([t for t in ticks if t[0] > 0]))
                for iid, ticks in stock_ticks.items()]
stock_counts.sort(key=lambda x: x[1], reverse=True)
for iid, count in stock_counts[:15]:
    code = issue_to_code.get(str(iid), "????")
    ticks = [t[0] for t in stock_ticks[iid] if t[0] > 0]
    if ticks:
        from collections import Counter
        top_tick = Counter(ticks).most_common(1)[0][0]
        p10 = tick_index_to_price10(top_tick)
        print(f"  {code} (iid={iid:>4d}): {count:>4d} entries, "
              f"most_common_tick={top_tick} → {p10/10:.1f} yen")
