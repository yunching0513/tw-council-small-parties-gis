#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnose_join.py — 實測三屆村里代碼如何對齊到界圖 VILLCODE（不靠猜）

對齊問題：
  界圖 / 2022(elections)：VILLCODE 11 位，如 67000020033
  2014/2018 cunli.json   ：內部代碼，需經各自 vcode.php 對回 VILLCODE
  vcode.php 左側         ：12 位舊碼，如 630001200001（村里尾碼 4 位）

本腳本：
  1. 載入界圖 → VILLCODE 集合
  2. 解析 vcode.php → (左碼12位, cunli_key)
  3. 對「左碼」試多種轉換，回報與界圖 VILLCODE 的命中率，挑出正解
  4. 順帶檢查 elections 檔名、2018 cunli key 是否本身即 VILLCODE
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def load_villcodes() -> set[str]:
    geo = json.loads((RAW / "cunli_geo_20221118.json").read_text(encoding="utf-8"))
    return {f["properties"]["VILLCODE"] for f in geo["features"]}


def parse_vcode_php(path: Path) -> list[tuple[str, str]]:
    txt = path.read_text(encoding="utf-8", errors="replace")
    # 形如:  630001200001 => '6301200-001',
    return re.findall(r"(\d+)\s*=>\s*'([^']*)'", txt)


# 候選轉換：12位左碼 -> 11位 VILLCODE
TRANSFORMS = {
    "as_is": lambda c: c,
    "drop_idx8": lambda c: c[:8] + c[9:] if len(c) >= 9 else c,        # 移除村里段首位
    "town8+vill3": lambda c: c[:8] + str(int(c[8:])).zfill(3) if len(c) >= 9 and c[8:].isdigit() else c,
    "last11": lambda c: c[-11:],
    "strip_zero_at5": lambda c: (c[:5] + c[6:]) if len(c) >= 6 else c,
}


def test_transforms(pairs: list[tuple[str, str]], villset: set[str], label: str) -> str:
    print(f"\n=== {label}：{len(pairs)} 筆 vcode.php 對照 ===")
    lens = {}
    for c, _ in pairs:
        lens[len(c)] = lens.get(len(c), 0) + 1
    print("  左碼長度分布：", dict(sorted(lens.items())))
    best, best_rate = None, -1.0
    for name, fn in TRANSFORMS.items():
        hit = sum(1 for c, _ in pairs if fn(c) in villset)
        rate = hit / max(1, len(pairs))
        flag = ""
        if rate > best_rate:
            best, best_rate = name, rate
        print(f"  {name:14s} 命中 {hit:5d}/{len(pairs)} = {rate:6.1%}")
    print(f"  → 最佳轉換：{best}（{best_rate:.1%}）")
    # 列幾個未命中範例
    fn = TRANSFORMS[best]
    miss = [(c, fn(c)) for c, _ in pairs if fn(c) not in villset][:5]
    if miss:
        print("  未命中範例（左碼 -> 轉換後）：", miss)
    return best


def main() -> None:
    if not (RAW / "cunli_geo_20221118.json").exists():
        sys.exit("界圖尚未下載完成")
    villset = load_villcodes()
    print(f"界圖 VILLCODE 數：{len(villset)}（範例 {list(villset)[:3]}）")

    # elections 檔名是否即 VILLCODE
    eldir = RAW / "cec_mirror" / "data" / "elections" / "2020-2024"
    if eldir.exists():
        els = [p.stem for p in eldir.glob("*.json")]
        hit = sum(1 for e in els if e in villset)
        print(f"\nelections 檔名 ∈ 界圖：{hit}/{len(els)} = {hit/len(els):.1%}")

    # 2018 cunli key 是否本身即 VILLCODE
    c2018 = json.loads((RAW / "council_2018_cunli.json").read_text(encoding="utf-8"))
    keys18 = list(c2018.keys())
    hit18 = sum(1 for k in keys18 if k in villset)
    print(f"2018 cunli key ∈ 界圖：{hit18}/{len(keys18)} = {hit18/len(keys18):.1%}（範例 {keys18[:3]}）")

    best14 = test_transforms(parse_vcode_php(RAW / "council_2014_vcode.php"), villset, "2014")
    best18 = test_transforms(parse_vcode_php(RAW / "council_2018_vcode.php"), villset, "2018")
    print(f"\n結論：2014 用 {best14}；2018 用 {best18}")


if __name__ == "__main__":
    main()
