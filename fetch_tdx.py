#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_tdx.py — 由 TDX 運輸資料流通服務平臺抓「大眾運輸人流」訊號 → docs/transit_flow.json
=========================================================================================
資料：公車站位（站牌密度＝人流動線）、臺鐵車站、臺鐵各站進出站人次（實際人流）。
來源：TDX https://tdx.transportdata.tw （免費，需註冊金鑰）。

金鑰用法（重要）：本腳本只在「本機建置時」用金鑰向 TDX 取資料、產出**靜態 JSON**；
網頁只讀該 JSON，金鑰不會進版控、不會上到 GitHub Pages。金鑰由環境變數讀取：
  export TDX_CLIENT_ID=你的ClientId
  export TDX_CLIENT_SECRET=你的ClientSecret
  python3 fetch_tdx.py --cities YilanCounty            # 先做宜蘭縣（含宜蘭市）
  python3 fetch_tdx.py --cities YilanCounty Taipei NewTaipei   # 多縣市

TDX 城市代碼（英文）：YilanCounty, Taipei, NewTaipei, Taoyuan, Taichung, Tainan,
  Kaohsiung, HsinchuCity, HsinchuCounty, Keelung, MiaoliCounty, ChanghuaCounty,
  NantouCounty, YunlinCounty, ChiayiCity, ChiayiCounty, PingtungCounty, TaitungCounty,
  HualienCounty, PenghuCounty, KinmenCounty, LienchiangCounty。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DOCS = Path(__file__).parent / "docs"
AUTH = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
BASE = "https://tdx.transportdata.tw/api/basic"
UA = "tw-council-gis/1.0"


def get_token() -> str:
    cid = os.environ.get("TDX_CLIENT_ID")
    sec = os.environ.get("TDX_CLIENT_SECRET")
    if not cid or not sec:
        sys.exit("請先設定環境變數 TDX_CLIENT_ID / TDX_CLIENT_SECRET（見檔頭說明）")
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials", "client_id": cid, "client_secret": sec}).encode()
    req = urllib.request.Request(AUTH, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["access_token"]


def api(path: str, token: str) -> list | dict:
    url = f"{BASE}/{path}"
    url += ("&" if "?" in url else "?") + "%24format=JSON"
    req = urllib.request.Request(url, headers={
        "authorization": f"Bearer {token}", "User-Agent": UA, "Accept-Encoding": "gzip"})
    req.add_header("Accept-Encoding", "identity")  # 避免 gzip 解碼麻煩
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cities", nargs="+", default=["YilanCounty"], help="TDX 英文城市代碼")
    args = ap.parse_args()
    token = get_token()
    print("✓ 取得 TDX token")

    out: dict[str, list] = {"bus": [], "tra": []}

    # 1) 公車站位（站牌密度＝人流動線）
    for city in args.cities:
        try:
            stops = api(f"v2/Bus/Stop/City/{city}", token)
            for s in stops:
                pos = s.get("StopPosition") or {}
                lat, lon = pos.get("PositionLat"), pos.get("PositionLon")
                nm = (s.get("StopName") or {}).get("Zh_tw", "")
                if lat and lon:
                    out["bus"].append([round(lon, 5), round(lat, 5), nm])
            print(f"  公車站位 {city}: {len(stops)}")
        except Exception as e:  # noqa: BLE001
            print(f"  公車站位 {city} 失敗：{e}", file=sys.stderr)

    # 2) 臺鐵車站（全台，前端可自行依縣市篩）
    try:
        tra = api("v3/Rail/TRA/Station", token)
        recs = tra.get("Stations", tra) if isinstance(tra, dict) else tra
        for s in recs:
            pos = s.get("StationPosition") or {}
            lat, lon = pos.get("PositionLat"), pos.get("PositionLon")
            nm = (s.get("StationName") or {}).get("Zh_tw", "")
            if lat and lon:
                out["tra"].append([round(lon, 5), round(lat, 5), nm])
        print(f"  臺鐵車站: {len(out['tra'])}")
    except Exception as e:  # noqa: BLE001
        print(f"  臺鐵車站失敗：{e}", file=sys.stderr)

    # 3) （可選）臺鐵各站進出站人次＝實際人流；端點依 TDX 現況確認後補
    #    例：v3/Rail/TRA/StationOfLine 或歷史運量資料集。

    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "transit_flow.json").write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"寫出 docs/transit_flow.json（公車 {len(out['bus'])}、臺鐵 {len(out['tra'])}）")


if __name__ == "__main__":
    main()
