#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_pollstations.py — 2022 區域議員「投開票所」下鑽資料 → docs/pollstations.json
================================================================================
由 data/raw/votedata.zip（中選會選舉資料庫，fetch_votedata.py 下載）的
2022-111年地方公職人員選舉 / T1（議員區域）/ city(縣市議員)+prv(直轄市議員) 解析，
彙總成「每村里 → 各投開票所之總票與小黨得票率」，供地圖點擊村里時下鑽顯示。

檔案（每資料夾，UTF-8 內容；zip 檔名為 Big5/cp437）：
  elbase.csv  prv,city,area,dept,li,名稱     行政區/村里碼→名
  elcand.csv  prv,city,area,...,號次,姓名,政黨碼,...  候選人（選區×號次→政黨）
  elpaty.csv  政黨碼,政黨名
  elctks.csv  prv,city,area,dept,li,投開票所,號次,得票,得票率,當選

對應 VILLCODE：以 (縣市,鄉鎮,村里) 名稱對 village_map.json（界圖名稱）。

輸出 docs/pollstations.json：
  {villcode: {"n":"村里名","p":[[投開票所號, 總票, 小黨得票率%], ...]}}
"""
from __future__ import annotations
import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parties import norm_party, is_small  # noqa: E402

ROOT = Path(__file__).parent
ZIP = ROOT / "data" / "raw" / "votedata.zip"
NORM = ROOT / "data" / "normalized"
DOCS = ROOT / "docs"
ELECTION = "2022-111年地方公職人員選舉"


def b5(zi: zipfile.ZipInfo) -> str:
    try:
        return zi.filename.encode("cp437").decode("big5")
    except Exception:
        return zi.filename


def tw(s: str) -> str:
    return (s or "").strip().replace("臺", "台")


def load_villcode_index() -> dict[tuple, str]:
    """(縣市,鄉鎮,村里) 正規化名 → VILLCODE，來自 village_map.json。"""
    vm = json.loads((DOCS / "data.js").read_text(encoding="utf-8")
                    .split("=", 1)[1].rstrip().rstrip(";"))
    idx = {}
    for vc, n in vm.items():
        idx[(tw(n.get("c", "")), tw(n.get("t", "")), tw(n.get("v", "")))] = vc
    return idx


def read_csv(z: zipfile.ZipFile, nm: dict, suffix: str) -> list[list[str]]:
    key = next((d for d in nm if d.endswith(suffix)), None)
    if not key:
        return []
    return list(csv.reader(io.StringIO(z.read(nm[key]).decode("utf-8", "replace"))))


def process_folder(z, nm, sub: str, parties: dict,
                   poll_acc: dict) -> None:
    """sub = 'T1/city' 或 'T1/prv'。累積 poll_acc[(county,town,vill,poll)] = [total, small]."""
    base = read_csv(z, nm, f"{ELECTION}/{sub}/elbase.csv")
    cand = read_csv(z, nm, f"{ELECTION}/{sub}/elcand.csv")
    ctks = read_csv(z, nm, f"{ELECTION}/{sub}/elctks.csv")
    # 名稱對照
    name = {tuple(r[:5]): r[5] for r in base if len(r) >= 6}

    def county_of(p, c): return name.get((p, c, "00", "000", "0000"), "")
    def town_of(p, c, a, d): return name.get((p, c, a, d, "0000"), "")

    # 候選人政黨：key=(prv,city,area=選區,號次) → 是否小黨
    cand_small = {}
    for r in cand:
        if len(r) < 8:
            continue
        prv, city, area, _dept, _li, no = r[0], r[1], r[2], r[3], r[4], r[5]
        pname = parties.get(r[7], "")
        cand_small[(prv, city, area, no)] = is_small(pname)

    rows = 0
    for r in ctks:
        if len(r) < 8 or r[4] == "0000" or r[5] == "0000":
            continue  # 只取投開票所層級（村里、投開票所皆非 0）
        prv, city, area, dept, li, poll, no = r[:7]
        try:
            votes = int(r[7])
        except ValueError:
            continue
        county = county_of(prv, city)
        town = town_of(prv, city, area, dept)
        vill = name.get((prv, city, area, dept, li), "")
        if not (county and vill):
            continue
        key = (tw(county), tw(town), tw(vill), poll)
        acc = poll_acc[key]
        acc[0] += votes
        if cand_small.get((prv, city, area, no)):
            acc[1] += votes
        rows += 1
    print(f"  {sub}: 投開票所得票列 {rows}")


def main() -> None:
    if not ZIP.exists():
        sys.exit("缺 votedata.zip：先跑 python3 fetch_votedata.py")
    z = zipfile.ZipFile(ZIP)
    nm = {b5(zi): zi.filename for zi in z.infolist()}

    print("載入 VILLCODE 名稱索引…")
    vidx = load_villcode_index()
    print(f"  界圖村里名索引：{len(vidx)}")

    poll_acc: dict[tuple, list] = defaultdict(lambda: [0, 0])
    for sub in ("T1/city", "T1/prv"):
        parties = {r[0]: norm_party(r[1]) for r in read_csv(z, nm, f"{ELECTION}/{sub}/elpaty.csv") if len(r) >= 2}
        print(f"解析 {sub}（政黨 {len(parties)}）…")
        process_folder(z, nm, sub, parties, poll_acc)

    # 彙總到村里 → VILLCODE
    out: dict[str, dict] = {}
    miss = set()
    for (county, town, vill, poll), (total, small) in poll_acc.items():
        vc = vidx.get((county, town, vill))
        if not vc:
            miss.add((county, town, vill))
            continue
        node = out.setdefault(vc, {"n": vill, "p": []})
        pct = round(100 * small / total, 1) if total else 0
        node["p"].append([poll, total, pct])
    for node in out.values():
        node["p"].sort(key=lambda x: x[0])

    NORM.mkdir(parents=True, exist_ok=True)
    (DOCS / "pollstations.json").write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    npolls = sum(len(n["p"]) for n in out.values())
    print(f"\n村里數 {len(out)}、投開票所數 {npolls}；未對到村里 {len(miss)} 個")
    if miss:
        print("  未對到範例：", list(miss)[:6])
    print(f"寫出 docs/pollstations.json（{(DOCS/'pollstations.json').stat().st_size/1e6:.2f} MB）")


if __name__ == "__main__":
    main()
