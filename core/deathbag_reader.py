# -*- coding: utf-8 -*-
"""
Deathbag Inventory Reader for Let It Die Save Editor.

Reads the complete contents of fighters' deathbags (the in-game Death Bag / inventory),
as opposed to the Coin Locker (storage). The deathbag is stored in soul.deathbag[uid][cid]
as slot entries with EIDs that reference actual items in part.pts, mushroom.msrs,
beast.bsts, and item.items.

This module provides functions to:
- Read all deathbag items across all fighters
- Get detailed inventory per fighter
- Count items by type
- Resolve EIDs to actual item data (equipment names, mushroom types, beast types, materials)
"""

import json
import os
import sys
from collections import Counter, defaultdict
from core.helpers import get_player_uid, get_equipment_meta, get_or_create_list, PROJECT_ROOT
from core.blueprints import get_bag_equipment_counts


def _build_eid_mappings(save):
    """
    Build lookup dictionaries mapping EIDs to their actual item data.
    Covers equipment (part.pts), materials (item.items), mushrooms (mushroom.msrs),
    and beasts (beast.bsts) across ALL UIDs.
    """
    eid_to_ptid = {}       # equipment: eid -> ptid
    eid_to_eq_data = {}    # equipment: eid -> full part.pts entry
    eid_to_item = {}       # materials: eid -> item entry
    eid_to_mushroom = {}   # mushrooms: eid -> mushroom entry
    eid_to_beast = {}      # beasts: eid -> beast entry
    
    # Equipment from part.pts
    pts_dict = save.get("part", {}).get("pts", {})
    if isinstance(pts_dict, dict):
        for uid_key, p_list in pts_dict.items():
            if isinstance(p_list, list):
                for p in p_list:
                    if isinstance(p, dict) and p.get("eid"):
                        eid = p["eid"]
                        eid_to_ptid[eid] = p.get("ptid", "")
                        eid_to_eq_data[eid] = p
    elif isinstance(pts_dict, list):
        for p in pts_dict:
            if isinstance(p, dict) and p.get("eid"):
                eid = p["eid"]
                eid_to_ptid[eid] = p.get("ptid", "")
                eid_to_eq_data[eid] = p
    
    # Materials from item.items
    items_container = get_or_create_list(save.setdefault("item", {}), "items")
    for it in items_container:
        if isinstance(it, dict) and it.get("eid"):
            eid_to_item[it["eid"]] = it
    
    # Mushrooms from mushroom.msrs
    msrs_container = get_or_create_list(save.setdefault("mushroom", {}), "msrs")
    for m in msrs_container:
        if isinstance(m, dict) and m.get("eid"):
            eid_to_mushroom[m["eid"]] = m
    
    # Beasts from beast.bsts
    bsts_container = get_or_create_list(save.setdefault("beast", {}), "bsts")
    for b in bsts_container:
        if isinstance(b, dict) and b.get("eid"):
            eid_to_beast[b["eid"]] = b
    
    return {
        "eq_ptid": eid_to_ptid,
        "eq_data": eid_to_eq_data,
        "item": eid_to_item,
        "mushroom": eid_to_mushroom,
        "beast": eid_to_beast,
    }


def get_deathbag_fighter_items(save, fighter_cid=None, uid=None):
    """
    Read all items in a fighter's deathbag, resolving EIDs to actual item data.
    
    Args:
        save: The save JSON dict
        fighter_cid: Optional specific fighter CID to read. If None, reads all fighters.
        uid: Optional player UID. If None, auto-resolves from save.
    
    Returns:
        dict: {cid: [item_infos]} where each item_info is a dict with:
            - slot: int (slot number in deathbag)
            - type: int (0=equipment, 1=mushroom, 2=beast, 3=material, -1=empty)
            - eid: str (entity ID, empty for empty slots)
            - site: str (equipment slot site like EQSITE_HEAD)
            - arm_slot: int (arm slot for weapons, -1 for armor)
            - resolved: dict with the actual item data:
                - For type=0: {ptid, name_en, name_es, lvl, dur, ...}
                - For type=1: {msrid, state, eefcid, tefcid, ...}
                - For type=2: {bstid, state, lvl, ...}
                - For type=3: {itemid, gettime, ...}
                - For type=-1: {empty: True}
            - name: str (display name of the item)
    """
    if uid is None:
        uid = str(get_player_uid(save))
    
    soul = save.setdefault("soul", {})
    deathbag = soul.get("deathbag", {})
    
    if not isinstance(deathbag, dict):
        return {}
    
    uid_db = deathbag.get(uid, {})
    if not isinstance(uid_db, dict):
        return {}
    
    mappings = _build_eid_mappings(save)
    
    result = {}
    
    if fighter_cid is not None:
        # Read single fighter
        items = uid_db.get(fighter_cid, [])
        if not isinstance(items, list):
            return {}
        result[fighter_cid] = _resolve_deathbag_items(items, mappings)
    else:
        # Read all fighters
        for cid, items in uid_db.items():
            if isinstance(items, list):
                result[cid] = _resolve_deathbag_items(items, mappings)
    
    return result


