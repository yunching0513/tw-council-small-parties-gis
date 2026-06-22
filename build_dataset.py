#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_dataset.py — 把原始資料正規化成「村里級議員選舉」分析資料集
================================================================
讀 data/raw/（fetch_data.py 下載），輸出 data/normalized/：

  councilors_long.csv  最細表：每列 = (屆, 村里, 候選人) 得票
                       欄位含 政黨(正規化)/分組/是否小黨/是否焦點/現任/當選/得票
  village_metrics.csv  每列 = (屆, 村里) 彙總：總票、各黨組得票與得票率、
                       領先黨、競爭差距、小黨候選人數；2022 另含政黨票(白地)欄位
  parties_summary.csv  每列 = (屆, 縣市, 政黨) 概況：候選人數、得票、當選席次
  village_map.json      地圖用精簡資料（以 VILLCODE 為 key，含三屆 + 政黨票）

三屆村里代碼對齊：
  2022  elections 檔名即界圖 VILLCODE
  2014/2018  cunli.json 內部碼 → 經 vcode.php → 轉換成 VILLCODE（見 villcode_map）
"""
from __future__ import annotations
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parties import (norm_party, party_group, is_small, is_focus,  # noqa: E402
                     FOCUS, FOCUS_CODE, SMALL_PARTIES)

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "normalized"
ELDIR = RAW / "cec_mirror" / "data" / "elections" / "2020-2024"

# vcode.php 12 位舊碼 → 11 位 VILLCODE：移除村里段首位（drop_idx8）。
# 經 diagnose_join.py 實測為最佳轉換（2014 命中 96.8%、2018 99.1%）。
def code_to_villcode(c: str) -> str:
    return c[:8] + c[9:] if len(c) >= 9 else c


# ---------- 載入界圖（VILLCODE → 縣市/鄉鎮/村里名）----------
def load_geo() -> dict[str, dict]:
    geo = json.loads((RAW / "cunli_geo_20221118.json").read_text(encoding="utf-8"))
    out = {}
    for f in geo["features"]:
        p = f["properties"]
        out[p["VILLCODE"]] = {"county": p["COUNTYNAME"], "town": p["TOWNNAME"],
                              "village": p["VILLNAME"]}
    return out


# ---------- vcode.php → {cunli_key: VILLCODE} ----------
def load_vcode_map(php_path: Path, villset: set[str]) -> dict[str, str]:
    txt = php_path.read_text(encoding="utf-8", errors="replace")
    out, miss = {}, 0
    for left, cunli_key in re.findall(r"(\d+)\s*=>\s*'([^']*)'", txt):
        vc = code_to_villcode(left)
        if vc in villset:
            out[cunli_key] = vc
        else:
            miss += 1
    if miss:
        print(f"    note: {php_path.name} 有 {miss} 筆轉換後不在界圖（多為外島/合併/改制）")
    return out


# ---------- 候選人記錄 ----------
def rec(year, villcode, geo, zone, no, name, party, current, elected, votes):
    np_ = norm_party(party)
    return {
        "year": year, "villcode": villcode,
        "county": geo.get("county", ""), "town": geo.get("town", ""),
        "village": geo.get("village", ""), "zone": zone,
        "cand_no": no, "cand_name": name, "party": np_,
        "party_group": party_group(np_),
        "is_small": int(is_small(np_)), "is_focus": int(is_focus(np_)),
        "current": int(current), "elected": int(elected), "votes": int(votes or 0),
    }


def parse_cunli_year(year: int, cunli_path: Path, vmap: dict[str, str],
                     villset: set[str], geo: dict) -> list[dict]:
    """2014 / 2018：{cunli_key: {candno: {code,name,party,current,win,vote}}}
    代碼解析：2018 的 key 本身即 VILLCODE（直接命中）；2014 為 dash 舊碼，退回 vmap。"""
    data = json.loads(cunli_path.read_text(encoding="utf-8"))
    recs, no_vc = [], 0
    for cunli_key, cands in data.items():
        vc = cunli_key if cunli_key in villset else vmap.get(cunli_key)
        if not vc:
            no_vc += 1
            continue
        g = geo.get(vc, {})
        for no, c in cands.items():
            recs.append(rec(year, vc, g, c.get("code", ""), no, c.get("name", ""),
                            c.get("party", ""), c.get("current") == "Y",
                            str(c.get("win", "")).strip() == "*", c.get("vote", 0)))
    print(f"  {year}: {len(recs)} 候選人列；{no_vc} 個村里碼無法對齊 VILLCODE")
    return recs


def parse_2022(geo: dict) -> tuple[list[dict], dict[str, dict]]:
    """2022：elections/2020-2024/{VILLCODE}.json → 議員候選人 + 政黨票"""
    recs = []
    partylist = {}  # villcode -> {"2020":{party:votes}, "2024":{...}}
    files = sorted(ELDIR.glob("*.json"))
    for fp in files:
        vc = fp.stem
        d = json.loads(fp.read_text(encoding="utf-8"))
        g = geo.get(vc, {"county": d.get("county", ""), "town": d.get("town", ""),
                         "village": d.get("name", "")})
        for c in d.get("2022議員", []):
            recs.append(rec(2022, vc, g, "", c.get("no", ""), c.get("name", ""),
                            c.get("party", ""), False, bool(c.get("elected")),
                            c.get("votes", 0)))
        pl = {}
        for label, key in (("2020不分區", "2020"), ("2024不分區", "2024")):
            if isinstance(d.get(label), dict):
                pl[key] = d[label]
        if pl:
            partylist[vc] = pl
    print(f"  2022: {len(recs)} 候選人列（來自 {len(files)} 個村里檔）")
    return recs, partylist


# ---------- 村里彙總 ----------
def aggregate(recs: list[dict]) -> dict[tuple, dict]:
    """key=(year, villcode) → 彙總指標"""
    agg: dict[tuple, dict] = {}
    for r in recs:
        k = (r["year"], r["villcode"])
        a = agg.get(k)
        if a is None:
            a = agg[k] = {
                "year": r["year"], "villcode": r["villcode"], "county": r["county"],
                "town": r["town"], "village": r["village"],
                "total": 0, "kmt": 0, "dpp": 0, "tpp": 0, "small": 0, "focus": 0,
                "indep": 0, "other": 0,
                "npp": 0, "tsp": 0, "obasan": 0, "green": 0, "sdp": 0,
                "small_cand": 0, "focus_cand": 0,
                "_byparty": defaultdict(int),
            }
        v = r["votes"]
        a["total"] += v
        a["_byparty"][r["party"]] += v
        grp = r["party_group"]
        if grp == "kmt": a["kmt"] += v
        elif grp == "dpp": a["dpp"] += v
        elif grp == "tpp": a["tpp"] += v
        elif grp == "independent": a["indep"] += v
        elif grp == "other": a["other"] += v
        if r["is_small"]:
            a["small"] += v
            a["small_cand"] += 1
        if r["is_focus"]:
            a["focus"] += v
            a["focus_cand"] += 1
            a[FOCUS_CODE.get(r["party"], "_")] = a.get(FOCUS_CODE.get(r["party"], "_"), 0) + v
    # 領先黨 / 競爭差距
    for a in agg.values():
        bp = sorted(a.pop("_byparty").items(), key=lambda kv: -kv[1])
        a["lead_party"] = bp[0][0] if bp else ""
        tot = a["total"] or 1
        a["lead_share"] = round(100 * bp[0][1] / tot, 2) if bp else 0
        a["second_share"] = round(100 * bp[1][1] / tot, 2) if len(bp) > 1 else 0
        a["margin"] = round(a["lead_share"] - a["second_share"], 2)
    return agg


def pl_small_share(pl_year: dict) -> dict:
    """政黨票某年 {party:votes} → 小黨/焦點各自得票率(%)"""
    if not pl_year:
        return {}
    norm = defaultdict(int)
    for p, v in pl_year.items():
        norm[norm_party(p)] += int(v or 0)
    tot = sum(norm.values()) or 1
    out = {"pl_total": tot,
           "pl_small": round(100 * sum(v for p, v in norm.items() if p in SMALL_PARTIES) / tot, 2),
           "pl_focus": round(100 * sum(v for p, v in norm.items() if p in FOCUS) / tot, 2)}
    for p, code in FOCUS_CODE.items():
        out[f"pl_{code}"] = round(100 * norm.get(p, 0) / tot, 2)
    return out


# ---------- 輸出 ----------
def write_long(recs: list[dict]) -> None:
    cols = ["year", "villcode", "county", "town", "village", "zone", "cand_no",
            "cand_name", "party", "party_group", "is_small", "is_focus",
            "current", "elected", "votes"]
    with open(OUT / "councilors_long.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(recs)
    print(f"  寫出 councilors_long.csv（{len(recs)} 列）")


def write_village_metrics(agg: dict, partylist: dict) -> None:
    cols = ["year", "villcode", "county", "town", "village", "total",
            "kmt", "dpp", "tpp", "small", "focus", "indep", "other",
            "npp", "tsp", "obasan", "small_cand", "focus_cand",
            "small_share", "focus_share", "lead_party", "lead_share", "margin",
            "pl_small", "pl_focus", "white_gap"]
    rows = []
    for (year, vc), a in sorted(agg.items()):
        tot = a["total"] or 1
        small_share = round(100 * a["small"] / tot, 2)
        row = {k: a.get(k, "") for k in cols}
        row.update(year=year, villcode=vc, small_share=small_share,
                   focus_share=round(100 * a["focus"] / tot, 2))
        # 白地：政黨票小黨支持率 − 議員小黨得票率（僅 2022 有政黨票）
        if year == 2022 and vc in partylist:
            pl = pl_small_share(partylist[vc].get("2024") or partylist[vc].get("2020"))
            row["pl_small"] = pl.get("pl_small", "")
            row["pl_focus"] = pl.get("pl_focus", "")
            if pl.get("pl_small") != "":
                row["white_gap"] = round(pl["pl_small"] - small_share, 2)
        rows.append(row)
    with open(OUT / "village_metrics.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"  寫出 village_metrics.csv（{len(rows)} 列）")


def write_parties_summary(recs: list[dict]) -> None:
    # councilors_long 每位候選人在所屬選區的「每個里」各一列，故須先去重到
    # 「候選人」層級（同一人=同年+同縣市+同姓名+同黨）再彙總，否則人數/席次會被
    # 乘上里數而灌水。得票則為該候選人跨里加總（=其選區總得票）。
    cand: dict[tuple, dict] = {}
    for r in recs:
        k = (r["year"], r["county"], r["cand_name"], r["party"])
        s = cand.get(k)
        if s is None:
            s = cand[k] = {"votes": 0, "elected": 0}
        s["votes"] += r["votes"]
        s["elected"] = max(s["elected"], r["elected"])
    agg = defaultdict(lambda: {"cands": 0, "votes": 0, "seats": 0})
    for (year, county, _name, party), s in cand.items():
        a = agg[(year, county, party)]
        a["cands"] += 1
        a["votes"] += s["votes"]
        a["seats"] += s["elected"]
    with open(OUT / "parties_summary.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["year", "county", "party", "is_small", "is_focus",
                    "candidates", "votes", "seats_won"])
        for (year, county, party), a in sorted(agg.items()):
            w.writerow([year, county, party, int(is_small(party)), int(is_focus(party)),
                        a["cands"], a["votes"], a["seats"]])
    print(f"  寫出 parties_summary.csv（{len(agg)} 列）")


def write_map_json(agg: dict, partylist: dict, geo: dict) -> None:
    """地圖用：{villcode: {c,t,v, y:{2014:{...},2018,2022}, pl:{2020,2024}}}"""
    out: dict[str, dict] = {}
    for (year, vc), a in agg.items():
        node = out.setdefault(vc, {"c": a["county"], "t": a["town"], "v": a["village"], "y": {}})
        tot = a["total"] or 1
        node["y"][str(year)] = {
            "tot": a["total"],
            "sm": a["small"], "fo": a["focus"],
            "npp": a["npp"], "tsp": a["tsp"], "ob": a["obasan"],
            "green": a["green"], "sdp": a["sdp"],
            "kmt": a["kmt"], "dpp": a["dpp"], "tpp": a["tpp"],
            "ind": a["indep"], "oth": a["other"],
            "smS": round(100 * a["small"] / tot, 1),
            "foS": round(100 * a["focus"] / tot, 1),
            "lead": party_group(a["lead_party"]), "leadS": a["lead_share"],
            "scand": a["small_cand"],
        }
    for vc, pl in partylist.items():
        node = out.setdefault(vc, {"c": geo.get(vc, {}).get("county", ""),
                                   "t": geo.get(vc, {}).get("town", ""),
                                   "v": geo.get(vc, {}).get("village", ""), "y": {}})
        node["pl"] = {}
        for yr in ("2020", "2024"):
            if yr in pl:
                s = pl_small_share(pl[yr])
                node["pl"][yr] = {"sm": s.get("pl_small", 0), "fo": s.get("pl_focus", 0),
                                  "npp": s.get("pl_npp", 0), "tsp": s.get("pl_tsp", 0),
                                  "ob": s.get("pl_obasan", 0)}
    (OUT / "village_map.json").write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  寫出 village_map.json（{len(out)} 個村里）")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("載入界圖…")
    geo = load_geo()
    villset = set(geo)
    print(f"  界圖村里數：{len(villset)}")

    print("對齊村里代碼…")
    vmap14 = load_vcode_map(RAW / "council_2014_vcode.php", villset)
    vmap18 = load_vcode_map(RAW / "council_2018_vcode.php", villset)

    print("解析三屆議員資料…")
    recs = []
    recs += parse_cunli_year(2014, RAW / "council_2014_cunli.json", vmap14, villset, geo)
    recs += parse_cunli_year(2018, RAW / "council_2018_cunli.json", vmap18, villset, geo)
    r22, partylist = parse_2022(geo)
    recs += r22

    print("彙總村里指標…")
    agg = aggregate(recs)

    print("輸出…")
    write_long(recs)
    write_village_metrics(agg, partylist)
    write_parties_summary(recs)
    write_map_json(agg, partylist, geo)
    print("完成。")


if __name__ == "__main__":
    main()
