#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_winners.py — 歷年小黨當選議員名單 + 其選區輪廓 → docs/winners.json + winner_zones.json
============================================================================================
由 councilors_long.csv 取出小黨「當選」議員（2014/2018/2022），以其選區所含村里
（候選人在選區每個里皆有得票列）用 shapely 聯集成「選區輪廓」多邊形。

輸出：
  docs/winners.json       名單：[{id,name,party,pg,county,years,zoneCode,photo,wiki}]
  docs/winner_zones.json  GeoJSON：每位當選者一個選區輪廓 feature（properties.id 對應）
鄉鎮市長：歷年無小黨當選紀錄（已查 votedata；小黨斬獲集中於議員）。
"""
from __future__ import annotations
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parties import FOCUS_CODE, party_group  # noqa: E402

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
NORM = ROOT / "data" / "normalized"
DOCS = ROOT / "docs"
GEO = RAW / "cunli_geo_20221118.json"

PARTY_SHORT = {"時代力量": "npp", "台灣基進": "tsp", "綠黨": "green",
               "社會民主黨": "sdp", "樹黨": "tree", "小民參政歐巴桑聯盟": "ob"}


def main() -> None:
    # 1) 當選者 + 各年選區村里
    win: dict[tuple, dict] = {}
    for r in csv.DictReader(open(NORM / "councilors_long.csv", encoding="utf-8-sig")):
        if r["is_small"] != "1" or r["elected"] != "1":
            continue
        key = (r["cand_name"], r["party"], r["county"])
        w = win.setdefault(key, {"years": set(), "zoneByYear": {}, "vills": defaultdict(set)})
        w["years"].add(r["year"])
        w["vills"][r["year"]].add(r["villcode"])
        if r["zone"]:
            w["zoneByYear"][r["year"]] = r["zone"]
    print(f"小黨當選議員：{len(win)} 人")

    # 2) 需要的村里幾何（只載入用到的，省記憶體）
    need = set()
    for w in win.values():
        latest = max(w["years"])
        need |= w["vills"][latest]
    print(f"需要村里幾何：{len(need)}")

    from shapely.geometry import shape, mapping
    from shapely.ops import unary_union
    geos = {}
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    for f in geo["features"]:
        vc = f["properties"]["VILLCODE"]
        if vc in need:
            try:
                geos[vc] = shape(f["geometry"]).buffer(0)
            except Exception:
                pass
    print(f"載入幾何：{len(geos)}")

    # 3) 每位當選者聯集選區輪廓
    def round_coords(o):
        if isinstance(o, list):
            if o and isinstance(o[0], (int, float)):
                return [round(o[0], 5), round(o[1], 5)]
            return [round_coords(x) for x in o]
        return o

    records, feats = [], []
    for (name, party, county), w in sorted(win.items(), key=lambda kv: (kv[0][1], kv[0][2])):
        latest = max(w["years"])
        shapes = [geos[v] for v in w["vills"][latest] if v in geos]
        wid = f"{name}-{county}"
        rec = {"id": wid, "name": name, "party": party,
               "pg": PARTY_SHORT.get(party, party_group(party)),
               "county": county, "years": sorted(w["years"]),
               "zoneCode": w["zoneByYear"].get(latest, ""),
               "photo": None, "wiki": None}
        records.append(rec)
        if shapes:
            poly = unary_union(shapes).simplify(0.0008, preserve_topology=True)
            gm = mapping(poly)
            gm["coordinates"] = round_coords(gm["coordinates"])
            feats.append({"type": "Feature",
                          "properties": {"id": wid, "name": name, "party": party,
                                         "pg": rec["pg"], "county": county},
                          "geometry": gm})

    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "winners.json").write_text(
        json.dumps(records, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (DOCS / "winner_zones.json").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats},
                   ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"寫出 winners.json（{len(records)} 人）、winner_zones.json（{len(feats)} 選區，"
          f"{(DOCS/'winner_zones.json').stat().st_size/1e6:.2f}MB）")


if __name__ == "__main__":
    main()
