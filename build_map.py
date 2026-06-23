#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_map.py — 產生網頁地圖所需資料 → docs/
=============================================
1. 簡化全國村里界圖（94MB → 數 MB），只保留 VILLCODE 屬性
   - 首選 mapshaper（npx 自動取用）：拓樸保形簡化 + 輸出 TopoJSON（最小）
   - 後備 純 Python：座標降精度 + 道格拉斯-普克簡化，輸出 GeoJSON
2. 把 data/normalized/village_map.json 包成 docs/data.js（window.VILLAGE_DATA）

用法：
  python3 build_map.py                 # 預設簡化度
  python3 build_map.py --simplify 6    # 自訂 mapshaper 簡化百分比
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
NORM = ROOT / "data" / "normalized"
DOCS = ROOT / "docs"
GEO_SRC = RAW / "cunli_geo_20221118.json"


def have_mapshaper() -> bool:
    if shutil.which("mapshaper"):
        return True
    # 試 npx（會在首次使用時下載）
    try:
        subprocess.run(["npx", "-y", "mapshaper", "--version"],
                       capture_output=True, timeout=120, check=True)
        return True
    except Exception:
        return False


def simplify_mapshaper(pct: int) -> bool:
    out = DOCS / "villages.topojson"
    cmd = (["mapshaper"] if shutil.which("mapshaper") else ["npx", "-y", "mapshaper"]) + [
        str(GEO_SRC),
        "-filter-fields", "VILLCODE",
        "-simplify", f"{pct}%", "keep-shapes",
        "-clean",
        "-o", "format=topojson", "quantization=1e5", str(out),
    ]
    print("  $", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, timeout=900)
    except Exception as e:  # noqa: BLE001
        print("  mapshaper 失敗：", e, file=sys.stderr)
        return False
    print(f"  ✓ {out.name}（{out.stat().st_size/1e6:.1f}MB, TopoJSON）")
    return True


def simplify_python(tol: float, ndigits: int) -> bool:
    """後備：無 mapshaper 時，用座標降精度 + shapely 簡化，輸出 GeoJSON。"""
    try:
        from shapely.geometry import shape, mapping  # noqa: F401
    except ImportError:
        print("  後備需 shapely：pip install shapely", file=sys.stderr)
        return False
    from shapely.geometry import shape, mapping
    geo = json.loads(GEO_SRC.read_text(encoding="utf-8"))

    def round_coords(obj):
        if isinstance(obj, list):
            if obj and isinstance(obj[0], (int, float)):
                return [round(obj[0], ndigits), round(obj[1], ndigits)]
            return [round_coords(x) for x in obj]
        return obj

    feats = []
    for f in geo["features"]:
        try:
            g = shape(f["geometry"]).simplify(tol, preserve_topology=True)
            gm = mapping(g)
            gm["coordinates"] = round_coords(gm["coordinates"])
            feats.append({"type": "Feature",
                          "properties": {"VILLCODE": f["properties"]["VILLCODE"]},
                          "geometry": gm})
        except Exception:
            continue
    out = DOCS / "villages.geojson"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  ✓ {out.name}（{out.stat().st_size/1e6:.1f}MB, GeoJSON, {len(feats)} 村里）")
    return True


def write_data_js() -> None:
    src = NORM / "village_map.json"
    data = src.read_text(encoding="utf-8")
    (DOCS / "data.js").write_text("window.VILLAGE_DATA=" + data + ";\n", encoding="utf-8")
    print(f"  ✓ data.js（{(DOCS/'data.js').stat().st_size/1e6:.1f}MB）")


def build_boundaries() -> None:
    """把村里界溶接成鄉鎮(TOWNCODE)、縣市(COUNTYCODE)界線 → docs/{towns,counties}.topojson"""
    if not shutil.which("mapshaper") and not _has_npx():
        print("  （無 mapshaper，略過行政界生成）")
        return
    base = ["mapshaper"] if shutil.which("mapshaper") else ["npx", "-y", "mapshaper"]
    for field, out in (("TOWNCODE", "towns.topojson"), ("COUNTYCODE", "counties.topojson")):
        cmd = base + [str(GEO_SRC), "-dissolve2", field, "-simplify", "6%", "keep-shapes",
                      "-o", "force", "format=topojson", str(DOCS / out)]
        try:
            subprocess.run(cmd, check=True, timeout=900)
            print(f"  ✓ {out}（{(DOCS/out).stat().st_size/1e6:.2f}MB）")
        except Exception as e:  # noqa: BLE001
            print(f"  界線 {out} 失敗：{e}", file=sys.stderr)


def _has_npx() -> bool:
    try:
        subprocess.run(["npx", "-y", "mapshaper", "--version"],
                       capture_output=True, timeout=120, check=True)
        return True
    except Exception:
        return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simplify", type=int, default=8, help="mapshaper 簡化百分比")
    ap.add_argument("--py-tol", type=float, default=0.0003, help="後備簡化容差(度)")
    args = ap.parse_args()
    DOCS.mkdir(parents=True, exist_ok=True)
    if not GEO_SRC.exists():
        sys.exit("界圖尚未下載：先跑 python3 fetch_data.py")

    print("簡化村里界圖…")
    if have_mapshaper():
        ok = simplify_mapshaper(args.simplify)
        if not ok:
            print("  改用 Python 後備簡化…")
            simplify_python(args.py_tol, 5)
    else:
        print("  未偵測到 mapshaper，改用 Python 後備簡化…")
        simplify_python(args.py_tol, 5)

    print("產生行政界（鄉鎮/縣市 白框用）…")
    build_boundaries()

    print("產生地圖資料…")
    write_data_js()
    print("完成。docs/ 已就緒，可 python3 -m http.server -d docs 8000 預覽。")


if __name__ == "__main__":
    main()
