#!/usr/bin/env python3
"""Read base storage (soul.cl) from encrypted save — items sent to F0/Waiting room via Dustin."""
import sys, os
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from save_io import decompress_save

THIS_DIR = Path(__file__).parent
TYPE_NAMES = {-1: "empty", 0: "equipment", 1: "material", 2: "mushroom", 3: "beast"}

def resolve_eid(eid, save_data):
    """Resolve EID to item info. Checks top-level part.pts + soul item/mushroom/beast."""
    # d['part']['pts'][uid] (TOP LEVEL, not under soul)
    pts = save_data.get('part', {}).get('pts', {})
    if isinstance(pts, dict):
        for uid, entries in pts.items():
            if isinstance(entries, list):
                for e in entries:
                    if isinstance(e, dict) and e.get('eid') == eid:
                        ptid = e.get('ptid', '?')
                        name = e.get('name_en') or e.get('name_ja') or e.get('name') or ptid
                        return ('part.pts', name, ptid, e.get('owner', '?'), e.get('dur', '?'), e.get('lvl', '?'))
    # soul.item.items
    for it in save_data.get('soul', {}).get('item', {}).get('items', []):
        if isinstance(it, dict) and it.get('eid') == eid:
            return ('item.items', it.get('name_en') or it.get('name_ja') or '?', it.get('itemid', '?'), '?', '?', '?')
    # soul.mushroom.msrs
    for m in save_data.get('soul', {}).get('mushroom', {}).get('msrs', []):
        if isinstance(m, dict) and m.get('eid') == eid:
            name = m.get('name_en') or m.get('name_ja') or m.get('name') or '?'
            return ('mushroom.msrs', name, f"MSR:{m.get('msrid','?')}", '?', '?', '?')
    # soul.beast.bsts
    for b in save_data.get('soul', {}).get('beast', {}).get('bsts', []):
        if isinstance(b, dict) and b.get('eid') == eid:
            name = b.get('name_en') or b.get('name_ja') or b.get('name') or '?'
            return ('beast.bsts', name, f"BST:{b.get('bstid','?')}", '?', '?', '?')
    return (None, f'[unresolved:{eid[:12]}...]', '?', '?', '?', '?')

def read_base_storage(save_path):
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
    cl = soul.get('cl', [])
    if not isinstance(cl, list):
        print("soul.cl not found or not a list")
        return

    print(f"\n{'='*60}")
    print(f"BASE STORAGE — soul.cl ({len(cl)} slots)")
    print(f"{'='*60}")

    # Summary
    type_counts = Counter()
    for e in cl:
        if isinstance(e, dict):
            type_counts[e.get('type', -1)] += 1
    print(f"\nContents by type:")
    for t, c in sorted(type_counts.items()):
        print(f"  {TYPE_NAMES.get(t, '?'):12s} (type {t}): {c:5d} slots")
    print(f"  {'TOTAL':12s}: {len(cl):5d} slots")

    # Equipment (type 0) — items sent to F0 via Dustin
    equip = [(e['slot'], e['eid']) for e in cl if isinstance(e, dict) and e.get('type') == 0]
    if equip:
        print(f"\n--- EQUIPMENT IN F0 ({len(equip)} items, sent via Dustin) ---")
        for slot, eid in sorted(equip):
            src, name, idval, owner, dur, lvl = resolve_eid(eid, save_data)
            print(f"  slot {slot:5d}: {name} [{idval}]")
            if owner != '?':
                print(f"           owner={owner}  dur={dur}  lvl={lvl}  src={src}")

    # Materials (type 1) — count by resolved item
    mat_counter = Counter()
    for e in cl:
        if not isinstance(e, dict) or e.get('type') != 1:
            continue
        src, name, idval, *_ = resolve_eid(e['eid'], save_data)
        mat_counter[idval] += 1

    if mat_counter:
        print(f"\n--- MATERIALS IN F0 ({sum(mat_counter.values())} total) ---")
        for idval, count in mat_counter.most_common():
            print(f"  {idval}: {count}")

    # Mushrooms (type 2)
    mush_counter = Counter()
    for e in cl:
        if not isinstance(e, dict) or e.get('type') != 2:
            continue
        src, name, idval, *_ = resolve_eid(e['eid'], save_data)
        mush_counter[idval] += 1

    if mush_counter:
        print(f"\n--- MUSHROOMS IN F0 ({sum(mush_counter.values())} total) ---")
        for idval, count in mush_counter.most_common():
            print(f"  {idval}: {count}")

    # Beasts (type 3)
    beast_counter = Counter()
    for e in cl:
        if not isinstance(e, dict) or e.get('type') != 3:
            continue
        src, name, idval, *_ = resolve_eid(e['eid'], save_data)
        beast_counter[idval] += 1

    if beast_counter:
        print(f"\n--- BEASTS IN F0 ({sum(beast_counter.values())} total) ---")
        for idval, count in beast_counter.most_common():
            print(f"  {idval}: {count}")

    unresolved = sum(1 for e in cl if isinstance(e, dict) and e.get('eid') and resolve_eid(e['eid'], save_data)[0] is None)
    print(f"\nUnresolved EIDs: {unresolved}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Read F0 base storage from Let It Die save")
    parser.add_argument("save_path", nargs="?", help="Encrypted .sav file path")
    args = parser.parse_args()
    save_path = args.save_path
    if not save_path:
        from todo_tracker.read_save import load_save_data
        from save_io import pick_save_file
        save_path = pick_save_file()
        if not save_path:
            print("No save selected")
            sys.exit(1)
    read_base_storage(save_path)
