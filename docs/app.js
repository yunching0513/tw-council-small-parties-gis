/* 進擊的小黨 — 村里級議員選舉 GIS 前端邏輯 */
(function () {
  "use strict";
  const D = window.VILLAGE_DATA || {};
  const NODATA = "#EBE7E0";   // 無資料：近底色，讓空白退入余白
  // しなやか低彩度色盤（朱・常磐綠・金茶・青灰）
  const GROUP_COLOR = {
    kmt: "#6E7E96", dpp: "#2E6B4E", tpp: "#6FA89B", focus: "#A6392C",
    small: "#B8945A", independent: "#A8A8A8", other: "#CDC8BD"
  };
  const GROUP_LABEL = {
    kmt: "國民黨", dpp: "民進黨", tpp: "民眾黨", focus: "焦點小黨",
    small: "小黨", independent: "無黨籍", other: "其他"
  };
  // 焦點黨短碼 → 名稱（圖例與資訊面板共用）
  const FOCUS_NAMES = { npp:"時代力量", tsp:"台灣基進", ob:"歐巴桑聯盟", green:"綠黨", sdp:"社民黨" };
  // 選區參選人名單的政黨配色（含焦點黨）
  const PG_COLOR = { kmt:"#6E7E96", dpp:"#2E6B4E", tpp:"#6FA89B", npp:"#C8862C", tsp:"#A6392C",
    green:"#2C8C7A", sdp:"#5C7186", ob:"#9C6BA3", tree:"#5E8C6A", small:"#B8945A",
    independent:"#A8A8A8", focus:"#A6392C", other:"#C2BBAE" };
  const SMALL_PG = new Set(["npp","tsp","green","sdp","ob","tree","small","focus"]);

  // ---- 狀態 ----
  const state = { layer: "small", year: "2022", focus: "all" };

  // ---- 色階（低彩度・淺底，低值退入余白） ----
  // 小黨得票率：米紙 → 古樸朱紅
  function seq(v) {
    if (v == null || isNaN(v)) return NODATA;
    const stops = [[0, [237,232,224]], [3, [231,211,204]], [8, [210,150,138]],
                   [18, [183,90,74]], [40, [150,42,34]], [60, [120,30,24]]];
    return ramp(v, stops);
  }
  // 焦點黨熱區：同朱紅家族，門檻較低（單黨得票率較小）
  function seqFocus(v) {
    if (v == null || isNaN(v)) return NODATA;
    const stops = [[0, [237,232,224]], [1.5, [231,211,204]], [4, [212,150,135]],
                   [9, [185,88,72]], [20, [150,42,34]]];
    return ramp(v, stops);
  }
  // 待拓展區：金茶 → 朱紅（政黨票挺小黨 0–11%，越暖＝潛力越大）
  function seqWhite(v) {
    if (v == null || isNaN(v)) return NODATA;
    const stops = [[0, [233,229,221]], [2, [219,201,170]], [4, [197,160,110]],
                   [7, [184,110,70]], [11, [166,57,44]]];
    return ramp(v, stops);
  }
  // 發散（跨屆成長）：常磐綠(降) ↔ 紙(平) ↔ 朱紅(升)
  function div(v) {
    if (v == null || isNaN(v)) return NODATA;
    const c = Math.max(-15, Math.min(15, v)) / 15;
    if (c >= 0) return mix([228,224,216], [166,57,44], c);
    return mix([228,224,216], [46,107,78], -c);
  }
  function ramp(v, stops) {
    for (let i = 1; i < stops.length; i++) {
      if (v <= stops[i][0]) {
        const t = (v - stops[i-1][0]) / (stops[i][0] - stops[i-1][0] || 1);
        return mix(stops[i-1][1], stops[i][1], t);
      }
    }
    return rgb(stops[stops.length-1][1]);
  }
  const mix = (a, b, t) => rgb([0,1,2].map(i => Math.round(a[i] + (b[i]-a[i])*t)));
  const rgb = a => `rgb(${a[0]},${a[1]},${a[2]})`;

  // ---- 取值：每個村里在當前圖層的 (數值, 顏色, 透明度) ----
  function valueOf(vc) {
    const n = D[vc]; if (!n) return null;
    const Y = n.y || {};
    if (state.layer === "small") {
      const d = Y[state.year]; if (!d) return null;
      let val, col;
      if (state.focus === "all") { val = d.smS; col = seq(val); }
      else { const v = d[state.focus] || 0, t = d.tot || 1;
             val = Math.round(1000*v/t)/10; col = seqFocus(val); }
      return { val, col, op: 0.82, fmt: val + "%" };
    }
    if (state.layer === "compete") {
      const d = Y[state.year]; if (!d || !d.tot) return null;
      const g = d.lead || "other";
      return { val: g, col: GROUP_COLOR[g] || "#4a5568",
               op: 0.45 + 0.5 * Math.min(1, (d.leadS||0)/70), fmt: GROUP_LABEL[g] };
    }
    if (state.layer === "trend") {
      const a = Y["2022"], base = Y["2014"] || Y["2018"]; if (!a || !base) return null;
      const val = Math.round((a.smS - base.smS)*10)/10;
      return { val, col: div(val), op: 0.82, fmt: (val>=0?"+":"") + val + "%" };
    }
    if (state.layer === "white") {
      const pl = (n.pl && (n.pl["2024"] || n.pl["2020"])); const a = Y["2022"];
      if (!pl) return null;
      const latent = pl.sm || 0, scand = a ? a.scand : 0;
      if (scand > 0)   // 已有小黨參選 → 淡綠，退入余白（已被服務）
        return { val: latent, col: "#C9D6CC", op: 0.5,
                 fmt: "已有小黨議員參選（政黨票挺小黨 " + latent + "%）" };
      // 無小黨參選 → 暖色凸顯，越暖＝政黨票潛力越大（有需求、無供給）
      return { val: latent, col: seqWhite(latent), op: 0.9,
               fmt: "待拓展區・政黨票挺小黨 " + latent + "%（無小黨議員參選）" };
    }
    return null;
  }

  // ---- 圖例 ----
  function renderLegend() {
    const el = document.getElementById("legend");
    if (state.layer === "compete") {
      el.innerHTML = '<div class="cap">領先政黨（深淺＝領先幅度）</div>' +
        Object.keys(GROUP_LABEL).map(g =>
          `<div class="row"><span class="sw" style="background:${GROUP_COLOR[g]}"></span>${GROUP_LABEL[g]}</div>`).join("");
      return;
    }
    if (state.layer === "trend") {
      el.innerHTML = '<div class="cap">小黨得票率 2014→2022 變化（綠降・朱升）</div>' + bar([
        ["#2E6B4E","-15%↓"], ["#E4E0D8","0"], ["#A6392C","+15%↑"]]);
      return;
    }
    if (state.layer === "white") {
      el.innerHTML = '<div class="cap">無小黨議員參選的里，依政黨票挺小黨比例上色（越暖＝潛力越大）</div>' +
        bar([["#E9E5DD","0%"], ["#C5A06E","4%"], ["#B86E46","7%"], ["#A6392C","11%+"]]) +
        '<div class="row" style="margin-top:6px"><span class="sw" style="background:#C9D6CC"></span>已有小黨參選</div>';
      return;
    }
    const who = state.focus === "all" ? "小黨合計" : FOCUS_NAMES[state.focus];
    el.innerHTML = `<div class="cap">${who}得票率</div>` +
      bar([["#EDE8E0","0%"], ["#E7D3CC","5%"], ["#D2968A","10%"], ["#B75A4A","35%"], ["#962A22","60%+"]]);
  }
  const bar = arr => '<div style="display:flex;gap:0;height:12px;border-radius:4px;overflow:hidden;margin:2px 0">' +
    arr.map(a => `<span style="flex:1;background:${a[0]}"></span>`).join("") + '</div>' +
    '<div style="display:flex;justify-content:space-between;font-size:10px;color:var(--ink-faint)">' +
    arr.map(a => `<span>${a[1]}</span>`).join("") + '</div>';

  // ---- 地圖 ----
  const map = L.map("map", { preferCanvas: true, renderer: L.canvas(),
    zoomControl: true, minZoom: 7, maxZoom: 15 }).setView([23.7, 120.95], 8);
  window.__map = map;   // 供 console 除錯／程式化控制視野
  map.zoomControl.setPosition("bottomright");   // 避免被左上面板蓋住
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
    { attribution: "© OpenStreetMap © CARTO", subdomains: "abcd" }).addTo(map);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png",
    { subdomains: "abcd", pane: "shadowPane", opacity: .8 }).addTo(map);

  // ---- 行政界白框：村里細線在 styleFn；鄉鎮中線、縣市粗線為獨立圖層 ----
  map.createPane("townPane"); map.getPane("townPane").style.zIndex = 410;
  map.createPane("countyPane"); map.getPane("countyPane").style.zIndex = 420;
  function addBoundary(url, pane, weight, opacity) {
    fetch(url).then(r => r.json()).then(t => {
      const f = topojson.feature(t, t.objects[Object.keys(t.objects)[0]]);
      L.geoJSON(f, { renderer: L.canvas({ pane }), interactive: false,
        style: { stroke: true, color: "#ffffff", weight, opacity, fill: false } }).addTo(map);
    }).catch(() => {});
  }
  addBoundary("towns.topojson", "townPane", 1.2, 0.7);
  addBoundary("counties.topojson", "countyPane", 2.6, 0.85);

  let geoLayer = null, layerByVc = {};
  function styleFn(feat) {
    const vc = feat.properties.VILLCODE, r = valueOf(vc);
    const b = { stroke: true, color: "#ffffff", weight: 0.4, opacity: 0.5, fill: true };
    if (!r) return { ...b, fillColor: NODATA, fillOpacity: .5 };
    return { ...b, fillColor: r.col, fillOpacity: r.op };
  }

  function refresh() {
    if (geoLayer) geoLayer.setStyle(styleFn);
    renderLegend();
    document.getElementById("focusRow").style.display = state.layer === "small" ? "block" : "none";
    const ydis = (state.layer === "trend" || state.layer === "white");
    document.getElementById("yearGrp").style.opacity = ydis ? .4 : 1;
    document.getElementById("yearGrp").style.pointerEvents = ydis ? "none" : "auto";
    if (window.__renderLabels) window.__renderLabels();   // 標註隨圖層/屆別/焦點更新
  }

  // ---- 資訊框 ----
  const info = document.getElementById("info");
  let POLLS = null;     // 投開票所下鑽資料（pollstations.json）
  let ROSTERS = null;   // 各選區參選人名單（zone_rosters.json）
  function showInfo(vc, full) {
    const n = D[vc]; if (!n) { info.style.display = "none"; return; }
    const Y = n.y || {};
    const line = (y) => {
      const d = Y[y]; if (!d) return `<tr><td>${y}</td><td class="r" style="color:#b0b0b0">—</td><td class="r" style="color:#b0b0b0">無資料</td></tr>`;
      const g = d.lead || "other";
      return `<tr><td>${y}</td><td class="r"><b style="color:#A6392C">${d.smS}%</b></td>`+
        `<td class="r"><span class="pill" style="background:${GROUP_COLOR[g]}33;color:${GROUP_COLOR[g]}">${GROUP_LABEL[g]} ${d.leadS}%</span></td></tr>`;
    };
    let foc = "";
    const d22 = Y["2022"];
    if (d22 && d22.tot) {
      const s = (v) => Math.round(1000*(v||0)/d22.tot)/10;
      foc = `<div style="font-size:11px;color:var(--ink-faint);margin:8px 0 3px">2022 焦點小黨得票率</div><table>`+
        Object.entries(FOCUS_NAMES).map(([k,name]) =>
          `<tr><td>${name}</td><td class="r">${s(d22[k])}%</td></tr>`).join("") + `</table>`;
    }
    let pl = "";
    const p = n.pl && (n.pl["2024"] || n.pl["2020"]);
    if (p) pl = `<div style="font-size:11px;color:var(--ink-faint);margin:8px 0 3px">政黨票挺小黨（不分區）</div>`+
      `<table><tr><td>小黨合計</td><td class="r"><b style="color:#A6392C">${p.sm}%</b></td></tr></table>`;
    // 投開票所下鑽（點擊村里時顯示）：2022 區域議員各投開票所小黨得票率
    let polls = "";
    if (full && POLLS && POLLS[vc]) {
      const ps = POLLS[vc].p.slice().sort((a, b) => b[2] - a[2]);
      polls = `<div style="font-size:11px;color:var(--ink-faint);margin:9px 0 3px">2022 投開票所小黨得票率（共 ${ps.length} 所）</div>` +
        `<table>` + ps.slice(0, 12).map(([no, tot, pct]) =>
          `<tr><td>${no} 所</td><td class="r" style="color:#9a9a9a">${tot} 票</td>` +
          `<td class="r"><b style="color:#A6392C">${pct}%</b></td></tr>`).join("") +
        (ps.length > 12 ? `<tr><td colspan="3" style="color:var(--ink-faint);font-size:10.5px">…列小黨得票率前 12 高</td></tr>` : "") +
        `</table>`;
    } else if (full && POLLS && !POLLS[vc]) {
      polls = `<div style="font-size:10.5px;color:var(--ink-faint);margin:9px 0 0">（此里無 2022 區域議員投開票所資料）</div>`;
    }
    // 該選區參選人（點擊村里時顯示）：當次該選區全部候選人＋全選區得票
    let roster = "";
    if (full && ROSTERS) {
      const yr = (state.layer === "trend" || state.layer === "white") ? "2022" : state.year;
      const zid = ROSTERS.v[vc] && ROSTERS.v[vc][yr];
      const list = (zid != null) ? (ROSTERS.r[yr] || {})[zid] : null;
      if (list && list.length) {
        roster = `<div style="font-size:11px;color:var(--ink-faint);margin:9px 0 3px">${yr} 該選區參選人（全選區得票・★當選）</div><table>` +
          list.map(([name, party, pg, votes, elected]) => {
            const col = PG_COLOR[pg] || "#999", sm = SMALL_PG.has(pg);
            const mark = elected ? `<span style="color:var(--shu)">★</span> ` : "　";
            const nmStyle = sm ? `color:${col};font-weight:700` : "color:#333";
            return `<tr><td>${mark}<span style="${nmStyle}">${name}</span> ` +
              `<span class="pill" style="background:${col}22;color:${col};font-size:9.5px;padding:0 6px">${party}</span></td>` +
              `<td class="r" style="color:#888">${votes.toLocaleString()}</td></tr>`;
          }).join("") + `</table>`;
      }
    }
    // 本選區歷屆最低當選票數（門檻＝最後一席）
    let thr = "";
    if (full && ROSTERS && ROSTERS.v[vc]) {
      const parts = ["2014", "2018", "2022"].map(yr => {
        const zid = ROSTERS.v[vc][yr];
        const list = (zid != null) ? (ROSTERS.r[yr] || {})[zid] : null;
        if (!list) return null;
        const el = list.filter(c => c[4] === 1);
        if (!el.length) return null;
        const minw = Math.min(...el.map(c => c[3]));
        return `<span style="color:var(--ink-faint)">${yr}</span> <b style="color:var(--shu)">${minw.toLocaleString()}</b>`;
      }).filter(Boolean);
      if (parts.length) thr = `<div style="font-size:11px;color:var(--ink-faint);margin:9px 0 2px">本選區最低當選票數（門檻・最後一席）</div>` +
        `<div style="font-size:12.5px;letter-spacing:.02em">${parts.join("　")}</div>`;
    }
    info.innerHTML = `<div class="vname">${n.v||"（未知村里）"}</div>`+
      `<div class="vloc">${n.c||""} ${n.t||""}　${vc}</div>`+
      `<table><tr><td style="color:var(--ink-faint)">屆別</td><td class="r" style="color:var(--ink-faint)">小黨%</td><td class="r" style="color:var(--ink-faint)">領先黨</td></tr>`+
      line("2014") + line("2018") + line("2022") + `</table>` + foc + pl + polls + thr + roster;
    info.style.display = "block";
  }

  // ---- 載入界圖 ----
  function addGeo(features) {
    geoLayer = L.geoJSON({ type: "FeatureCollection", features }, {
      style: styleFn,
      onEachFeature: (f, lyr) => {
        layerByVc[f.properties.VILLCODE] = lyr;
        lyr.on("mouseover", () => { showInfo(f.properties.VILLCODE, false);
          lyr.bringToFront && lyr.bringToFront();
          lyr.setStyle({ color: "#333333", weight: 1.3, opacity: 1 }); });
        lyr.on("mouseout", () => geoLayer.resetStyle(lyr));
        lyr.on("click", () => { showInfo(f.properties.VILLCODE, true);
          map.fitBounds(lyr.getBounds(), { maxZoom: 13, padding: [40,40] }); });
      }
    }).addTo(map);
    refresh();
    document.getElementById("loading").style.display = "none";
    // 投開票所下鑽 + 選區參選人名單（小檔，背景載入；點擊村里時即可顯示）
    fetch("pollstations.json").then(r => r.json()).then(j => { POLLS = j; }).catch(() => {});
    fetch("zone_rosters.json").then(r => r.json()).then(j => { ROSTERS = j; }).catch(() => {});
  }

  async function load() {
    let r = await fetch("villages.topojson").catch(() => null);
    if (r && r.ok) {
      const topo = await r.json();
      const key = Object.keys(topo.objects)[0];
      addGeo(topojson.feature(topo, topo.objects[key]).features);
      return;
    }
    r = await fetch("villages.geojson");
    addGeo((await r.json()).features);
  }
  load().catch(e => {
    document.getElementById("loading").innerHTML = "載入失敗：" + e +
      "<br><small style='color:#b0b0b0'>請先執行 build_map.py 產生 villages.topojson</small>";
  });

  // ---- 控制項 ----
  document.querySelectorAll(".layerbtn").forEach(b => b.onclick = () => {
    document.querySelectorAll(".layerbtn").forEach(x => x.classList.remove("on"));
    b.classList.add("on"); state.layer = b.dataset.layer; refresh();
  });
  document.querySelectorAll("#yearSeg button").forEach(b => b.onclick = () => {
    document.querySelectorAll("#yearSeg button").forEach(x => x.classList.remove("on"));
    b.classList.add("on"); state.year = b.dataset.y; refresh();
  });
  document.querySelectorAll("#focusSeg button").forEach(b => b.onclick = () => {
    document.querySelectorAll("#focusSeg button").forEach(x => x.classList.remove("on"));
    b.classList.add("on"); state.focus = b.dataset.f; refresh();
  });

  // ---- 搜尋 ----
  const search = document.getElementById("search");
  search.addEventListener("change", () => {
    const q = search.value.trim(); if (!q) return;
    for (const vc in D) {
      const n = D[vc];
      if ((n.v && n.v.includes(q)) || (n.t && n.t.includes(q))) {
        const lyr = layerByVc[vc];
        if (lyr) { map.fitBounds(lyr.getBounds(), { maxZoom: 13, padding: [40,40] }); showInfo(vc, true); }
        return;
      }
    }
  });

  // ---- 手機：面板收合 ----
  const panel = document.getElementById("panel");
  const panelToggle = document.getElementById("panelToggle");
  const setCollapsed = (c) => { panel.classList.toggle("collapsed", c); panelToggle.textContent = c ? "▴" : "▾"; };
  if (window.innerWidth <= 680) setCollapsed(true);
  panelToggle.onclick = () => setCollapsed(!panel.classList.contains("collapsed"));

  // ---- 拜票地點 POI（市場/郵局/宗教場所/車站）----
  const POI_STYLE = {
    market:  { c: "#D9772B", label: "市場" },
    post:    { c: "#2E7D46", label: "郵局" },
    temple:  { c: "#B23A86", label: "宗教場所" },
    transit: { c: "#2E6DA4", label: "車站" },
  };
  const POI_CAP = 600;      // 每類在當前視野的顯示上限
  const POI_MINZOOM = 11;   // 放大到此層級才顯示（避免全台滿版）
  let POI = null, poiLoading = false;
  const poiOn = new Set();
  const poiNote = document.getElementById("poiNote");
  // 專屬高層 pane，確保標記畫在面量圖之上
  map.createPane("poiPane");
  map.getPane("poiPane").style.zIndex = 650;
  const poiRenderer = L.canvas({ pane: "poiPane" });
  const poiLayer = L.layerGroup().addTo(map);

  function renderPOI() {
    poiLayer.clearLayers();
    if (poiOn.size === 0) { poiNote.textContent = "勾選類別以顯示拜票點"; return; }
    if (!POI) { poiNote.textContent = poiLoading ? "載入拜票點資料…" : ""; return; }
    if (map.getZoom() < POI_MINZOOM) { poiNote.textContent = "放大到鄉鎮層級以顯示拜票點"; return; }
    const b = map.getBounds();
    let shown = 0, capped = false;
    for (const cat of poiOn) {
      const arr = POI[cat] || []; let n = 0;
      for (const p of arr) {
        const lng = p[0], lat = p[1];
        if (lat < b.getSouth() || lat > b.getNorth() || lng < b.getWest() || lng > b.getEast()) continue;
        if (n >= POI_CAP) { capped = true; break; }
        L.circleMarker([lat, lng], { renderer: poiRenderer, radius: 5, color: "#fff",
          weight: 1, fillColor: POI_STYLE[cat].c, fillOpacity: .95 })
          .bindPopup(`<b>${p[2]}</b><br><span style="color:#9a9a9a">${POI_STYLE[cat].label}</span>`)
          .addTo(poiLayer);
        n++; shown++;
      }
    }
    poiNote.textContent = shown
      ? (capped ? `顯示 ${shown} 個（部分類別達上限，再放大看更多）` : `顯示 ${shown} 個拜票點`)
      : "此範圍內無所選類別據點";
  }
  map.on("moveend zoomend", () => { if (poiOn.size) renderPOI(); });

  document.querySelectorAll("#poiSeg button").forEach(b => b.onclick = () => {
    const cat = b.dataset.poi;
    if (poiOn.has(cat)) { poiOn.delete(cat); b.classList.remove("on"); }
    else { poiOn.add(cat); b.classList.add("on"); }
    if (!POI && !poiLoading) {
      poiLoading = true; poiNote.textContent = "載入拜票點資料…";
      fetch("canvass.json").then(r => r.json())
        .then(j => { POI = j; poiLoading = false; renderPOI(); })
        .catch(() => { poiLoading = false; poiNote.textContent = "拜票點資料載入失敗"; });
    } else renderPOI();
  });

  // ---- 道路圖層（國道/省道/主要道路）----
  map.createPane("roadPane");
  map.getPane("roadPane").style.zIndex = 440;   // 面量圖(400)之上、標籤/POI 之下
  const roadRenderer = L.canvas({ pane: "roadPane" });
  let ROADS = null, roadsLoading = false, roadsOn = false, roadLayer = null;
  const roadStyle = (f) => {
    if (f.properties.hw === "trunk") return { color: "#6b7884", weight: 1.8, opacity: .66 };
    return { color: "#9aa3ad", weight: 1, opacity: .5 };   // primary 主要市區幹道
  };
  function renderRoads() {
    if (roadLayer) { map.removeLayer(roadLayer); roadLayer = null; }
    if (!roadsOn || !ROADS) return;
    // 全台視野只畫國道/省道骨架；放大到 zoom≥11 才加主要市區幹道
    const feats = map.getZoom() >= 11 ? ROADS.features
      : ROADS.features.filter(f => f.properties.hw !== "primary");
    roadLayer = L.geoJSON({ type: "FeatureCollection", features: feats },
      { renderer: roadRenderer, style: roadStyle, interactive: false }).addTo(map);
  }
  map.on("zoomend", () => { if (roadsOn) renderRoads(); });

  const roadBtn = document.getElementById("roadBtn");
  const roadLabel = roadBtn.lastChild;   // 文字節點
  roadBtn.onclick = () => {
    roadsOn = !roadsOn; roadBtn.classList.toggle("on", roadsOn);
    if (roadsOn && !ROADS && !roadsLoading) {
      roadsLoading = true; roadLabel.nodeValue = " 載入道路…";
      fetch("roads.json").then(r => r.json())
        .then(j => { ROADS = j; roadsLoading = false; roadLabel.nodeValue = "省道・主要道路"; renderRoads(); })
        .catch(() => { roadsLoading = false; roadLabel.nodeValue = "省道・主要道路"; });
    } else renderRoads();
  };

  // ---- 面量圖得票標註（小黨得票數／率，字級隨縮放）----
  const labelLayer = L.layerGroup();
  let labelsOn = false;
  const centroids = {};
  const labelNote = document.getElementById("labelNote");
  const LABEL_MINZOOM = 12, LABEL_CAP = 260;
  const mapEl = document.getElementById("map");

  function centerOf(vc) {
    if (centroids[vc]) return centroids[vc];
    const lyr = layerByVc[vc]; if (!lyr) return null;
    return (centroids[vc] = lyr.getBounds().getCenter());
  }
  function labelVal(vc) {
    const yr = (state.layer === "trend" || state.layer === "white") ? "2022" : state.year;
    const d = (D[vc] && D[vc].y) ? D[vc].y[yr] : null;
    if (!d || !d.tot) return null;
    const foc = state.layer === "small" ? state.focus : "all";
    const votes = foc === "all" ? d.sm : (d[foc] || 0);
    if (votes < 15) return null;            // 太少不標，避免雜亂
    const share = Math.round(1000 * votes / d.tot) / 10;
    if (share < 2) return null;
    return { votes, share };
  }
  const labelSize = (z) => z <= 12 ? 9.5 : z === 13 ? 11 : z === 14 ? 12.5 : 14;

  function renderLabels() {
    labelLayer.clearLayers();
    if (!labelsOn) { labelNote.textContent = "勾選後放大到鄉鎮層級顯示"; return; }
    const z = map.getZoom();
    if (z < LABEL_MINZOOM) { labelNote.textContent = "放大到鄉鎮層級顯示標註"; return; }
    mapEl.style.setProperty("--lab", labelSize(z) + "px");
    const b = map.getBounds(), withVotes = z >= 14, cand = [];
    for (const vc in D) {
      const v = labelVal(vc); if (!v) continue;
      const c = centerOf(vc); if (!c) continue;
      if (c.lat < b.getSouth() || c.lat > b.getNorth() || c.lng < b.getWest() || c.lng > b.getEast()) continue;
      cand.push({ vc, c, v });
    }
    cand.sort((a, b2) => b2.v.share - a.v.share);           // 密集時優先標得票率高者
    const show = cand.slice(0, LABEL_CAP);
    for (const { vc, c, v } of show) {
      const name = (D[vc] && D[vc].v) || "";                // 里名為主
      const sub = withVotes ? `${v.share}%・${v.votes.toLocaleString()}票` : `${v.share}%`;
      const html = `<div class="vlab"><b>${name}</b><i>${sub}</i></div>`;
      L.marker(c, { icon: L.divIcon({ html, className: "", iconSize: [0, 0] }),
        interactive: false, keyboard: false }).addTo(labelLayer);
    }
    labelNote.textContent = `標註 ${show.length} 里` +
      (cand.length > LABEL_CAP ? `（密集處取得票率前 ${LABEL_CAP} 高）` : "");
  }
  map.on("moveend zoomend", () => { if (labelsOn) renderLabels(); });
  document.getElementById("labelBtn").onclick = (e) => {
    labelsOn = !labelsOn; e.currentTarget.classList.toggle("on", labelsOn);
    if (labelsOn) labelLayer.addTo(map); else labelLayer.remove();
    renderLabels();
  };
  window.__renderLabels = renderLabels;   // 供圖層/屆別切換時更新

  // ---- 選區門檻分析 Modal ----
  const SMALL_PARTIES = new Set(["時代力量","台灣基進","綠黨","社會民主黨","小民參政歐巴桑聯盟","樹黨","綠黨社會民主黨聯盟","人民民主黨","左翼聯盟"]);
  const SM_COLOR = {"時代力量":"#C8862C","台灣基進":"#A6392C","社會民主黨":"#5C7186","綠黨":"#2E6B4E","小民參政歐巴桑聯盟":"#9C6BA3","樹黨":"#5E8C6A","左翼聯盟":"#8B6914"};
  const SM_SHORT = {"時代力量":"時力","台灣基進":"基進","社會民主黨":"社民","綠黨":"綠黨","小民參政歐巴桑聯盟":"歐巴桑","樹黨":"樹黨","左翼聯盟":"左翼"};

  let zmData = null, zmMaxW = 1;
  let zmSc = "min_win", zmSd = 1;

  function buildZoneAnalysis() {
    if (!ROSTERS) return [];
    const yr = "2022";
    const zones = ROSTERS.r[yr] || {};
    const zoneVills = {};
    for (const vc in (ROSTERS.v || {})) {
      const zid = ROSTERS.v[vc][yr];
      if (zid == null) continue;
      const zk = String(zid);
      if (!zoneVills[zk]) zoneVills[zk] = [];
      zoneVills[zk].push(vc);
    }
    const results = [];
    for (const [zid, cands] of Object.entries(zones)) {
      const elected = cands.filter(c => c[4] === 1);
      if (!elected.length) continue;
      const losers = cands.filter(c => c[4] === 0);
      const minWin = elected.reduce((a,b) => a[3]<b[3]?a:b);
      const maxWin = elected.reduce((a,b) => a[3]>b[3]?a:b);
      const maxLose = losers.length ? losers.reduce((a,b) => a[3]>b[3]?a:b) : null;
      const vills = zoneVills[zid] || [];
      const county = vills.length ? ((D[vills[0]] && D[vills[0]].c) || "") : "";
      const towns = [...new Set(vills.map(vc => (D[vc] && D[vc].t) || "").filter(Boolean))].sort();
      const label = towns.slice(0,4).join("・") + (towns.length > 4 ? "…" : "");
      const smCands = cands.filter(c => SMALL_PARTIES.has(c[1]));
      const smTotal = smCands.reduce((s,c) => s+c[3], 0);
      results.push({
        county, label, seats: elected.length,
        min_win: minWin[3], min_win_cand: minWin[0],
        max_win: maxWin[3], max_win_cand: maxWin[0],
        margin: maxLose ? minWin[3] - maxLose[3] : null,
        sm_total: smTotal,
        sm: smCands.sort((a,b)=>b[3]-a[3]).map(c=>[c[0],c[1],c[3]])
      });
    }
    return results.sort((a,b) => a.county.localeCompare(b.county,"zh-TW") || a.label.localeCompare(b.label,"zh-TW"));
  }

  function zmRender() {
    if (!zmData) return;
    const c = document.getElementById("zmSel").value;
    const q = document.getElementById("zmQ").value.toLowerCase();
    const cap = +document.getElementById("zmCap").value;
    const onlySm = document.getElementById("zmOnlySm").checked;
    const onlyD = document.getElementById("zmOnlyD").checked;
    document.getElementById("zmCapOut").textContent = cap >= 30000 ? "不限" : cap.toLocaleString("zh-TW");
    let data = zmData.filter(r => {
      if (c && r.county !== c) return false;
      const t = r.label+r.county+(r.min_win_cand||"")+(r.max_win_cand||"")+(r.sm||[]).map(s=>s[0]+s[1]).join("");
      if (q && !t.toLowerCase().includes(q)) return false;
      if (r.min_win > cap) return false;
      if (onlySm && !r.sm_total) return false;
      if (onlyD && (r.margin == null || Math.abs(r.margin) >= 500)) return false;
      return true;
    });
    const inf = zmSd > 0 ? Infinity : -Infinity;
    data.sort((a,b) => {
      const av = a[zmSc] != null ? a[zmSc] : inf;
      const bv = b[zmSc] != null ? b[zmSc] : inf;
      return zmSd * (typeof av === "string" ? av.localeCompare(bv,"zh-TW") : av-bv);
    });
    const tbody = document.getElementById("zmBody");
    tbody.innerHTML = "";
    document.getElementById("zmEmpty").style.display = data.length ? "none" : "block";
    document.getElementById("zmMeta").textContent = `顯示 ${data.length} 個選區（2022，全台 ${zmData.length} 選區）`;
    const fmt = n => n == null ? "—" : n.toLocaleString("zh-TW");
    data.forEach(r => {
      const tr = document.createElement("tr");
      const smHtml = (r.sm||[]).map(([n,p,v]) =>
        `<span style="color:${SM_COLOR[p]||"#888"};font-weight:500">${n}</span>` +
        `<span style="font-size:10px;color:var(--ink-faint)"> ${SM_SHORT[p]||p} ${v.toLocaleString("zh-TW")}</span>`
      ).join("<br>");
      const mg = r.margin;
      const mgStr = mg == null ? "—" : (mg>=0?"+":"") + mg.toLocaleString("zh-TW");
      const mgCls = mg != null && Math.abs(mg) < 200 ? "zm-danger" : mg != null && mg > 800 ? "zm-ok" : "";
      const bMin = Math.round(r.min_win/zmMaxW*80);
      const bMax = Math.round(r.max_win/zmMaxW*80);
      const bSm = r.sm_total ? Math.round(r.sm_total/zmMaxW*80) : 0;
      tr.innerHTML =
        `<td title="${r.county} ${r.label}">` +
          `<span style="font-size:10px;color:var(--ink-faint)">${r.county}</span>` +
          `<br><span style="font-weight:500;font-size:11.5px">${r.label}</span>` +
        `</td>` +
        `<td style="text-align:center"><span class="seat">${r.seats}</span></td>` +
        `<td>` +
          `<span class="n zm-danger">${fmt(r.min_win)}</span>` +
          `<br><span class="cname">${r.min_win_cand||""}</span>` +
          `<span class="mbar" style="width:${bMin}%;background:#D4958C;opacity:.8"></span>` +
        `</td>` +
        `<td>` +
          `<span class="n">${fmt(r.max_win)}</span>` +
          `<br><span class="cname">${r.max_win_cand||""}</span>` +
          `<span class="mbar" style="width:${bMax}%;background:#9ab0c4;opacity:.7"></span>` +
        `</td>` +
        `<td>` +
          (r.sm_total ?
            `<span class="n" style="color:#1D6B50;font-weight:500">${fmt(r.sm_total)}</span>` +
            `<span class="mbar" style="width:${bSm}%;background:#2E6B4E;opacity:.65"></span>` :
            `<span style="opacity:.3;font-size:11px">—</span>`) +
        `</td>` +
        `<td class="n ${mgCls}" style="font-size:12px">${mgStr}</td>` +
        `<td style="font-size:11px">${smHtml||'<span style="opacity:.3">無</span>'}</td>`;
      tbody.appendChild(tr);
    });
  }

  function zmInit() {
    zmData = buildZoneAnalysis();
    zmMaxW = Math.max(...zmData.map(r=>r.max_win));
    const counties = [...new Set(zmData.map(r=>r.county))].sort();
    const sel = document.getElementById("zmSel");
    counties.forEach(c => { const o=document.createElement("option"); o.value=c; o.textContent=c; sel.appendChild(o); });
    zmRender();
  }

  function zmOpen() {
    document.getElementById("zoneModal").classList.add("open");
    if (zmData) return;
    if (ROSTERS) { zmInit(); return; }
    document.getElementById("zmMeta").textContent = "載入選區資料中…";
    const check = setInterval(() => { if (ROSTERS) { clearInterval(check); zmInit(); } }, 200);
  }

  document.getElementById("zoneBtn").onclick = zmOpen;
  document.getElementById("zmClose").onclick = () => document.getElementById("zoneModal").classList.remove("open");
  document.getElementById("zoneModal").onclick = (e) => { if (e.target === e.currentTarget) e.currentTarget.classList.remove("open"); };
  document.querySelectorAll("#zmTable th[data-col]").forEach(th => {
    th.addEventListener("click", () => {
      if (zmSc === th.dataset.col) zmSd *= -1;
      else { zmSc = th.dataset.col; zmSd = 1; }
      document.querySelectorAll("#zmTable th").forEach(t => t.classList.remove("asc","desc"));
      th.classList.add(zmSd === 1 ? "asc" : "desc");
      zmRender();
    });
  });
  ["zmSel","zmOnlySm","zmOnlyD"].forEach(id => document.getElementById(id).addEventListener("change", zmRender));
  document.getElementById("zmCap").addEventListener("input", zmRender);
  document.getElementById("zmQ").addEventListener("input", zmRender);
  document.querySelector("#zmTable th[data-col='min_win']").classList.add("asc");
})();
