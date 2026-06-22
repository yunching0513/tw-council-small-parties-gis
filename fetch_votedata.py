#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_votedata.py — 下載中選會「選舉資料庫」votedata.zip（投開票所層級明細）並檢視結構
=====================================================================================
來源：https://data.cec.gov.tw/選舉資料庫/votedata.zip （約 110MB，Big5 檔名/內容）
這是投開票所（每一投開票所 × 候選人得票）的官方資料，供「村里→投開票所」下鑽用。

用法：
  python3 fetch_votedata.py            # 下載並列出結構（不全解壓）
  python3 fetch_votedata.py --list 議員 # 過濾列出含「議員」的項目
"""
from __future__ import annotations
import argparse
import sys
import urllib.request
import zipfile
from pathlib import Path

RAW = Path(__file__).parent / "data" / "raw"
ZIP = RAW / "votedata.zip"
URL = "https://data.cec.gov.tw/%E9%81%B8%E8%88%89%E8%B3%87%E6%96%99%E5%BA%AB/votedata.zip"
UA = "tw-council-gis/1.0 (civic research)"


def big5name(zi: zipfile.ZipInfo) -> str:
    """zip 內 Big5 檔名以 cp437 存放，轉回 Big5。"""
    try:
        return zi.filename.encode("cp437").decode("big5")
    except Exception:
        return zi.filename


def download() -> None:
    if ZIP.exists() and ZIP.stat().st_size > 1_000_000:
        print(f"✓ 已存在 {ZIP.name}（{ZIP.stat().st_size/1e6:.0f}MB），略過下載")
        return
    RAW.mkdir(parents=True, exist_ok=True)
    print("下載 votedata.zip（約 110MB）…")
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=600) as r, open(ZIP, "wb") as f:
        total = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk); total += len(chunk)
    print(f"完成 {total/1e6:.0f}MB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", default="", help="只列出含此關鍵字的項目")
    args = ap.parse_args()
    download()
    print("\n=== 檢視 zip 結構（Big5 解碼）===")
    with zipfile.ZipFile(ZIP) as z:
        names = [big5name(zi) for zi in z.infolist()]
    print("總項目數：", len(names))
    # 頂層資料夾統計
    tops = {}
    for n in names:
        top = n.split("/")[0]
        tops[top] = tops.get(top, 0) + 1
    print("\n頂層項目（前 40）：")
    for t, c in sorted(tops.items())[:40]:
        print(f"  {c:5d}  {t}")
    if args.list:
        print(f"\n含「{args.list}」的項目（前 30）：")
        for n in [x for x in names if args.list in x][:30]:
            print("  ", n)


if __name__ == "__main__":
    main()
