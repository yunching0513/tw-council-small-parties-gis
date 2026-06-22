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
  // 白地：金茶 → 朱紅（政黨票挺小黨 0–11%，越暖＝潛力越大）
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
               fmt: "白地・政黨票挺小黨 " + latent + "%（無小黨議員參選）" };
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
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
    { attribution: "© OpenStreetMap © CARTO", subdomains: "abcd" }).addTo(map);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png",
    { subdomains: "abcd", pane: "shadowPane", opacity: .8 }).addTo(map);

  let geoLayer = null, layerByVc = {};
  function styleFn(feat) {
    const vc = feat.properties.VILLCODE, r = valueOf(vc);
    if (!r) return { stroke: false, fill: true, fillColor: NODATA, fillOpacity: .5 };
    return { stroke: false, fill: true, fillColor: r.col, fillOpacity: r.op };
  }

  function refresh() {
    if (geoLayer) geoLayer.setStyle(styleFn);
    renderLegend();
    document.getElementById("focusRow").style.display = state.layer === "small" ? "block" : "none";
    const ydis = (state.layer === "trend" || state.layer === "white");
    document.getElementById("yearGrp").style.opacity = ydis ? .4 : 1;
    document.getElementById("yearGrp").style.pointerEvents = ydis ? "none" : "auto";
  }

  // ---- 資訊框 ----
  const info = document.getElementById("info");
  function showInfo(vc) {
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
    info.innerHTML = `<div class="vname">${n.v||"（未知村里）"}</div>`+
      `<div class="vloc">${n.c||""} ${n.t||""}　${vc}</div>`+
      `<table><tr><td style="color:var(--ink-faint)">屆別</td><td class="r" style="color:var(--ink-faint)">小黨%</td><td class="r" style="color:var(--ink-faint)">領先黨</td></tr>`+
      line("2014") + line("2018") + line("2022") + `</table>` + foc + pl;
    info.style.display = "block";
  }

  // ---- 載入界圖 ----
  function addGeo(features) {
    geoLayer = L.geoJSON({ type: "FeatureCollection", features }, {
      style: styleFn,
      onEachFeature: (f, lyr) => {
        layerByVc[f.properties.VILLCODE] = lyr;
        lyr.on("mouseover", () => { showInfo(f.properties.VILLCODE);
          lyr.bringToFront && lyr.bringToFront();
          lyr.setStyle({ stroke: true, color: "#333333", weight: 1 }); });
        lyr.on("mouseout", () => lyr.setStyle({ stroke: false }));
        lyr.on("click", () => { showInfo(f.properties.VILLCODE);
          map.fitBounds(lyr.getBounds(), { maxZoom: 13, padding: [40,40] }); });
      }
    }).addTo(map);
    refresh();
    document.getElementById("loading").style.display = "none";
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
        if (lyr) { map.fitBounds(lyr.getBounds(), { maxZoom: 13, padding: [40,40] }); showInfo(vc); }
        return;
      }
    }
  });
})();