def _resolve_deathbag_items(items, mappings):
    """Resolve a list of deathbag slot entries to detailed item info."""
    resolved = []
    
    for item in items:
        if not isinstance(item, dict):
            continue
        
        slot = item.get("slot", 0)
        itype = item.get("type", -1)
        eid = item.get("eid", "")
        site = item.get("site", "")
        arm_slot = item.get("arm_slot", -1)
        
        info = {
            "slot": slot,
            "type": itype,
            "eid": eid,
            "site": site,
            "arm_slot": arm_slot,
            "resolved": {},
            "name": "",
        }
        
        if itype == -1 or not eid:
            # Empty slot
            info["resolved"] = {"empty": True}
            info["name"] = "(Empty Slot)"
        elif itype == 0:
            # Equipment
            ptid = mappings["eq_ptid"].get(eid, "")
            eq_data = mappings["eq_data"].get(eid, {})
            
            if ptid:
                meta = get_equipment_meta(ptid)
                name_en = meta.get("name_en", "") if meta else ""
                name_es = meta.get("name_es", "") if meta else ""
                name = name_en or name_es or ptid
            else:
                name = ptid or "(Unknown Equipment)"
                meta = None
            
            resolved_eq = {
                "ptid": ptid,
                "name_en": meta.get("name_en", "") if meta else "",
                "name_es": meta.get("name_es", "") if meta else "",
                "category": meta.get("category", "") if meta else "",
                "type": meta.get("type", "") if meta else "",
                "lvl": eq_data.get("lvl", item.get("lvl", 0)),
                "dur": eq_data.get("dur", item.get("dur", 0)),
                "rest": eq_data.get("rest", item.get("rest", 0)),
                "spare": eq_data.get("spare", item.get("spare", 0)),
            }
            info["resolved"] = resolved_eq
            info["name"] = name
            
        elif itype == 1:
            # Mushroom
            mush = mappings["mushroom"].get(eid, {})
            msrid = mush.get("msrid", "") or item.get("msrid", "")
            
            # Try to get name from the all_shrooms_beasts_db
            name = msrid
            try:
                sb_path = os.path.join(PROJECT_ROOT, "all_shrooms_beasts_db.json")
                if os.path.exists(sb_path):
                    with open(sb_path, "r", encoding="utf-8") as f:
                        sb_db = json.load(f)
                        meta = sb_db.get(msrid, {})
                        name = meta.get("name_en", meta.get("name_es", msrid)) if meta else msrid
            except Exception:
                pass
            
            info["resolved"] = {
                "msrid": msrid,
                "state": mush.get("state", item.get("state", 0)),
                "eefcid": mush.get("eefcid", ""),
                "tefcid": mush.get("tefcid", ""),
                "posonce": mush.get("posonce", item.get("posonce", 0)),
                "name_en": name,
            }
            info["name"] = name
            
        elif itype == 2:
            # Beast
            beast = mappings["beast"].get(eid, {})
            bstid = beast.get("bstid", "") or item.get("bstid", "")
            
            name = bstid
            try:
                sb_path = os.path.join(PROJECT_ROOT, "all_shrooms_beasts_db.json")
                if os.path.exists(sb_path):
                    with open(sb_path, "r", encoding="utf-8") as f:
                        sb_db = json.load(f)
                        meta = sb_db.get(bstid, {})
                        name = meta.get("name_en", meta.get("name_es", bstid)) if meta else bstid
            except Exception:
                pass
            
            info["resolved"] = {
                "bstid": bstid,
                "state": beast.get("state", item.get("state", 0)),
                "lvl": beast.get("lvl", item.get("lvl", 1)),
                "rwdemsrid": beast.get("rwdemsrid", ""),
                "posonce": beast.get("posonce", item.get("posonce", 0)),
                "name_en": name,
            }
            info["name"] = name
            
        elif itype == 3:
            # Material / Item
            mat = mappings["item"].get(eid, {})
            itemid = mat.get("itemid", "") or item.get("itemid", "")
            
            name = itemid
            # Try to get name from materials database
            try:
                mats_path = os.path.join(PROJECT_ROOT, "all_materials_db.json")
                if os.path.exists(mats_path):
                    with open(mats_path, "r", encoding="utf-8") as f:
                        mats_db = json.load(f)
                        meta = mats_db.get(itemid, {})
                        name = meta.get("name_en", meta.get("name_es", itemid)) if meta else itemid
            except Exception:
                pass
            
            info["resolved"] = {
                "itemid": itemid,
                "gettime": mat.get("gettime", item.get("gettime", 0)),
                "owner": mat.get("owner", ""),
                "name_en": name,
            }
            info["name"] = name
        
        resolved.append(info)
    
    return resolved


