const COLORS = { extreme: "#b71c1c", high: "#e65100", moderate: "#f9a825", projected: "#7b1fa2" };
const REC = { fast_track: "#2e7d32", standard: "#1565c0", manual_review: "#c62828", needs_info: "#6a1b9a" };
const REC_LABEL = { fast_track: "fast-track", standard: "standard", manual_review: "manual review", needs_info: "needs info" };
const INDIA = [22.5, 79.0];

const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const map = L.map("map").setView(INDIA, 5);
const eventsEl = document.getElementById("events");

let tileWarned = false;
const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18, attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);
tiles.on("tileerror", () => {
  if (tileWarned) return;
  tileWarned = true;
  eventsEl.insertAdjacentHTML("beforeend",
    "<p style='color:#b71c1c;font-size:12px'>Map tiles failed to load. Zones and buildings still draw.</p>");
});

const projLayer = L.layerGroup().addTo(map);
const safeLayer = L.layerGroup().addTo(map);
const hitLayer = L.layerGroup().addTo(map);
const all = L.featureGroup();
const markers = {};          // building_id -> marker
const baseStyle = {};        // building_id -> original style
let claims = [];
let selectedId = null;

function ring(geom) { return geom.coordinates[0].map(([lng, lat]) => [lat, lng]); }
const fmt = n => Number(n).toLocaleString();

function buildingPopup(b) {
  return `<b>${esc(b.building_id)}</b> (${esc(b.policy_id)})<br>${esc(b.construction_type)}, built ${esc(b.year_built)}, ${esc(b.storeys)} storeys<br>` +
    `Insured value: ${fmt(b.insured_value)}<br>Exposure: ${esc(b.band || "none")}${b.event_id ? " (" + esc(b.event_id) + ")" : ""}`;
}

function checkRow(name, ch) {
  let status;
  if (ch.ran) status = `risk ${ch.risk}`;
  else if (ch.skipped_by_flag) status = `<span class="skip">skipped (flag)</span>`;
  else status = `<span class="skip">not run</span>`;
  return `<tr><td>${esc(name)}</td><td>${status}</td><td>${esc(ch.result ?? "")}</td></tr>`;
}

function claimDetail(c) {
  const a = c.authenticity || {};
  const checks = Object.entries(a.checks || {}).map(([k, v]) => checkRow(k, v)).join("");
  const dmg = (c.damage_summary.elements || [])
    .map(d => `${esc(d.element)} ${d.severity}`).join(", ") || "none detected";
  const an = c.building_analysis || {};
  const orn = an.ornateness ? `${an.ornateness.score}${an.ornateness.evidence.length ? " (" + esc(an.ornateness.evidence.join(", ")) + ")" : ""}` : "off";
  return `<div class="box">
    <b>${esc(c.claim_id)}</b> &middot; rank ${c.priority_rank} &middot;
    <span class="badge" style="background:${REC[c.recommendation]}">${REC_LABEL[c.recommendation]}</span>
    ${c.requires_human_confirmation ? " &middot; needs human confirmation" : ""}
    <div>Building ${esc(c.building_id)} &middot; ${esc(c.band || "-")} &middot; insured ${fmt(c.insured_value)}</div>
    <div>Severity ${c.damage_summary.overall_severity} (${esc(c.damage_summary.basis)}) &middot; priority score ${c.priority_score}</div>
    <div>Damage: ${dmg}</div>
    <div>Ornateness: ${orn} &middot; rebuild cost modifier ${an.replacement_cost_modifier} &middot; vision mode: ${esc(an.mode)}</div>
    <div><b>Why:</b> ${esc((c.reasoning || []).join(" "))}</div>
    <div style="margin-top:6px"><b>Authenticity</b>: ${a.enabled === false ? "disabled by flag" : "risk " + a.manipulation_risk + " &rarr; " + esc(a.route)}</div>
    <table>${checks}</table>
    ${c.test_label && c.test_label !== "honest" ? `<div class="note">test label: ${esc(c.test_label)} (mock data only)</div>` : ""}
  </div>`;
}

function selectClaim(c) {
  selectedId = c.claim_id;
  document.getElementById("detail").innerHTML = claimDetail(c);
  document.querySelectorAll(".q").forEach(el => el.classList.toggle("sel", el.dataset.id === c.claim_id));
  const m = markers[c.building_id];
  if (m) {
    map.setView(m.getLatLng(), Math.max(map.getZoom(), 12));
    m.openPopup();
  }
}

