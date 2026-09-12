# -*- coding: utf-8 -*-
"""
Safe, read-only save file operations for the TODO Tracker.

This module provides functions to load and analyze Let-It-Die save files
WITHOUT modifying them. All operations are strictly read-only to prevent
accidental save corruption.
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

# Try to use the project's save_io and helpers if available
try:
    # Add project root to path for imports
    PROJECT_ROOT = Path(__file__).parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))
    
    from save_io import decompress_save
    
    _USE_PROJECT_MODULES = True
except ImportError:
    _USE_PROJECT_MODULES = False
    print("Warning: Could not import project modules, using fallback decompression")


def load_save_data(save_path: str) -> Optional[Dict[str, Any]]:
    """
    Load and decompress a Let-It-Die save file.
    
    Args:
        save_path: Path to the .sav file
        
    Returns:
        Parsed save data as dictionary, or None if loading failed
        
    Raises:
        FileNotFoundError: If save file doesn't exist
        ValueError: If save file format is invalid
    """
    save_path_obj = Path(save_path)
    
    if not save_path_obj.exists():
        raise FileNotFoundError(f"Save file not found: {save_path_obj}")
    
    try:
        if _USE_PROJECT_MODULES:
            # Use project's decompression
            save_data, _ = decompress_save(str(save_path_obj))
            return save_data
        else:
            # Fallback manual decompression
            return _fallback_decompress(save_path_obj)
            
    except Exception as e:
        raise ValueError(f"Failed to load save file: {e}")


def _fallback_decompress(save_path: Path) -> Dict[str, Any]:
    """
    Fallback decompression when project modules are unavailable.
    Implements the same BRG/ZLIB format parsing.
    """
    import struct
    import zlib
    
    with open(save_path, "rb") as f:
        data = f.read()
    
    if len(data) < 16 or data[:4] != b"BRG\x00":
        raise ValueError("Invalid Let It Die save header. Magic BRG\\0 not found.")
    
    offset = 16
    chunks = []
    while offset < len(data):
        if offset + 4 >= len(data):
            break
        uncomp_size = struct.unpack("<I", data[offset:offset+4])[0]
        if uncomp_size == 0:
            break
        comp_size = struct.unpack("<I", data[offset+4:offset+8])[0]
        offset += 8
        chunks.append(zlib.decompress(data[offset:offset+comp_size]))
        offset += comp_size
    
    full_decomp = b"".join(chunks)
    return json.loads(full_decomp.decode("utf-8"))


def get_dustin_sent_analysis(save_data: Optional[Dict[str, Any]]) -> Dict[str, int]:
    """
    Analyze Dustin-sent items in soul.present (Reward Box / base storage).
    These are items sent back to F0/Waiting room via Dustin that appear
    in soul.present with from=DUSTSHOOTER_CHARGE.

    When the player returns to base and opens the Reward Box, these items
    are collected and move into soul.cl (coin locker). Until collected,
    they count as "gathered but not in storage".

    Args:
        save_data: Loaded save data dictionary

    Returns:
        Dict mapping item_id -> count of Dustin-sent items (only type=ITTP_MATERIAL)
    """
    if not isinstance(save_data, dict):
        return {}

    soul = save_data.get("soul", {})
    present = soul.get("present", [])
    if not isinstance(present, list):
        return {}

    # Build set of valid material EIDs from item.items
    item_eid_map = {}  # eid -> itemid
    items_list = save_data.get("item", {}).get("items", [])
    if isinstance(items_list, list):
        for it in items_list:
            if isinstance(it, dict) and it.get("eid") and it.get("itemid"):
                item_eid_map[it["eid"]] = it["itemid"]

    counts = {}
    for p in present:
        if not isinstance(p, dict):
            continue
        # Only count Dustin-sent material items
        if p.get("from") != "DUSTSHOOTER_CHARGE":
            continue
        if p.get("type") != "ITTP_MATERIAL":
            continue
        # val0 is the item ID (e.g., ITMT_FIBER_1)
        item_id = p.get("val0", "")
        if item_id:
            counts[item_id] = counts.get(item_id, 0) + int(p.get("num", 1))

    return counts


def get_storage_analysis(save_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze storage (Coin Locker) contents from save data.
    
    Args:
        save_data: Loaded save data dictionary
        
    Returns:
        Dictionary with storage analysis including:
        - total_slots: Total storage slots
        - used_slots: Used slots count
        - free_slots: Free slots count
        - items: Dict of item_id -> count
        - mushrooms: Dict of msrid -> count  
        - beasts: Dict of bstid -> count
    """
    if not isinstance(save_data, dict):
        return {}
    
    soul = save_data.get("soul", {})
    cl = soul.get("cl", [])
    if not isinstance(cl, list):
        cl = []
    
    # Build set of all occupied eids
    cl_eids = set()
    for entry in cl:
        if isinstance(entry, dict):
            eid = entry.get("eid")
            item_type = entry.get("type")
            if eid and item_type != -1:
                cl_eids.add(eid)
    
    # Count items by type
    items = save_data.get("item", {}).get("items", [])
    if not isinstance(items, list):
        items = []
    
    mushrooms = save_data.get("mushroom", {}).get("msrs", [])
    if not isinstance(mushrooms, list):
        mushrooms = []
    
    beasts = save_data.get("beast", {}).get("bsts", [])
    if not isinstance(beasts, list):
        beasts = []
    
    # Tally counts
    item_counts: Dict[str, int] = {}
    mushroom_counts: Dict[str, int] = {}
    beast_counts: Dict[str, int] = {}
    
    for item in items:
        if isinstance(item, dict):
            eid = item.get("eid")
            item_id = item.get("itemid")
            if eid in cl_eids and item_id:
                item_counts[item_id] = item_counts.get(item_id, 0) + 1
    
    for msr in mushrooms:
        if isinstance(msr, dict):
            eid = msr.get("eid")
            msr_id = msr.get("msrid")
            if eid in cl_eids and msr_id:
                mushroom_counts[msr_id] = mushroom_counts.get(msr_id, 0) + 1
    
    for beast in beasts:
        if isinstance(beast, dict):
            eid = beast.get("eid")
            bst_id = beast.get("bstid")
            if eid in cl_eids and bst_id:
                beast_counts[bst_id] = beast_counts.get(bst_id, 0) + 1
    
    return {
        "total_slots": len(cl),
        "used_slots": len(cl_eids),
        "free_slots": max(0, len(cl) - len(cl_eids)),
        "items": item_counts,
        "mushrooms": mushroom_counts,
        "beasts": beast_counts
    }