def get_deathbag_summary(save, uid=None):
    """
    Get a summary of all deathbag contents across all fighters.
    
    Returns:
        dict: {
            "uid": str,
            "bag_slot": int (capacity from soul.bag_slot),
            "fighters": [
                {
                    "cid": str,
                    "name": str (fighter name from chr data),
                    "class": str (fighter class),
                    "used_slots": int,
                    "total_slots": int,
                    "items_by_type": {0: count_equip, 1: count_mush, 2: count_beast, 3: count_mat},
                    "equipment": [(slot, ptid, name), ...],
                    "mushrooms": [(slot, msrid, name, state), ...],
                    "beasts": [(slot, bstid, name, state, lvl), ...],
                    "materials": [(slot, itemid, name), ...],
                }
            ],
            "totals": {
                "total_items": int,
                "total_equipment": int,
                "total_mushrooms": int,
                "total_beasts": int,
                "total_materials": int,
            }
        }
    """
    if uid is None:
        uid = str(get_player_uid(save))
    
    soul = save.setdefault("soul", {})
    deathbag = soul.get("deathbag", {})
    bag_slot = soul.get("bag_slot", 20)
    
    chr_chrs = soul.get("chr", {}).get("chrs", {}).get(uid, [])
    fighter_names = {}
    fighter_classes = {}
    if isinstance(chr_chrs, list):
        for c in chr_chrs:
            if isinstance(c, dict) and c.get("cid"):
                fighter_names[c["cid"]] = c.get("name", "")
                fighter_classes[c["cid"]] = c.get("type", "")
    
    if not isinstance(deathbag, dict):
        return {"uid": uid, "bag_slot": bag_slot, "fighters": [], "totals": {}}
    
    uid_db = deathbag.get(uid, {})
    if not isinstance(uid_db, dict):
        return {"uid": uid, "bag_slot": bag_slot, "fighters": [], "totals": {}}
    
    mappings = _build_eid_mappings(save)
    
    fighters = []
    totals = Counter()
    
    for cid, items in uid_db.items():
        if not isinstance(items, list):
            continue
        
        resolved = _resolve_deathbag_items(items, mappings)
        
        used_slots = sum(1 for r in resolved if r["type"] != -1)
        total_slots = len(resolved)
        
        items_by_type = Counter(r["type"] for r in resolved)
        
        equipment = []
        mushrooms = []
        beasts = []
        materials = []
        
        for r in resolved:
            if r["type"] == 0:
                eq = r["resolved"]
                equipment.append((r["slot"], eq.get("ptid", ""), r["name"]))
            elif r["type"] == 1:
                mush = r["resolved"]
                mushrooms.append((r["slot"], mush.get("msrid", ""), r["name"], mush.get("state", 0)))
            elif r["type"] == 2:
                bst = r["resolved"]
                beasts.append((r["slot"], bst.get("bstid", ""), r["name"], bst.get("state", 0), bst.get("lvl", 1)))
            elif r["type"] == 3:
                mat = r["resolved"]
                materials.append((r["slot"], mat.get("itemid", ""), r["name"]))
        
        fighter_info = {
            "cid": cid,
            "name": fighter_names.get(cid, cid),
            "class": fighter_classes.get(cid, ""),
            "used_slots": used_slots,
            "total_slots": total_slots,
            "items_by_type": dict(items_by_type),
            "equipment": equipment,
            "mushrooms": mushrooms,
            "beasts": beasts,
            "materials": materials,
        }
        fighters.append(fighter_info)
        
        totals["total_items"] += used_slots
        totals["total_equipment"] += len(equipment)
        totals["total_mushrooms"] += len(mushrooms)
        totals["total_beasts"] += len(beasts)
        totals["total_materials"] += len(materials)
    
    # Sort fighters by name
    fighters.sort(key=lambda f: f["name"].lower())
    
    return {
        "uid": uid,
        "bag_slot": bag_slot,
        "fighters": fighters,
        "totals": dict(totals),
    }


