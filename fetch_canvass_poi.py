#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_canvass_poi.py — 抓全台「拜票掃街熱點」POI → docs/canvass.json
====================================================================
候選人實體拜票/曝光的據點：傳統市場、夜市、郵局、宮廟、車站。
資料源：OpenStreetMap Overpass API（ODbL 授權，需標註 © OpenStreetMap contributors）。
以台灣行政區 area（ISO3166-1=TW）過濾，排除對岸 POI。

輸出 docs/canvass.json：
  {"meta":{...}, "market":[[lng,lat,"名稱"],...], "post":[...], "temple":[...], "transit":[...]}
座標取 5 位小數（約 1m）以縮小檔案。

用法：python3 fetch_canvass_poi.py
"""
from __future__ import annotations
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "docs" / "canvass.json"
ENDPOINT = "https://overpass-api.de/api/interpreter"
UA = "tw-council-gis/1.0 (civic research; jtl0513@gmail.com)"

QUERY = """
[out:json][timeout:300];
area["ISO3166-1"="TW"]->.tw;
(
  nwr["amenity"="marketplace"](area.tw);
  nwr["amenity"="post_office"](area.tw);
  nwr["amenity"="place_of_worship"](area.tw);
  node["railway"~"^(station|halt)$"](area.tw);
);
out center tags;
"""


def categorize(tags: dict) -> str | None:
    a = tags.get("amenity")
    if a == "marketplace":
        return "market"
    if a == "post_office":
        return "post"
    if a == "place_of_worship":
        return "temple"
    if tags.get("railway") in ("station", "halt"):
        return "transit"
    return None


def name_of(tags: dict, cat: str) -> str:
    for k in ("name", "name:zh", "name:zh-Hant", "official_name", "alt_name"):
        if tags.get(k):
            return tags[k]
    return {"market": "（未命名市場）", "post": "郵局", "temple": "（未命名廟宇）",
            "transit": "車站"}[cat]


def main() -> None:
    print("查詢 Overpass（全台四類 POI，約需 1–3 分鐘）…")
    req = urllib.request.Request(
        ENDPOINT, data=urllib.parse.urlencode({"data": QUERY}).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=320) as r:
        data = json.load(r)

    buckets: dict[str, list] = {"market": [], "post": [], "temple": [], "transit": []}
    skipped = 0
    for el in data.get("elements", []):
        tags = el.get("tags") or {}
        cat = categorize(tags)
        if not cat:
            skipped += 1
            continue
        if el["type"] == "node":
            lat, lng = el.get("lat"), el.get("lon")
        else:  # way / relation → out center
            c = el.get("center") or {}
            lat, lng = c.get("lat"), c.get("lon")
        if lat is None or lng is None:
            continue
        buckets[cat].append([round(lng, 5), round(lat, 5), name_of(tags, cat)])

    meta = {k: len(v) for k, v in buckets.items()}
    out = {"meta": meta, **buckets}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("各類數量：", meta, "| 略過", skipped)
    print(f"寫出 {OUT}（{OUT.stat().st_size/1e6:.2f} MB）")


if __name__ == "__main__":
    main()