def get_deathbag_analysis(save_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze deathbag (fighter inventory) contents from save data.
    The deathbag is stored in soul.deathbag[uid][cid] as slot entries
    with EIDs that reference actual items in item.items, mushroom.msrs,
    beast.bsts, and part.pts.

    Args:
        save_data: Loaded save data dictionary

    Returns:
        Dictionary with deathbag analysis including:
        - items: Dict of item_id -> count (materials in deathbag)
        - mushrooms: Dict of msrid -> count
        - beasts: Dict of bstid -> count
        - equipment: Dict of ptid -> count
    """
    if not isinstance(save_data, dict):
        return {}

    soul = save_data.get("soul", {})
    uid = str(soul.get("uid", ""))
    if not uid:
        user = save_data.get("user", {})
        uid = str(user.get("uid", user.get("steamid", "")))

    deathbag = soul.get("deathbag", {})
    if not isinstance(deathbag, dict) or uid not in deathbag:
        return {"items": {}, "mushrooms": {}, "beasts": {}, "equipment": {}}

    uid_db = deathbag[uid]
    if not isinstance(uid_db, dict):
        return {"items": {}, "mushrooms": {}, "beasts": {}, "equipment": {}}

    # Build EID -> item lookup from all inventories
    item_eid_map = {}      # eid -> itemid (for materials)
    mushroom_eid_map = {}  # eid -> msrid
    beast_eid_map = {}     # eid -> bstid

    items_list = save_data.get("item", {}).get("items", [])
    if isinstance(items_list, list):
        for it in items_list:
            if isinstance(it, dict) and it.get("eid") and it.get("itemid"):
                item_eid_map[it["eid"]] = it["itemid"]

    msrs_list = save_data.get("mushroom", {}).get("msrs", [])
    if isinstance(msrs_list, list):
        for m in msrs_list:
            if isinstance(m, dict) and m.get("eid") and m.get("msrid"):
                mushroom_eid_map[m["eid"]] = m["msrid"]

    bsts_list = save_data.get("beast", {}).get("bsts", [])
    if isinstance(bsts_list, list):
        for b in bsts_list:
            if isinstance(b, dict) and b.get("eid") and b.get("bstid"):
                beast_eid_map[b["eid"]] = b["bstid"]

    # Also build equipment EID -> ptid from part.pts (all UIDs)
    eq_eid_map = {}
    pts = save_data.get("part", {}).get("pts", {})
    if isinstance(pts, dict):
        for uid_key, p_list in pts.items():
            if isinstance(p_list, list):
                for p in p_list:
                    if isinstance(p, dict) and p.get("eid") and p.get("ptid"):
                        eq_eid_map[p["eid"]] = p["ptid"]
    elif isinstance(pts, list):
        for p in pts:
            if isinstance(p, dict) and p.get("eid") and p.get("ptid"):
                eq_eid_map[p["eid"]] = p["ptid"]

    # Tally deathbag contents
    item_counts = {}
    mushroom_counts = {}
    beast_counts = {}
    equipment_counts = {}

    for cid, slots in uid_db.items():
        if not isinstance(slots, list):
            continue
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            eid = slot.get("eid", "")
            itype = slot.get("type", -1)

            if itype == 0 and eid in eq_eid_map:      # Equipment
                ptid = eq_eid_map[eid]
                equipment_counts[ptid] = equipment_counts.get(ptid, 0) + 1
            elif itype == 1 and eid in mushroom_eid_map:   # Mushroom
                msrid = mushroom_eid_map[eid]
                mushroom_counts[msrid] = mushroom_counts.get(msrid, 0) + 1
            elif itype == 2 and eid in beast_eid_map:      # Beast
                bstid = beast_eid_map[eid]
                beast_counts[bstid] = beast_counts.get(bstid, 0) + 1
            elif itype == 3 and eid in item_eid_map:       # Material
                itemid = item_eid_map[eid]
                item_counts[itemid] = item_counts.get(itemid, 0) + 1

    return {
        "items": item_counts,
        "mushrooms": mushroom_counts,
        "beasts": beast_counts,
        "equipment": equipment_counts,
    }


def get_currency_totals(save_data: Optional[Dict[str, Any]]) -> Dict[str, int]:
    """
    Extract all currency amounts from save data.
    
    Args:
        save_data: Loaded save data dictionary
        
    Returns:
        Dictionary with currency amounts:
        - dm: Death Metals (total)
        - kc: Kill Coins
        - spl: Splithium
        - bloodnium: Bloodnium points
        - recycle_points: RE Points
    """
    if not isinstance(save_data, dict):
        return {}
    
    user = save_data.get("user", {})
    soul = save_data.get("soul", {})
    
    return {
        "dm": int(user.get("free_medal", 0)) + int(user.get("paid_medal", 0)),
        "kc": int(soul.get("free_money", 0)) + int(soul.get("paid_money", 0)),
        "spl": int(soul.get("spirit", 0)),
        "bloodnium": int(soul.get("bloodnium_point", 0)),
        "recycle_points": int(soul.get("recycle_point", 0))
    }


def get_save_metadata(save_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract basic metadata from save data.
    
    Returns:
        Dictionary with:
        - player_rank: Player rank (1-130)
        - rank_points: Current rank points
        - bank_level: KC Bank level (1-99)
        - tank_level: SPL Tank level (1-99)
        - tdm_rank: TDM rank string
    """
    if not isinstance(save_data, dict):
        return {}
    
    soul = save_data.get("soul", {})
    
    return {
        "player_rank": int(soul.get("rank", 0)),
        "rank_points": int(soul.get("rank_point", 0)),
        "bank_level": int(soul.get("safe_level", 0)),
        "tank_level": int(soul.get("spirit_tank_level", 0)),
        "tdm_rank": str(soul.get("tdm_rank", "")).split("_")[-1] if soul.get("tdm_rank") else None
    }


def get_player_uid(save_data: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract player UID from save data."""
    if not isinstance(save_data, dict):
        return None
    
    user = save_data.get("user", {})
    return user.get("steamid") or user.get("uid")


def get_save_file_size(save_path: str) -> int:
    """Get the file size of a save file without loading it."""
    path = Path(save_path)
    if path.exists():
        return path.stat().st_size
    return 0


def validate_save_file(save_path: str) -> Tuple[bool, str]:
    """
    Validate that a save file is a proper Let-It-Die save.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    path = Path(save_path)
    
    if not path.exists():
        return False, "File not found"
    
    try:
        with open(path, "rb") as f:
            header = f.read(16)
        
        if len(header) < 16:
            return False, "File too small"
        
        if header[:4] != b"BRG\x00":
            return False, "Invalid save header (not a Let It Die save)"
        
        return True, "Valid save file"
        
    except Exception as e:
        return False, f"Error reading file: {e}"


if __name__ == "__main__":
    # Simple test when run directly
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python read_save.py <path_to_save_file>")
        sys.exit(1)
    
    path = sys.argv[1]
    
    try:
        print(f"Loading save file: {path}")
        data = load_save_data(path)
        print(f"Save loaded successfully!")
        print(f"Player UID: {get_player_uid(data)}")
        
        storage = get_storage_analysis(data)
        print(f"\nStorage Analysis:")
        print(f"  Total slots: {storage['total_slots']}")
        print(f"  Used slots: {storage['used_slots']}")
        print(f"  Free slots: {storage['free_slots']}")
        print(f"  Unique items: {len(storage['items'])}")
        print(f"  Unique mushrooms: {len(storage['mushrooms'])}")
        print(f"  Unique beasts: {len(storage['beasts'])}")
        
        currencies = get_currency_totals(data)
        print(f"\nCurrencies:")
        for name, amount in currencies.items():
            print(f"  {name}: {amount:,}")
        
        metadata = get_save_metadata(data)
        print(f"\nMetadata:")
        print(f"  Rank: {metadata['player_rank']}")
        print(f"  Rank Points: {metadata['rank_points']:,}")
        print(f"  Bank Level: {metadata['bank_level']}")
        print(f"  Tank Level: {metadata['tank_level']}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
