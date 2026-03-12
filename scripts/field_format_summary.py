"""Summary of field format analysis: offset 1 vs offset 2 with sign handling."""
import json
from collections import Counter
from scripts.binary_decoder import decode_frame, read_le_signed

summary = json.loads(open("docs/research/ws_frames/capture_summary.json").read())
frames = summary.get("frames", summary.get("sample_frames", []))
if not frames:
    hex_previews = summary.get("hex_previews", [])
    frames = [{"hex": h} for h in hex_previews] if hex_previews else []

# For ALL entries with price data (pb > 0), compare offset 1 vs 2
# Now also check if values are valid (any sign) and if pairs cancel
stats = {"off1_abs_range": 0, "off2_abs_range": 0, "total": 0,
         "off1_pos": 0, "off1_neg": 0, "off2_pos": 0, "off2_neg": 0}

# Collect per-stock tick sums at each offset
stock_sums_off1 = Counter()
stock_sums_off2 = Counter()
stock_counts = Counter()

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
        for se in chunk.get("sub_entries", []):
            for field_key, off_key in [("price_qty", "price_qty_offset"),
                                       ("depth_update", "depth_update_offset")]:
                if field_key not in se or off_key not in se:
                    continue
                off = se[off_key]
                tag = data[off]
                pb = tag & 7
                if pb == 0:
                    continue

                stats["total"] += 1
                stock_counts[iid] += 1

                v1 = read_le_signed(data, off + 1, pb)
                if off + 2 + pb <= len(data):
                    v2 = read_le_signed(data, off + 2, pb)
                else:
                    continue

                # Count sign
                if v1 >= 0: stats["off1_pos"] += 1
                else: stats["off1_neg"] += 1
                if v2 >= 0: stats["off2_pos"] += 1
                else: stats["off2_neg"] += 1

                # Check absolute range (0-15000 for valid tick indices)
                if abs(v1) <= 15000: stats["off1_abs_range"] += 1
                if abs(v2) <= 15000: stats["off2_abs_range"] += 1

                stock_sums_off1[iid] += v1
                stock_sums_off2[iid] += v2

print("=== Offset 1 vs 2 comparison (ALL entries with pb > 0) ===")
print(f"Total entries: {stats['total']}")
print(f"\nOffset 1: pos={stats['off1_pos']} neg={stats['off1_neg']} "
      f"|val|<=15000: {stats['off1_abs_range']} "
      f"({100*stats['off1_abs_range']/stats['total']:.1f}%)")
print(f"Offset 2: pos={stats['off2_pos']} neg={stats['off2_neg']} "
      f"|val|<=15000: {stats['off2_abs_range']} "
      f"({100*stats['off2_abs_range']/stats['total']:.1f}%)")

# Check if sums converge to 0 (paired entries cancel)
off1_zero = sum(1 for s in stock_sums_off1.values() if s == 0)
off2_zero = sum(1 for s in stock_sums_off2.values() if s == 0)
off1_small = sum(1 for s in stock_sums_off1.values() if abs(s) < 10)
off2_small = sum(1 for s in stock_sums_off2.values() if abs(s) < 10)
total_stocks = len(stock_counts)

print(f"\n=== Per-stock sum convergence (paired values should cancel) ===")
print(f"Total stocks with data: {total_stocks}")
print(f"Offset 1: sum==0 for {off1_zero} stocks, |sum|<10 for {off1_small} stocks")
print(f"Offset 2: sum==0 for {off2_zero} stocks, |sum|<10 for {off2_small} stocks")

# Show distribution of absolute values
print(f"\n=== Value magnitude distribution ===")
for off_name, off_delta in [("Offset 1", 1), ("Offset 2", 2)]:
    vals = []
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
                for field_key, off_key in [("price_qty", "price_qty_offset"),
                                           ("depth_update", "depth_update_offset")]:
                    if field_key not in se or off_key not in se:
                        continue
                    off = se[off_key]
                    tag = data[off]
                    pb = tag & 7
                    if pb == 0 or off + off_delta + pb > len(data):
                        continue
                    v = read_le_signed(data, off + off_delta, pb)
                    vals.append(abs(v))

    if vals:
        buckets = [(0, 0), (1, 10), (11, 100), (101, 1000),
                   (1001, 10000), (10001, 100000), (100001, float('inf'))]
        print(f"\n  {off_name} |value| distribution:")
        for lo, hi in buckets:
            count = sum(1 for v in vals if lo <= v <= hi)
            pct = 100 * count / len(vals)
            label = f"{lo}-{int(hi)}" if hi < float('inf') else f"{lo}+"
            print(f"    {label:>12s}: {count:>6d} ({pct:>5.1f}%)")