def get_deathbag_material_counts(save, uid=None):
    """
    Count materials in the deathbag by itemid.
    
    Returns:
        Counter: {itemid: count} for all materials in all fighters' deathbags
    """
    if uid is None:
        uid = str(get_player_uid(save))
    
    soul = save.setdefault("soul", {})
    deathbag = soul.get("deathbag", {})
    
    if not isinstance(deathbag, dict):
        return Counter()
    
    uid_db = deathbag.get(uid, {})
    if not isinstance(uid_db, dict):
        return Counter()
    
    mappings = _build_eid_mappings(save)
    counts = Counter()
    
    for cid, items in uid_db.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("type") == 3 and item.get("eid"):
                mat = mappings["item"].get(item["eid"], {})
                itemid = mat.get("itemid", "") or item.get("itemid", "")
                if itemid:
                    counts[itemid] += 1
    
    return counts


def get_deathbag_mushroom_counts(save, uid=None):
    """
    Count mushrooms in the deathbag by msrid.
    
    Returns:
        Counter: {msrid: count} for all mushrooms in all fighters' deathbags
    """
    if uid is None:
        uid = str(get_player_uid(save))
    
    soul = save.setdefault("soul", {})
    deathbag = soul.get("deathbag", {})
    
    if not isinstance(deathbag, dict):
        return Counter()
    
    uid_db = deathbag.get(uid, {})
    if not isinstance(uid_db, dict):
        return Counter()
    
    mappings = _build_eid_mappings(save)
    counts = Counter()
    
    for cid, items in uid_db.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("type") == 1 and item.get("eid"):
                mush = mappings["mushroom"].get(item["eid"], {})
                msrid = mush.get("msrid", "") or item.get("msrid", "")
                if msrid:
                    counts[msrid] += 1
    
    return counts


def get_deathbag_beast_counts(save, uid=None):
    """
    Count beasts in the deathbag by bstid.
    
    Returns:
        Counter: {bstid: count} for all beasts in all fighters' deathbags
    """
    if uid is None:
        uid = str(get_player_uid(save))
    
    soul = save.setdefault("soul", {})
    deathbag = soul.get("deathbag", {})
    
    if not isinstance(deathbag, dict):
        return Counter()
    
    uid_db = deathbag.get(uid, {})
    if not isinstance(uid_db, dict):
        return Counter()
    
    mappings = _build_eid_mappings(save)
    counts = Counter()
    
    for cid, items in uid_db.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("type") == 2 and item.get("eid"):
                beast = mappings["beast"].get(item["eid"], {})
                bstid = beast.get("bstid", "") or item.get("bstid", "")
                if bstid:
                    counts[bstid] += 1
    
    return counts


def get_deathbag_equipment_counts(save, uid=None):
    """
    Count equipment in the deathbag by ptid.
    Unlike get_bag_equipment_counts() which infers from part.pts ownership,
    this directly reads soul.deathbag slot entries.
    
    Returns:
        Counter: {ptid: count} for all equipment in all fighters' deathbags
    """
    if uid is None:
        uid = str(get_player_uid(save))
    
    soul = save.setdefault("soul", {})
    deathbag = soul.get("deathbag", {})
    
    if not isinstance(deathbag, dict):
        return Counter()
    
    uid_db = deathbag.get(uid, {})
    if not isinstance(uid_db, dict):
        return Counter()
    
    mappings = _build_eid_mappings(save)
    counts = Counter()
    
    for cid, items in uid_db.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("type") == 0 and item.get("eid"):
                ptid = mappings["eq_ptid"].get(item["eid"], "")
                if ptid:
                    counts[ptid] += 1
    
    return counts
