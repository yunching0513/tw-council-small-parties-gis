#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_data.py — 從 g0v「中選會選舉資料庫鏡像」抓取村里層級議員選舉原始資料
================================================================================
資料來源（CC BY 4.0，作者 Finjon Kiang / 江明宗，整理自中央選舉委員會）：
  https://github.com/kiang/db.cec.gov.tw       選舉得票（村里 × 候選人）
  https://github.com/kiang/taiwan_basecode      村里界圖 GeoJSON

下載內容（全部存到 data/raw/，可重複執行、已存在者略過）：
  1. data/raw/elections_2020-2024/   ← 7,747 個村里檔，每檔含 2022議員(全候選人,含落選)
                                         + 2020不分區 + 2024不分區 + 2024總統 政黨票
     （用 git sparse-checkout 只抓這層 ~27MB，跳過 repo 其餘 800MB+ 投開票所大檔）
  2. data/raw/council_2014_cunli.json  ← 2014 議員 村里 × 候選人（含政黨/落選）17.7MB
  3. data/raw/council_2018_cunli.json  ← 2018 議員 村里 × 候選人（含政黨/落選）19.4MB
  4. data/raw/cunli_geo_20221118.json  ← 全國村里界圖（geojson VILLCODE 為 key）94MB

用法：
  python3 fetch_data.py            # 全抓
  python3 fetch_data.py --refresh  # 強制重抓
"""
from __future__ import annotations
import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

RAW = Path(__file__).parent / "data" / "raw"
CEC_RAW = "https://raw.githubusercontent.com/kiang/db.cec.gov.tw/master/"
BASECODE_RAW = "https://raw.githubusercontent.com/kiang/taiwan_basecode/master/"

# 直接 curl 的單一檔： (輸出檔名, 來源 URL)
BIG_FILES = [
    ("council_2014_cunli.json", CEC_RAW + "data/council/2014/cunli.json"),
    ("council_2018_cunli.json", CEC_RAW + "data/council/2018/cunli.json"),
    # 村里代碼橋接：vcode.php 把 geojson VILLCODE 對應到 cunli.json 的內部代碼，
    # zone.php 把內部代碼對應到鄉鎮市區名（2014/2018 cunli.json 本身無村里名）。
    ("council_2014_vcode.php", CEC_RAW + "data/council/2014/vcode.php"),
    ("council_2014_zone.php", CEC_RAW + "data/council/2014/zone.php"),
    ("council_2018_vcode.php", CEC_RAW + "data/council/2018/vcode.php"),
    ("council_2018_zone.php", CEC_RAW + "data/council/2018/zone.php"),
    # 全國村里界圖（geojson VILLCODE 為 key）
    ("cunli_geo_20221118.json", BASECODE_RAW + "cunli/geo/20221118.json"),
]

# sparse-checkout 抓的目錄
MIRROR_DIR = RAW / "cec_mirror"
SPARSE_PATH = "data/elections/2020-2024"
ELECTIONS_OUT = RAW / "elections_2020-2024"  # 完成後指向 mirror 內的目錄


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("  $", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def download(url: str, dest: Path, refresh: bool) -> None:
    if dest.exists() and not refresh and dest.stat().st_size > 0:
        print(f"  ✓ 已存在，略過 {dest.name} ({dest.stat().st_size/1e6:.1f}MB)")
        return
    print(f"  ↓ 下載 {dest.name}  <- {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "tw-council-gis/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        total = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    print(f"    完成 {total/1e6:.1f}MB")


def fetch_elections_dir(refresh: bool) -> None:
    """用 git partial+sparse clone 只抓 elections/2020-2024（~27MB / 7747 檔）。"""
    target = MIRROR_DIR / SPARSE_PATH
    if target.exists() and any(target.iterdir()) and not refresh:
        n = sum(1 for _ in target.glob("*.json"))
        print(f"  ✓ 已存在 elections/2020-2024（{n} 檔），略過")
        return
    if refresh and MIRROR_DIR.exists():
        run(["rm", "-rf", str(MIRROR_DIR)])
    if not MIRROR_DIR.exists():
        run(["git", "clone", "--filter=blob:none", "--no-checkout", "--depth", "1",
             "https://github.com/kiang/db.cec.gov.tw", str(MIRROR_DIR)])
        run(["git", "sparse-checkout", "init", "--cone"], cwd=MIRROR_DIR)
        run(["git", "sparse-checkout", "set", SPARSE_PATH], cwd=MIRROR_DIR)
    run(["git", "checkout"], cwd=MIRROR_DIR)
    n = sum(1 for _ in target.glob("*.json"))
    print(f"  完成 elections/2020-2024：{n} 檔")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="強制重新下載")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    print("== 1) elections/2020-2024（2022議員 + 政黨票）==")
    fetch_elections_dir(args.refresh)

    print("\n== 2) 議員村里得票大檔 + 村里界圖 ==")
    for name, url in BIG_FILES:
        try:
            download(url, RAW / name, args.refresh)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ 失敗 {name}: {e}", file=sys.stderr)

    print("\n完成。原始資料位於：", RAW)
    print("elections 目錄：", MIRROR_DIR / SPARSE_PATH)


if __name__ == "__main__":
    main()
