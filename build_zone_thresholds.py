#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_zone_thresholds.py — 每個議員選區歷屆「最低當選票數」（當選門檻）→ CSV
=============================================================================
由 zone_rosters.json（各選區候選人得票＋當選註記）計算每選區每屆：
  最低當選票數 = 當選者中票數最低者（最後一席的門檻）
  最高落選票數、差距(margin) = 最低當選 − 最高落選（最後一席多險）
選區標籤：縣市 + 選區代碼(2014/2018 有)或所含鄉鎮市區。

輸出 data/normalized/zone_min_winning.csv
"""
from __future__ import annotations
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
NORM = ROOT / "data" / "normalized"
DOCS = ROOT / "docs"


def load_village_map() -> dict:
    txt = (DOCS / "data.js").read_text(encoding="utf-8")
    return json.loads(txt.split("=", 1)[1].rstrip().rstrip(";"))


def main() -> None:
    rosters = json.loads((DOCS / "zone_rosters.json").read_text(encoding="utf-8"))
    R, V = rosters["r"], rosters["v"]
    vm = load_village_map()

    # zid -> 該選區的村里清單（取縣市與鄉鎮）
    zone_vills: dict[tuple, list] = defaultdict(list)
    for vc, ys in V.items():
        for yr, zid in ys.items():
            zone_vills[(yr, str(zid))].append(vc)

    # 2014/2018 選區代碼（zid -> zonecode），由 councilors_long 取
    zid_zonecode: dict[tuple, str] = {}
    for r in csv.DictReader(open(NORM / "councilors_long.csv", encoding="utf-8-sig")):
        if r["zone"] and r["villcode"] in V and r["year"] in V[r["villcode"]]:
            zid_zonecode[(r["year"], str(V[r["villcode"]][r["year"]]))] = r["zone"]

    rows = []
    for yr in ("2014", "2018", "2022"):
        for zid, cands in R.get(yr, {}).items():
            elected = [c for c in cands if c[4] == 1]
            if not elected:
                continue
            losers = [c for c in cands if c[4] == 0]
            min_win = min(elected, key=lambda c: c[3])
            max_lose = max(losers, key=lambda c: c[3]) if losers else None
            vills = zone_vills.get((yr, zid), [])
            county = next((vm[v]["c"] for v in vills if v in vm), "")
            towns = sorted({vm[v]["t"] for v in vills if v in vm})
            code = zid_zonecode.get((yr, zid), "")
            znum = code.split("-")[1] if "-" in code else ""
            label = (county + f"第{znum}選區") if znum else (county + " " + "・".join(towns[:4]) + ("…" if len(towns) > 4 else ""))
            rows.append({
                "year": yr, "county": county, "zone_label": label, "zone_code": code,
                "seats": len(elected),
                "min_win_votes": min_win[3], "min_win_cand": min_win[0], "min_win_party": min_win[1],
                "max_lose_votes": max_lose[3] if max_lose else "",
                "max_lose_cand": max_lose[0] if max_lose else "",
                "margin": (min_win[3] - max_lose[3]) if max_lose else "",
                "n_cand": len(cands),
            })

    rows.sort(key=lambda r: (r["county"], r["zone_label"], r["year"]))
    cols = ["year", "county", "zone_label", "zone_code", "seats", "min_win_votes",
            "min_win_cand", "min_win_party", "max_lose_votes", "max_lose_cand", "margin", "n_cand"]
    out = NORM / "zone_min_winning.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"寫出 {out}（{len(rows)} 列 = 年×選區）")
    # 摘要
    by_year = defaultdict(list)
    for r in rows:
        by_year[r["year"]].append(r["min_win_votes"])
    for yr in ("2014", "2018", "2022"):
        vs = sorted(by_year[yr])
        if vs:
            print(f"  {yr}: {len(vs)} 選區，最低當選票數 中位數 {vs[len(vs)//2]}，"
                  f"最小 {vs[0]}，最大 {vs[-1]}")


if __name__ == "__main__":
    main()
