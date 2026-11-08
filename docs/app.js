const yen = n => "¥" + Math.round(n).toLocaleString("ja-JP");
const sgn = n => (n > 0 ? "+" : n < 0 ? "−" : "±") + Math.abs(Math.round(n)).toLocaleString("ja-JP");
const fmtT = t => { const d = new Date(t); return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`; };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const ago = t => { const m = (Date.now() - new Date(t)) / 60000; return m < 60 ? `${Math.round(m)}分前` : `${(m/60).toFixed(1)}時間前`; };

async function load() {
  try {
    const q = "?t=" + Date.now();
    const [hist, status] = await Promise.all([
      fetch("data/history.json" + q).then(r => r.json()),
      fetch("data/status.json" + q).then(r => r.json()),
    ]);
    render(hist, status);
  } catch (e) {
    document.getElementById("banner").innerHTML = `<div class="banner bad">データを読み込めませんでした（${esc(e.message)}）</div>`;
  }
}

function render(hist, st) {
  const days = Math.ceil((new Date(st.depart_date + "T00:00:00+09:00") - Date.now()) / 86400000);
  document.getElementById("sub").textContent =
    `${st.depart_date.slice(5).replace("-", "/")} 発 → ${st.return_date.slice(5).replace("-", "/")} 帰着 ・ 出発まであと ${days} 日`;
  document.getElementById("updated").textContent = st.updated ? `最終チェック ${fmtT(st.updated)}（${ago(st.updated)}）` : "";

  // 鮮度チェック
  const lastOk = Math.max(...st.routes.map(r => r.last_ok ? +new Date(r.last_ok) : 0));
  const hrs = lastOk ? (Date.now() - lastOk) / 3600000 : Infinity;
  const b = document.getElementById("banner");
  b.innerHTML = hrs > 8 ? `<div class="banner bad">⚠ 価格の取得が ${isFinite(hrs) ? Math.floor(hrs) + "時間" : "まだ一度も"} 成功していません。表示は古い可能性があります。</div>`
    : hrs > 4 ? `<div class="banner warn">最終取得から ${Math.floor(hrs)} 時間たっています</div>` : "";

  const wrap = document.getElementById("cards");
  wrap.innerHTML = "";
  for (const r of st.routes) {
    const h = hist[r.id] || [];
    const cur = h[h.length - 1];
    const card = document.createElement("section");
    card.className = "card";
    let html = `<h2>${esc(r.name)}</h2><div class="route-sub">${esc(r.from)} ⇄ ${esc(r.to)}</div>`;
    if (!cur) {
      html += `<div class="price na">${r.last_error ? "取得できていません" : "データ待ち"}</div>`;
      if (r.last_error) html += `<div class="detail">エラー: ${esc(r.last_error)}</div>`;
    } else {
      const low = h.reduce((a, x) => x.price < a.price ? x : a, h[0]);
      const prev = h[h.length - 2];
      const dayAgo = [...h].reverse().find(x => new Date(x.t) <= new Date(new Date(cur.t) - 864e5));
      const chip = (label, d) => d == null ? "" :
        `<span class="chip ${d < 0 ? "down" : d > 0 ? "up" : ""}">${label} ${d < 0 ? "▼" : d > 0 ? "▲" : ""}${sgn(d)}</span>`;
      html += `<div class="price">${yen(cur.price)}</div><div class="chips">
        ${chip("前回比", prev ? cur.price - prev.price : null)}
        ${chip("24時間比", dayAgo ? cur.price - dayAgo.price : null)}
        <span class="chip">最安 ${yen(low.price)}（${fmtT(low.t)}）</span>
        ${r.target_price ? `<span class="chip ${cur.price <= r.target_price ? "down" : ""}">目標 ${yen(r.target_price)} ${cur.price <= r.target_price ? "達成🎯" : "まであと " + yen(cur.price - r.target_price)}</span>` : ""}
      </div>
      ${r.advice ? `<div class="advice ${esc(r.advice.level)}"><b>${{wait:"⏳",consider:"🤔",buy:"🛒",urgent:"⏰"}[r.advice.level] || ""} ${esc(r.advice.label)}</b><span>${esc(r.advice.reason)}</span></div>` : ""}
      ${cur.airline ? `<div class="detail"><b>${esc(cur.airline)}</b> ・ ${cur.stops ? "乗継" + cur.stops + "回" : "直行"}</div>` : ""}
      ${r.last_error && new Date(r.last_error_at) > new Date(cur.t) ? `<div class="detail" style="color:var(--warn)">直近の取得は失敗: ${esc(r.last_error)}</div>` : ""}
      <div class="chart"><svg role="img" aria-label="${esc(r.name)}の価格推移"></svg><div class="tip"></div></div>
      <details><summary>価格の履歴（表）</summary><table><tr><th>日時</th><th>航空会社</th><th>価格</th></tr>
        ${[...h].reverse().slice(0, 60).map(x => `<tr><td>${fmtT(x.t)}</td><td>${esc(x.airline || "")}</td><td>${yen(x.price)}</td></tr>`).join("")}
      </table></details>`;
    }
    html += `<a class="btn" href="${esc(r.search_url)}" target="_blank" rel="noopener">Trip.com で開く</a>`;
    card.innerHTML = html;
    wrap.appendChild(card);
    if (h.length) drawChart(card.querySelector(".chart"), h);
  }
}

function drawChart(box, h) {
  const svg = box.querySelector("svg"), tip = box.querySelector(".tip");
  const W = box.clientWidth, H = 150, L = 4, R = 52, T = 22, B = 18;
  const xs = h.map(x => +new Date(x.t)), ys = h.map(x => x.price);
  let x0 = Math.min(...xs), x1 = Math.max(...xs); if (x1 === x0) { x0 -= 36e5; x1 += 36e5; }
  let y0 = Math.min(...ys), y1 = Math.max(...ys); const pad = Math.max((y1 - y0) * 0.15, 500); y0 -= pad; y1 += pad;
  const X = v => L + (v - x0) / (x1 - x0) * (W - L - R), Y = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  const ns = "http://www.w3.org/2000/svg";
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const el = (n, a) => { const e = document.createElementNS(ns, n); for (const k in a) e.setAttribute(k, a[k]); svg.appendChild(e); return e; };
  // 目盛り（3本）
  const lo = Math.min(...ys), hi = Math.max(...ys);
  for (const v of (lo === hi ? [lo] : [lo, (lo + hi) / 2, hi])) {
    const y = Y(v);
    el("line", { x1: L, x2: W - R, y1: y, y2: y, stroke: "var(--grid)", "stroke-width": 1 });
    const t = el("text", { x: W - R + 6, y: y + 4, fill: "var(--text-3)", "font-size": 11 }); t.textContent = "¥" + (v / 1000).toFixed(1) + "k";
  }
  const tl = el("text", { x: L, y: H - 2, fill: "var(--text-3)", "font-size": 11 }); tl.textContent = fmtT(h[0].t).split(" ")[0];
  const tr = el("text", { x: W - R, y: H - 2, fill: "var(--text-3)", "font-size": 11, "text-anchor": "end" }); tr.textContent = "現在";
  const d = h.map((x, i) => (i ? "L" : "M") + X(xs[i]).toFixed(1) + " " + Y(x.price).toFixed(1)).join(" ");
  el("path", { d, fill: "none", stroke: "var(--series)", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" });
  // 最安点と現在点
  const li = ys.indexOf(Math.min(...ys)), n = h.length - 1;
  el("circle", { cx: X(xs[n]), cy: Y(ys[n]), r: 4, fill: "var(--series)", stroke: "var(--surface)", "stroke-width": 2 });
  if (li !== n) {
    el("circle", { cx: X(xs[li]), cy: Y(ys[li]), r: 4, fill: "var(--surface)", stroke: "var(--series)", "stroke-width": 2 });
  }
  // ホバー／タッチ
  const cross = el("line", { y1: T, y2: H - B, stroke: "var(--text-3)", "stroke-width": 1, "stroke-dasharray": "3 3", visibility: "hidden" });
  const dot = el("circle", { r: 5, fill: "var(--series)", stroke: "var(--surface)", "stroke-width": 2, visibility: "hidden" });
  const move = ev => {
    const p = ev.touches ? ev.touches[0] : ev, rect = svg.getBoundingClientRect(), px = p.clientX - rect.left;
    let best = 0; xs.forEach((v, i) => { if (Math.abs(X(v) - px) < Math.abs(X(xs[best]) - px)) best = i; });
    const cx = X(xs[best]), cy = Y(ys[best]);
    cross.setAttribute("x1", cx); cross.setAttribute("x2", cx); cross.setAttribute("visibility", "visible");
    dot.setAttribute("cx", cx); dot.setAttribute("cy", cy); dot.setAttribute("visibility", "visible");
    tip.style.display = "block"; tip.textContent = `${fmtT(h[best].t)}  ${yen(ys[best])}`;
    tip.style.left = Math.min(Math.max(cx, 60), W - 60) + "px";
  };
  const hide = () => { cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); tip.style.display = "none"; };
  svg.addEventListener("pointermove", move); svg.addEventListener("pointerdown", move);
  svg.addEventListener("touchmove", move, { passive: true }); svg.addEventListener("pointerleave", hide);
}

load();
setInterval(load, 10 * 60 * 1000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) load(); });