function renderQueue() {
  const f = document.getElementById("filter").value;
  const list = claims.filter(c => !f || c.recommendation === f);
  document.getElementById("qcount").textContent = `${list.length} of ${claims.length} claims`;
  const el = document.getElementById("queue");
  el.innerHTML = list.slice(0, 200).map(c => {
    const risk = c.authenticity.manipulation_risk;
    return `<div class="q${c.claim_id === selectedId ? " sel" : ""}" data-id="${esc(c.claim_id)}">
      <span class="rank">#${c.priority_rank}</span><span class="id">${esc(c.claim_id)}</span>
      <span class="meta">${esc(c.band || "-")} &middot; sev ${c.damage_summary.overall_severity}${risk != null ? " &middot; risk " + risk : ""}</span>
      <span class="badge" style="background:${REC[c.recommendation]}">${REC_LABEL[c.recommendation]}</span></div>`;
  }).join("") || "<div class='q'>No claims. Run scripts/run_pipeline.py</div>";
  el.querySelectorAll(".q[data-id]").forEach(div =>
    div.addEventListener("click", () => selectClaim(claims.find(c => c.claim_id === div.dataset.id))));
}

async function load() {
  const [data, claimsData] = await Promise.all([
    fetch("/data/fixtures/map_data.json").then(r => r.json()),
    fetch("/data/fixtures/claims.json").then(r => (r.ok ? r.json() : [])).catch(() => []),
  ]);
  claims = claimsData;

  data.events.forEach(e => {
    ["moderate", "high", "extreme"].forEach(name => {
      const b = e.severity_bands.find(x => x.band === name);
      const poly = L.polygon(ring(b.geometry), {
        color: COLORS[name], weight: 1, fillColor: COLORS[name], fillOpacity: 0.22,
      }).bindTooltip(`${e.hazard_type} - ${name}${e.is_simulated ? " (simulated)" : ""}`);
      poly.addTo(map);
      all.addLayer(poly);
    });
    if (e.projection) {
      projLayer.addLayer(L.polygon(ring(e.projection), {
        color: COLORS.projected, weight: 2, dashArray: "6 6", fill: false,
      }).bindTooltip(`${e.hazard_type} projection (estimate)`));
    }
    const s = data.summaries[e.event_id];
    const rows = Object.entries(s.by_band)
      .map(([band, v]) => `<tr><td>${band}</td><td>${v.count}</td><td>${fmt(v.insured_value)}</td></tr>`).join("");
    eventsEl.insertAdjacentHTML("beforeend",
      `<h2>${e.hazard_type}${e.is_simulated ? " (simulated)" : ""}: ${esc(e.event_id)}</h2>
       <div>${s.total_buildings} buildings, ${fmt(s.total_insured_value)} insured value</div>
       <table><tr><th>Band</th><th>Count</th><th>Value</th></tr>${rows}</table>`);
  });

  data.buildings.forEach(b => {
    const hit = !!b.band;
    const style = {
      radius: hit ? 5 : 3, weight: 1,
      color: hit ? COLORS[b.band] : "#78909c",
      fillColor: hit ? COLORS[b.band] : "#78909c", fillOpacity: 0.85,
    };
    const marker = L.circleMarker([b.lat, b.lng], style).bindPopup(buildingPopup(b));
    markers[b.building_id] = marker;
    baseStyle[b.building_id] = style;
    (hit ? hitLayer : safeLayer).addLayer(marker);
    all.addLayer(marker);
  });

  claims.forEach(c => {                       // outline = recommendation
    const m = markers[c.building_id];
    if (!m) return;
    m.setStyle({ color: REC[c.recommendation], weight: 3, radius: 6 });
    m.on("click", () => selectClaim(c));
  });

  if (claims.length) {
    const snap = claims[0].flags_snapshot || {};
    const notes = [];
    if (snap["vision.mode"] === "mock") notes.push("vision: <b>mock</b> (simulated, not from images)");
    if (snap["auth.enabled"] === false) notes.push("authenticity checks: <b>off</b>");
    notes.push(`dispatch: <b>${esc(snap["dispatch.priority_mode"])}</b>`);
    document.getElementById("banner").innerHTML = `<div class="banner">${notes.join(" &middot; ")}</div>`;
  } else {
    document.getElementById("banner").innerHTML =
      `<div class="banner">No claims yet. Run <code>python scripts\\run_pipeline.py</code>.</div>`;
  }

  renderQueue();
  map.invalidateSize();
  map.fitBounds(all.getBounds().pad(0.05), { maxZoom: 11 });
}

load().catch(err => {
  eventsEl.insertAdjacentHTML("beforeend",
    `<p style='color:#b71c1c;font-size:12px'>Failed to draw the map: ${esc(err.message)}. Press F12 and check the Console.</p>`);
  console.error(err);
});

document.getElementById("filter").addEventListener("change", renderQueue);
document.getElementById("t-proj").addEventListener("change", e =>
  e.target.checked ? projLayer.addTo(map) : map.removeLayer(projLayer));
document.getElementById("t-safe").addEventListener("change", e =>
  e.target.checked ? safeLayer.addTo(map) : map.removeLayer(safeLayer));