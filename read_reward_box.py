#!/usr/bin/env python3
"""Read Reward Box (soul.present) from encrypted Let-It-Die save — items sent via Dustin to F0."""
import sys, os, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from save_io import decompress_save
from collections import Counter

THIS_DIR = Path(__file__).parent

def read_reward_box(save_path):
    print(f"Reading: {save_path}")
    result = decompress_save(save_path)
    if isinstance(result, tuple):
        save_data = result[0]
    else:
        save_data = result
    if save_data is None:
        print("Failed to decompress")
        return

    soul = save_data.get('soul', {})
    present = soul.get('present', [])

    dustin_items = [p for p in present if p.get('from') == 'DUSTSHOOTER_CHARGE']
    other_items = [p for p in present if p.get('from') != 'DUSTSHOOTER_CHARGE']

    print(f"\n{'='*60}")
    print(f"REWARD BOX — soul.present ({len(present)} total entries)")
    print(f"{'='*60}")

    print(f"\n--- Dustin-sent items in Reward Box ({len(dustin_items)} items) ---")
    if dustin_items:
        mat_counter = Counter()
        for p in dustin_items:
            val0 = p.get('val0', '')
            mat_counter[val0] += 1
        for item_id, count in sorted(mat_counter.items()):
            print(f"  {item_id:30s} x{count}")
        print(f"\n  Total: {len(dustin_items)} individual items (each num=1)")
        print(f"  First sent: {min(p.get('created', 0) for p in dustin_items)}")
        print(f"  Last sent:  {max(p.get('created', 0) for p in dustin_items)}")
    else:
        print("  (none)")

    print(f"\n--- Other present entries ({len(other_items)}) ---")
    other_types = Counter(p.get('type', '?') for p in other_items)
    for t, c in other_types.most_common():
        print(f"  {t}: {c}")
    
    # Show first/last few other entries
    for p in other_items[:3]:
        print(f"  from={p.get('from'):15s} type={p.get('type'):10s} num={p.get('num',0):>8}  created={p.get('created')}")
    if len(other_items) > 3:
        print(f"  ... and {len(other_items)-3} more")

    # deathbox (opened rewards)
    deathbox = soul.get('deathbox', [])
    if deathbox:
        print(f"\n--- Opened Reward Boxes (soul.deathbox): {len(deathbox)} ---")
        for i, item in enumerate(deathbox):
            print(f"  [{i}] type={item.get('type','?'):15s} val0={item.get('val0','?'):30s} rarity={item.get('rarity','?')} created={item.get('created')} opentime={item.get('opentime')}")

    # Check mysterybag (unopened)
    mysterybag = soul.get('mysterybag', {})
    if mysterybag:
        total_bags = sum(len(v) for v in mysterybag.values())
        print(f"\n--- Mystery Bags (unopened): {total_bags} total ---")
        for rarity, bags in sorted(mysterybag.items()):
            print(f"  {rarity}: {len(bags)}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Read Reward Box from Let It Die save")
    parser.add_argument("save_path", nargs="?", help="Encrypted .sav file path")
    args = parser.parse_args()
    save_path = args.save_path
    if not save_path:
        from save_io import pick_save_file
        save_path = pick_save_file()
        if not save_path:
            print("No save selected")
            sys.exit(1)
    read_reward_box(save_path)
