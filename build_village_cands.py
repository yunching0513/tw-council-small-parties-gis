#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_village_cands.py — 各選區參選人名單（全選區得票）→ docs/zone_rosters.json
==============================================================================
「選區參選人」在同選區的每個里都相同，故以「候選人名單簽章」辨識選區、只存一次，
得票彙總為全選區總票（比單一里得票更符合『選區參選人』語意）。

輸出 docs/zone_rosters.json：
  {"r": {"2014":{zid:[[姓名,政黨,分組碼,全選區得票,當選0/1],...]}, "2018":{...}, "2022":{...}},
   "v": {villcode:{"2014":zid,"2018":zid,"2022":zid}}}
每選區名單依得票由高到低排序；zid 為各年度選區序號。
"""
from __future__ import annotations
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parties import party_group  # noqa: E402

NORM = Path(__file__).parent / "data" / "normalized"
DOCS = Path(__file__).parent / "docs"
PG_SHORT = {"時代力量": "npp", "台灣基進": "tsp", "綠黨": "green",
            "社會民主黨": "sdp", "小民參政歐巴桑聯盟": "ob"}


def pg_of(p): return PG_SHORT.get(p, party_group(p))


def main() -> None:
    # (year, villcode) -> list[(name, party, votes, elected)]；county per villcode
    vc_cands: dict[tuple, list] = defaultdict(list)
    vc_county: dict[str, str] = {}
    for r in csv.DictReader(open(NORM / "councilors_long.csv", encoding="utf-8-sig")):
        vc_cands[(r["year"], r["villcode"])].append(
            (r["cand_name"], r["party"], int(r["votes"] or 0), int(r["elected"])))
        vc_county[r["villcode"]] = r["county"]

    sig_to_zid: dict[tuple, int] = {}
    year_counter: dict[str, int] = defaultdict(int)
    vill_zone: dict[str, dict] = defaultdict(dict)
    # (year, zid) -> {name: [party, pg, votes, elected]}
    zr: dict[tuple, dict] = defaultdict(dict)

    for (year, vc), cands in vc_cands.items():
        sig = (year, vc_county.get(vc, ""), tuple(sorted(c[0] for c in cands)))
        zid = sig_to_zid.get(sig)
        if zid is None:
            zid = sig_to_zid[sig] = year_counter[year]
            year_counter[year] += 1
        vill_zone[vc][year] = zid
        bucket = zr[(year, zid)]
        for name, party, votes, elected in cands:
            b = bucket.get(name)
            if b is None:
                b = bucket[name] = [party, pg_of(party), 0, 0]
            b[2] += votes
            b[3] = max(b[3], elected)

    rosters: dict[str, dict] = {"2014": {}, "2018": {}, "2022": {}}
    for (year, zid), bucket in zr.items():
        lst = [[name, b[0], b[1], b[2], b[3]] for name, b in bucket.items()]
        lst.sort(key=lambda x: -x[3])
        rosters[year][str(zid)] = lst

    out = {"r": rosters, "v": vill_zone}
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "zone_rosters.json").write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sz = (DOCS / "zone_rosters.json").stat().st_size / 1e6
    nz = sum(len(v) for v in rosters.values())
    print(f"選區數（年×選區）{nz}、村里 {len(vill_zone)}；寫出 zone_rosters.json（{sz:.2f} MB）")


if __name__ == "__main__":
    main()
