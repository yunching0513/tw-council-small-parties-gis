#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_winner_photos.py — 為小黨當選者找照片（維基百科 / Wikimedia Commons，CC 授權）
================================================================================
讀 docs/winners.json，對每位當選者查中文維基 REST 摘要：
  - 僅採用 Wikimedia **Commons**（網址含 /commons/）的圖 → CC 授權可再利用；
    略過維基本地非自由圖（/wikipedia/zh/）以尊重著作權。
  - 比對摘要含「議員」或其黨名，避免同名誤認。
下載縮圖到 docs/photos/w{idx}.jpg，並回寫 winners.json 的 photo / wiki 欄位，
attribution 寫到 docs/photo_credits.json。
"""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
from pathlib import Path

DOCS = Path(__file__).parent / "docs"
PHOTOS = DOCS / "photos"
UA = "tw-council-gis/1.0 (civic research; jtl0513@gmail.com)"
REST = "https://zh.wikipedia.org/api/rest_v1/page/summary/"


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def main() -> None:
    PHOTOS.mkdir(parents=True, exist_ok=True)
    winners = json.loads((DOCS / "winners.json").read_text(encoding="utf-8"))
    credits, got = [], 0
    for i, w in enumerate(winners):
        name = w["name"]
        try:
            d = json.loads(get(REST + urllib.parse.quote(name)))
        except Exception:
            continue
        extract = d.get("extract", "") or ""
        # 確認是本人：摘要含「議員」或黨名
        if "議員" not in extract and w["party"] not in extract:
            continue
        thumb = (d.get("thumbnail") or {}).get("source") or ""
        orig = (d.get("originalimage") or {}).get("source") or ""
        src = orig or thumb
        if "/commons/" not in src:   # 僅用 Commons（CC），略過非自由圖
            w["wiki"] = (d.get("content_urls", {}).get("desktop", {}) or {}).get("page")
            continue
        # 用較小的縮圖版（thumb）以節省體積
        img_url = thumb if "/commons/" in thumb else src
        try:
            data = get(img_url)
        except Exception:
            continue
        fn = f"w{i}.jpg"
        (PHOTOS / fn).write_bytes(data)
        w["photo"] = f"photos/{fn}"
        w["wiki"] = (d.get("content_urls", {}).get("desktop", {}) or {}).get("page")
        credits.append({"name": name, "img": img_url, "page": w["wiki"]})
        got += 1
        print(f"  ✓ {name} ← {img_url.split('/')[-1][:40]}")

    (DOCS / "winners.json").write_text(
        json.dumps(winners, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (DOCS / "photo_credits.json").write_text(
        json.dumps(credits, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n取得照片 {got}/{len(winners)}；其餘附維基連結或留名字卡。")


if __name__ == "__main__":
    main()
