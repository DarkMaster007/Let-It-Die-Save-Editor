#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Let It Die - Deathbag Reader for Active Fighter

Select an encrypted .sav file, decrypt/decompress it, and display
the deathbag (in-game inventory) contents of the active fighter
(the one with state="USE" in soul.chr.chrs).

Usage:
    python read_deathbag.py [path_to_save.sav]
    
If no path is given, a file picker dialog opens.
Works on Windows and Linux (CLI mode falls back to console prompt).
"""

import os
import sys

# Ensure we can import from the project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import json
from core.deathbag_reader import get_deathbag_fighter_items, get_deathbag_summary
from core.fighters import get_all_fighters_info, get_player_uid
from core.helpers import repair_save_list_structures
from save_io import decompress_save


def pick_save_file():
    """Pick a .sav file via GUI dialog or CLI prompt."""
    # Try GUI first
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        
        sav_files = []
        for d in [
            os.path.join(BASE_DIR, "Savedata"),
            r"E:\SteamLibrary\steamapps\common\LET IT DIE\Savedata",
            r"C:\Program Files (x86)\Steam\steamapps\common\LET IT DIE\Savedata",
            r"C:\Program Files\Steam\steamapps\common\LET IT DIE\Savedata",
        ]:
            if os.path.isdir(d):
                sav_files.extend([
                    os.path.join(d, f) for f in os.listdir(d) if f.endswith(".sav")
                ])
        
        if sav_files:
            # Prefer the most recently modified
            sav_files.sort(key=os.path.getmtime, reverse=True)
            initial_dir = os.path.dirname(sav_files[0])
            initial_file = os.path.basename(sav_files[0])
        else:
            initial_dir = BASE_DIR
            initial_file = ""
        
        path = filedialog.askopenfilename(
            title="Select LET IT DIE Save File (.sav)",
            filetypes=[("Save files", "*.sav"), ("All files", "*.*")],
            initialdir=initial_dir,
            initialfile=initial_file,
        )
        root.destroy()
        return path if path else None
        
    except Exception:
        pass
    
    # CLI fallback
    print("\nEnter the full path to your .sav file:")
    print(f"  Example: {os.path.join(BASE_DIR, 'Savedata', '76561198140783693.sav')}")
    return input("Path: ").strip().strip('"')


def find_active_fighter_cid(save):
    """
    Find the CID of the active fighter (state="USE") in the save.
    Returns the CID string, or None if no active fighter found.
    """
    uid = str(get_player_uid(save))
    chr_chrs = save.get("soul", {}).get("chr", {}).get("chrs", {}).get(uid, [])
    
    if not isinstance(chr_chrs, list):
        return None
    
    for c in chr_chrs:
        if isinstance(c, dict) and c.get("state") == "USE":
            return c.get("cid")
    
    return None


def main():
    # 1. Pick the save file
    if len(sys.argv) > 1:
        save_path = sys.argv[1]
    else:
        save_path = pick_save_file()
    
    if not save_path:
        print("No save file selected. Exiting.")
        return
    
    if not os.path.exists(save_path):
        print(f"Error: File not found: {save_path}")
        return
    
    print(f"\nLoading save file: {save_path}")
    print(f"File size: {os.path.getsize(save_path):,} bytes")
    
    # 2. Decompress/decrypt the save
    try:
        save, version = decompress_save(save_path)
        print(f"Save version: {version}")
        print("Decompression successful.\n")
    except Exception as e:
        print(f"Error decompressing save: {e}")
        return
    
    # 3. Repair list structures
    repair_save_list_structures(save)
    
    # 4. Get player info
    uid = str(get_player_uid(save))
    print(f"Player UID: {uid}")
    
    user = save.get("user", {})
    player_name = user.get("nm", "Unknown")
    print(f"Player name: {player_name}")
    
    # 5. Find active fighter
    active_cid = find_active_fighter_cid(save)
    
    all_fighters = get_all_fighters_info(save)
    print(f"\nAll fighters ({len(all_fighters)}):")
    for f in all_fighters:
        active_mark = " <-- ACTIVE" if f["cid"] == active_cid else ""
        print(f"  [{f['class']}] {f['name']} (Grade {f['grade']}, Lvl {f['level']}){active_mark}")
    
    if active_cid is None:
        print("\nNo active fighter found (no fighter with state='USE').")
        print("Available CIDs in deathbag:")
        soul = save.get("soul", {})
        deathbag = soul.get("deathbag", {})
        if isinstance(deathbag, dict) and uid in deathbag:
            for cid in deathbag.get(uid, {}):
                print(f"  {cid}")
        return
    
    # 6. Read deathbag for active fighter
    print(f"\n{'='*60}")
    print(f"DEATHBAG FOR ACTIVE FIGHTER: {active_cid}")
    print(f"{'='*60}")
    
    fighter_db = get_deathbag_fighter_items(save, fighter_cid=active_cid)
    
    if not fighter_db:
        print("  No deathbag data found for this fighter.")
        return
    
    for cid, items in fighter_db.items():
        # Get fighter info for name/class
        fighter_info = next((f for f in all_fighters if f["cid"] == cid), None)
        fighter_name = fighter_info["name"] if fighter_info else cid
        fighter_class = fighter_info["class_name"] if fighter_info else "Unknown"
        
        print(f"\n  Fighter: {fighter_name} ({fighter_class})")
        print(f"  CID: {cid}")
        print(f"  Slots: {len(items)} total")
        
        used = [it for it in items if it["type"] != -1]
        empty = [it for it in items if it["type"] == -1]
        print(f"  Used: {len(used)} | Empty: {len(empty)}")
        
        if not used:
            print("  (Deathbag is empty)")
            continue
        
        # Group by type
        equipment = [it for it in used if it["type"] == 0]
        mushrooms = [it for it in used if it["type"] == 1]
        beasts = [it for it in used if it["type"] == 2]
        materials = [it for it in used if it["type"] == 3]
        
        current_slot = 0
        for item in items:
            slot = item["slot"]
            itype = item["type"]
            name = item["name"]
            eid = item["eid"][:24] + "..." if item["eid"] and len(item["eid"]) > 24 else item["eid"] or "(none)"
            
            if itype == -1:
                current_slot = slot + 1
                continue
            
            print(f"\n  ┌── Slot {slot}")
            
            if itype == 0:
                # Equipment
                eq = item["resolved"]
                ptid = eq.get("ptid", "")
                lvl = eq.get("lvl", 0)
                dur = eq.get("dur", 0)
                site = item["site"] or "-"
                arm = item["arm_slot"]
                
                print(f"  │ Type: EQUIPMENT")
                print(f"  │ PTID: {ptid}")
                print(f"  │ Name: {name}")
                if lvl:
                    print(f"  │ Level: {lvl}")
                if dur:
                    print(f"  │ Durability: {dur:,}")
                print(f"  │ Site: {site}")
                print(f"  │ Arm Slot: {arm}")
                print(f"  │ EID: {eid}")
                
            elif itype == 1:
                # Mushroom
                mush = item["resolved"]
                msrid = mush.get("msrid", "")
                state = mush.get("state", 0)
                state_str = "COOKED" if state else "RAW"
                eefcid = mush.get("eefcid", "") or "-"
                tefcid = mush.get("tefcid", "") or "-"
                
                print(f"  │ Type: MUSHROOM")
                print(f"  │ MSRID: {msrid}")
                print(f"  │ Name: {name}")
                print(f"  │ State: {state_str}")
                print(f"  │ EEFCID: {eefcid}")
                print(f"  │ TEFCID: {tefcid}")
                print(f"  │ EID: {eid}")
                
            elif itype == 2:
                # Beast
                bst = item["resolved"]
                bstid = bst.get("bstid", "")
                state = bst.get("state", 0)
                lvl = bst.get("lvl", 1)
                rwdemsrid = bst.get("rwdemsrid", "") or "-"
                
                print(f"  │ Type: BEAST")
                print(f"  │ BSTID: {bstid}")
                print(f"  │ Name: {name}")
                print(f"  │ State: {'ALIVE' if state == 0 else 'DEAD'}")
                print(f"  │ Level: {lvl}")
                print(f"  │ Reward MSR: {rwdemsrid}")
                print(f"  │ EID: {eid}")
                
            elif itype == 3:
                # Material
                mat = item["resolved"]
                itemid = mat.get("itemid", "")
                gettime = mat.get("gettime", 0)
                
                print(f"  │ Type: MATERIAL")
                print(f"  │ ItemID: {itemid}")
                print(f"  │ Name: {name}")
                if gettime:
                    import datetime
                    dt = datetime.datetime.fromtimestamp(gettime)
                    print(f"  │ Obtained: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  │ EID: {eid}")
            
            current_slot = slot + 1
        
        print(f"\n  └{'─'*(4+len(str(current_slot-1))) if items else '─'}")
    
    # 7. Summary
    print(f"\n{'='*60}")
    print("DEATHBAG SUMMARY")
    print(f"{'='*60}")
    
    summary = get_deathbag_summary(save)
    totals = summary["totals"]
    
    print(f"  Total items across all fighters: {totals.get('total_items', 0)}")
    print(f"    Equipment:  {totals.get('total_equipment', 0)}")
    print(f"    Mushrooms:  {totals.get('total_mushrooms', 0)}")
    print(f"    Beasts:     {totals.get('total_beasts', 0)}")
    print(f"    Materials:  {totals.get('total_materials', 0)}")
    print(f"  Bag slot capacity (soul.bag_slot): {summary['bag_slot']}")


if __name__ == "__main__":
    main()
