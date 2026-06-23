#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_roads.py — 抓全台主要道路（國道/省道/主要幹道）→ docs/roads.json
=====================================================================
讓候選人規劃掃街路線時有道路骨架可對位。範圍：
  trunk 省道/主要快速道路、primary 主要市區幹道。
（不含國道 motorway——交流道非拜票點；亦不含巷弄，否則過密。）
資料源 OpenStreetMap Overpass（ODbL）。座標取 4 位小數（~11m）縮小檔案。

輸出 docs/roads.json：GeoJSON FeatureCollection，
  properties: {hw: motorway|trunk|primary, ref: 台1/國1…, name}
"""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "docs" / "roads.json"
ENDPOINT = "https://overpass-api.de/api/interpreter"
UA = "tw-council-gis/1.0 (civic research; jtl0513@gmail.com)"
QUERY = """
[out:json][timeout:300];
area["ISO3166-1"="TW"]->.tw;
(
  way["highway"~"^(trunk|primary)$"](area.tw);
);
out geom;
"""


def main() -> None:
    print("查詢 Overpass（全台主要道路，約需 1–3 分鐘）…")
    req = urllib.request.Request(
        ENDPOINT, data=urllib.parse.urlencode({"data": QUERY}).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=320) as r:
        data = json.load(r)

    feats, by_class = [], {}
    for el in data.get("elements", []):
        geom = el.get("geometry")
        if not geom:
            continue
        coords = [[round(p["lon"], 4), round(p["lat"], 4)] for p in geom]
        t = el.get("tags", {})
        hw = t.get("highway")
        by_class[hw] = by_class.get(hw, 0) + 1
        feats.append({
            "type": "Feature",
            "properties": {"hw": hw, "ref": t.get("ref", ""), "name": t.get("name", "")},
            "geometry": {"type": "LineString", "coordinates": coords},
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("道路分類數：", by_class)
    print(f"寫出 {OUT}（{OUT.stat().st_size/1e6:.2f} MB，{len(feats)} 條）")


if __name__ == "__main__":
    main()
