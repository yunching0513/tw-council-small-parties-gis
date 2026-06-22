# 進擊的小黨：量化策略 — 歷年地方議員選舉村里級 GIS

為協助小黨（時代力量、台灣基進、小民參政歐巴桑聯盟等）規劃 2026 地方選舉佈局，
彙整 **2014 / 2018 / 2022 三屆九合一「縣市議員 / 直轄市議員」選舉**結果，
**細緻到村里層級**（含落選候選人、政黨別），並做成互動式 GIS 地圖。

## 四個分析視角（地圖圖層）

1. **小黨得票熱區** — 每個里把多少比例的票投給小黨議員候選人，找出既有票倉。
2. **全候選人競爭格局** — 每個里藍/綠/白/小黨/無黨的得票結構與領先黨。
3. **跨屆成長趨勢** — 小黨得票率 2014→2018→2022 在各里的消長。
4. **白地潛力** — 小黨「沒派」議員候選人、但政黨票（不分區）支持度高的里，
   即「有需求、無供給」的插旗潛力區。

## 資料來源

| 內容 | 來源 | 授權 |
|---|---|---|
| 村里 × 候選人得票（2014/2018/2022 議員） | [kiang/db.cec.gov.tw](https://github.com/kiang/db.cec.gov.tw)（整理自中選會） | CC BY 4.0 |
| 政黨票（2020/2024 不分區立委、2024 總統） | 同上 `data/elections/2020-2024/` | CC BY 4.0 |
| 全國村里界圖 GeoJSON | [kiang/taiwan_basecode](https://github.com/kiang/taiwan_basecode) | CC BY 4.0 |

> 原始資料屬中央選舉委員會，經 Finjon Kiang（江明宗 / g0v）整理。再利用請標註來源。

## 粒度

- **主圖：村里層級**（涵蓋全台 22 縣市約 7,700 里，三屆齊全）。
- **下鑽：投開票所層級**（規劃中；中選會原始投開票所明細不在上述鏡像，需另抓，
  見 `docs/投開票所下鑽.md`）。

## 流程

```bash
# 1) 下載原始資料到 data/raw/（git sparse-checkout + curl，約 130MB）
python3 fetch_data.py

# 2) ETL → 正規化 CSV + 村里指標
python3 build_dataset.py

# 3) 簡化村里界圖 + 產生網頁地圖資料 → docs/
#    （需 Node 的 mapshaper：npx 會自動取用）
python3 build_map.py

# 4) 本機預覽
python3 -m http.server -d docs 8000   # 開 http://localhost:8000
```

## 輸出

```
data/normalized/
├── councilors_long.csv   # 最細：每列 = (屆,里,候選人) 得票，含政黨/落選/現任
├── village_metrics.csv   # 每列 = (屆,里) 彙總指標，四圖層所需
└── parties_summary.csv   # 各屆各黨在議員選舉的縣市別席次/得票彙總

docs/
├── index.html            # Leaflet 互動地圖（四圖層 × 三屆 × 小黨篩選）
├── villages.topojson     # 簡化後村里界
└── data.js               # 各里各屆指標
```

## 政黨分組

見 `parties.py`。焦點三黨：時代力量(npp)、台灣基進(tsp)、小民參政歐巴桑聯盟(obasan)；
「小黨合計」另含社民黨、綠黨、樹黨、台聯等進步側小黨。藍綠白與無黨另計。
