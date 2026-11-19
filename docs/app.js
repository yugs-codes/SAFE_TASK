(() => {
  "use strict";
  const D = window.DATA;
  const $ = (s) => document.querySelector(s);
  if (!D) {
    $("#cards").textContent = "data.js is missing. Run python pipeline/run.py --offline to build it.";
    return;
  }

  // ---------- helpers (all data goes in through textContent, never innerHTML)
  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "style") Object.assign(n.style, v);
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids.flat()) if (k != null && k !== false) n.append(k instanceof Node ? k : String(k));
    return n;
  }
  function svg(tag, attrs = {}, ...kids) {
    const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs)) if (v != null) n.setAttribute(k, v);
    for (const k of kids) n.append(k instanceof Node ? k : document.createTextNode(String(k)));
    return n;
  }
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const fmtDate = (iso, precision = "day") => {
    if (!iso) return "undated";
    const [y, m, d] = iso.split("-").map(Number);
    if (precision === "year") return String(y);
    if (precision === "month") return `${MON[m - 1]} ${y}`;
    return `${d} ${MON[m - 1]} ${y}`;
  };
  const nf = new Intl.NumberFormat("en-IN");
  const count = (arr, key) => arr.reduce((m, x) => ((m[x[key]] = (m[x[key]] || 0) + 1), m), {});
  const STAGE = { proposed: "Proposed", announced: "Announced", implemented: "Implemented", unknown: "Unclear" };
  const CONF = { high: "High", medium: "Medium", low: "Low" };
  const DOTS = { high: "●●●", medium: "●●○", low: "●○○" };
  const GROUP = { adopted: "Adopted / in force", in_progress: "Draft, proposed or announced", inactive: "Lapsed or superseded" };
  const ANNOT = [
    { code: "TN", month: "2026-05", label: "New CM, 10 May 2026" },
    { code: "KA", month: "2026-05", label: "CM resigned, 28 May 2026" },
  ];
  const events = D.events;
  const insts = D.instruments;
  const focus = D.focus;
  const stateInfo = Object.fromEntries(D.states.map((s) => [s.code, s]));
  const levelColor = (l) => (l ? `var(--l${l})` : "var(--none)");

  // ---------- tooltip
  const tip = $("#tip");
  function showTip(e, ...lines) {
    tip.replaceChildren(...lines.map((l, i) => (i === 0 ? el("strong", {}, l) : el("div", {}, l))));
    tip.hidden = false;
    const x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    const y = e.clientY + 16 + tip.offsetHeight > window.innerHeight ? e.clientY - tip.offsetHeight - 10 : e.clientY + 16;
    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;
  }
  const hideTip = () => (tip.hidden = true);

  // ---------- filter state shared by cards, matrix, map and table
  const F = { tab: "events", state: "", category: "", stage: "", confidence: "", group: "", q: "", limit: 50 };
  function go(patch) {
    Object.assign(F, { limit: 50 }, patch);
    renderTable();
    renderCards();
    $("#records").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---------- header
  $("#meta").textContent = `Updated ${fmtDate(D.last_updated.slice(0, 10))} · Dataset ${D.version} · ${nf.format(events.length)} news events · ${nf.format(insts.length)} policy instruments in ${D.states.filter((s) => s.instruments).length} states and UTs`;
  $("#footer-meta").textContent = `Dataset ${D.version}. News since ${fmtDate(D.start_date)}. Policy instruments: ${D.instrument_provenance}.`;

  // ---------- focus cards
  function renderCards() {
    const box = $("#cards");
    box.replaceChildren(...focus.map((f) => {
      const evs = events.filter((e) => e.code === f.code);
      const cats = Object.entries(count(evs, "category")).filter(([c]) => c !== "other").sort((a, b) => b[1] - a[1]);
      const s = stateInfo[f.code] || { level: 0, level_label: "" };
      const pressed = F.state === f.name && F.tab === "events";
      return el("button", {
        class: "card", "aria-pressed": String(pressed),
        onclick: () => go({ tab: "events", state: pressed ? "" : f.name, category: "" }),
      },
        el("div", { class: "name" }, f.name),
        el("div", { class: "num" }, nf.format(evs.length)),
        el("div", { class: "unit" }, "news events"),
        el("div", { class: "line" }, el("span", { class: "swatch", style: { background: levelColor(s.level) } }), s.level_label),
        el("div", { class: "line" }, cats.length ? `Most often: ${D.categories[cats[0][0]]}` : "No events yet"),
      );
    }));
  }

  // ---------- tile map
  let selectedTile = null;
  function renderMap() {
    const box = $("#tiles");
    box.replaceChildren(...D.states.filter((s) => s.tile).map((s) => el("button", {
      class: `tile${s.focus ? " focus" : ""}`, "data-level": s.level, "aria-pressed": String(selectedTile === s.code),
      "aria-label": `${s.name}: ${s.level_label}, ${s.instruments} instruments`,
      style: { gridColumn: s.tile[0] + 1, gridRow: s.tile[1] + 1 },
      onclick: () => { selectedTile = selectedTile === s.code ? null : s.code; renderMap(); renderDetail(); },
      onpointermove: (e) => showTip(e, s.name, s.level_label, `${s.instruments} AI instrument${s.instruments === 1 ? "" : "s"}`),
      onpointerleave: hideTip,
    }, s.code)));
    $("#map-legend").replaceChildren(
      ...[3, 2, 1, 0].map((l) => el("li", {}, el("span", { class: "swatch", style: { background: levelColor(l) } }), D.levels[l])),
      el("li", {}, el("span", { class: "swatch", style: { boxShadow: "inset 0 0 0 2px var(--ink)" } }), "Focus state"),
    );
  }
  function renderDetail() {
    const box = $("#map-detail");
    if (!selectedTile) {
      const byLevel = count(D.states, "level");
      box.replaceChildren(
        el("h3", {}, `${D.states.length} states and union territories`),
        el("p", { class: "sub" }, "Select a tile to see its instruments."),
        el("table", { class: "levels" }, el("tbody", {}, ...[3, 2, 1, 0].map((l) =>
          el("tr", {}, el("td", {}, el("span", { class: "swatch", style: { background: levelColor(l), marginRight: "8px" } }), D.levels[l]), el("td", { class: "n" }, byLevel[l] || 0))))),
      );
      return;
    }
    const s = stateInfo[selectedTile];
    const items = insts.filter((i) => i.code === selectedTile).sort((a, b) => (a.date < b.date ? 1 : -1));
    const evs = events.filter((e) => e.code === selectedTile);
    box.replaceChildren(
      el("h3", {}, s.name),
      el("p", { class: "sub" }, `${s.level_label} · ${items.length} instrument${items.length === 1 ? "" : "s"}${s.focus ? ` · ${evs.length} news events` : ""}`),
      items.length ? el("ul", {}, ...items.slice(0, 8).map((i) => el("li", {},
        el("a", { class: "t", href: i.url, target: "_blank", rel: "noopener" }, i.title),
        el("span", { class: "m" }, `${fmtDate(i.date, i.precision)} · ${i.status.replace("-", " ")} · ${CONF[i.confidence]} confidence`)))) : el("p", {}, "No AI instrument found in the dataset."),
      el("p", {}, items.length > 8 ? el("a", { href: "#records", onclick: (e) => { e.preventDefault(); go({ tab: "instruments", state: s.name }); } }, `All ${items.length} instruments`) : null,
        s.focus && evs.length ? el("span", {}, items.length > 8 ? " · " : "", el("a", { href: "#records", onclick: (e) => { e.preventDefault(); go({ tab: "events", state: s.name }); } }, `${evs.length} news events`)) : null),
    );
  }

  // ---------- matrix
  function renderMatrix() {
    const cats = Object.keys(D.categories);
    const grid = focus.map((f) => cats.map((c) => events.filter((e) => e.code === f.code && e.category === c).length));
    const max = Math.max(1, ...grid.flat());
    const step = (n) => (n === 0 ? 0 : Math.min(6, 1 + Math.floor((n / max) * 5.999)));
    $("#matrix").replaceChildren(
      el("colgroup", {}, el("col", { class: "rowhead" }), ...cats.map(() => el("col")), el("col", { class: "totcol" })),
      el("thead", {}, el("tr", {}, el("th", {}, ""), ...cats.map((c) => el("th", { scope: "col" }, D.categories[c])), el("th", { scope: "col" }, "Total"))),
      el("tbody", {}, ...focus.map((f, r) => el("tr", {},
        el("th", { scope: "row" }, f.name),
        ...cats.map((c, k) => {
          const n = grid[r][k];
          const st = step(n);
          return el("td", {
            class: n ? "" : "zero",
            style: n ? { background: `var(--seq-${st})`, color: st >= 4 ? "var(--seq-ink-hi)" : "var(--ink)" } : {},
            tabindex: n ? "0" : null,
            onpointermove: n ? (e) => showTip(e, `${n} event${n === 1 ? "" : "s"}`, `${f.name} · ${D.categories[c]}`) : null,
            onpointerleave: hideTip,
            onclick: n ? () => go({ tab: "events", state: f.name, category: c }) : null,
            onkeydown: n ? (e) => { if (e.key === "Enter") go({ tab: "events", state: f.name, category: c }); } : null,
          }, n || "·");
        }),
        el("td", { class: "total" }, grid[r].reduce((a, b) => a + b, 0)),
      ))),
    );
  }

  // ---------- small multiples
  function months() {
    const out = [];
    let [y, m] = D.start_date.split("-").map(Number);
    const [ey, em] = D.last_updated.slice(0, 7).split("-").map(Number);
    while (y < ey || (y === ey && m <= em)) {
      out.push(`${y}-${String(m).padStart(2, "0")}`);
      m === 12 ? ((y += 1), (m = 1)) : (m += 1);
    }
    return out;
  }
  function renderMultiples() {
    const box = $("#multiples");
    const ms = months();
    const series = focus.map((f) => ms.map((mo) => events.filter((e) => e.code === f.code && e.date.startsWith(mo)).length));
    const max = Math.max(1, ...series.flat());
    const probe = el("div", { class: "mrow" }, el("div"), el("div", { id: "probe" }), el("div"));
    box.replaceChildren(probe);
    const W = Math.max(240, probe.children[1].clientWidth || 800);
    const H = 64;
    const slot = W / ms.length;
    const bw = Math.min(24, slot * 0.7);
    const rows = focus.map((f, r) => {
      const g = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${f.name}: news events per month` });
      g.append(svg("line", { class: "base", x1: 0, x2: W, y1: H - 0.5, y2: H - 0.5 }));
      for (const a of ANNOT.filter((a) => a.code === f.code)) {
        const i = ms.indexOf(a.month);
        if (i < 0) continue;
        const x = i * slot + slot / 2;
        g.append(svg("line", { class: "marker", x1: x, x2: x, y1: 0, y2: H }));
        g.append(svg("text", { x: x + 4, y: 10 }, a.label));
      }
      series[r].forEach((n, i) => {
        if (!n) return;
        const h = Math.max(2, (n / max) * (H - 14));
        const x = i * slot + (slot - bw) / 2;
        const y = H - h;
        const rr = Math.min(4, h / 2, bw / 2);
        const d = `M${x},${H}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + bw - rr}Q${x + bw},${y} ${x + bw},${y + rr}V${H}Z`;
        const [yy, mm] = ms[i].split("-").map(Number);
        const p = svg("path", { class: "bar", d });
        p.addEventListener("pointermove", (e) => showTip(e, `${n} event${n === 1 ? "" : "s"}`, `${f.name} · ${MON[mm - 1]} ${yy}`));
        p.addEventListener("pointerleave", hideTip);
        g.append(p);
      });
      return el("div", { class: "mrow" }, el("div", { class: "lab" }, f.name), el("div", {}, g), el("div", { class: "tot" }, series[r].reduce((a, b) => a + b, 0)));
    });
    const ax = svg("svg", { viewBox: `0 0 ${W} 20`, "aria-hidden": "true" });
    ms.forEach((mo, i) => {
      const [y, m] = mo.split("-").map(Number);
      if ((m - 1) % 3) return;
      ax.append(svg("text", { x: i * slot + slot / 2, y: 14, "text-anchor": "middle" }, m === 1 ? `${MON[0]} ${y}` : MON[m - 1]));
    });
    box.replaceChildren(...rows, el("div", { class: "mrow axis-row" }, el("div", { class: "lab small" }, `Tallest bar: ${max}`), el("div", {}, ax), el("div")));
  }

  // ---------- funnel
  function renderFunnel() {
    const st = D.funnel.stages;
    const top = st[0].count || 1;
    $("#funnel").replaceChildren(...st.map((s, i) => el("div", {
      class: "frow",
      onpointermove: (e) => showTip(e, `${nf.format(s.count)} ${s.label.toLowerCase()}`, ...focus.map((f) => `${f.name}: ${nf.format(D.funnel.per_state[f.code][s.key])}`)),
      onpointerleave: hideTip,
    },
      el("div", {}, s.label),
      el("div", { class: "track" }, el("div", { class: "fill", style: { width: `${(s.count / top) * 100}%` } })),
      el("div", { class: "n" }, nf.format(s.count), i ? el("div", { class: "pct" }, `${Math.round((s.count / (st[i - 1].count || 1)) * 100)}% kept`) : null),
    )));
    const names = { no_ai_term: "no AI term", no_gov_term: "no state-government signal", excluded: "private-sector phrase", central_only: "central government only", out_of_scope_state: "another state", out_of_window: "before 2025", override: "manual correction" };
    const drops = Object.entries(D.funnel.dropped).sort((a, b) => b[1] - a[1]);
    $("#drops").textContent = `Dropped, by reason: ${drops.map(([k, v]) => `${names[k] || k} ${nf.format(v)}`).join(" · ")}. ${D.funnel.note}`;
  }

  // ---------- records table
  function filtersUI() {
    const box = $("#filters");
    const isEv = F.tab === "events";
    const opt = (v, label, sel) => el("option", { value: v, selected: v === sel }, label);
    const select = (key, label, options) => el("select", { "aria-label": label, onchange: (e) => { F[key] = e.target.value; F.limit = 50; renderTable(); renderCards(); } },
      opt("", label, F[key]), ...options.map(([v, l]) => opt(v, l, F[key])));
    const stateNames = isEv ? focus.map((f) => f.name) : [...new Set(insts.map((i) => i.state))].sort();
    const parts = [select("state", "All states", stateNames.map((n) => [n, n]))];
    if (isEv) {
      parts.push(select("category", "All categories", Object.entries(D.categories)));
      parts.push(select("stage", "All stages", Object.entries(STAGE)));
    } else {
      parts.push(select("group", "All statuses", Object.entries(GROUP)));
    }
    parts.push(select("confidence", "Any confidence", Object.entries(CONF)));
    const q = el("input", { type: "search", placeholder: "Search titles", value: F.q, "aria-label": "Search titles" });
    q.addEventListener("input", (e) => { F.q = e.target.value; F.limit = 50; renderRows(); });
    parts.push(q, el("button", { type: "button", onclick: () => { Object.assign(F, { state: "", category: "", stage: "", confidence: "", group: "", q: "", limit: 50 }); renderTable(); renderCards(); } }, "Clear"));
    box.replaceChildren(...parts);
  }
  function rowsFor() {
    const q = F.q.trim().toLowerCase();
    if (F.tab === "events") {
      return events.filter((e) => (!F.state || e.state === F.state) && (!F.category || e.category === F.category)
        && (!F.stage || e.stage === F.stage) && (!F.confidence || e.confidence === F.confidence)
        && (!q || e.title.toLowerCase().includes(q)));
    }
    return insts.filter((i) => (!F.state || i.state === F.state) && (!F.group || i.group === F.group)
      && (!F.confidence || i.confidence === F.confidence) && (!q || i.title.toLowerCase().includes(q)))
      .sort((a, b) => (a.date < b.date ? 1 : -1));
  }
  const conf = (level, note) => el("span", { class: "conf", title: note }, el("span", { class: "dots", "aria-hidden": "true" }, DOTS[level]), " ", CONF[level]);
  function fixLink(title, id) {
    if (!D.repo_url) return null;
    const u = `${D.repo_url}/issues/new?title=${encodeURIComponent(`Correction: ${title}`)}&body=${encodeURIComponent(`Record id: ${id}\n\nWhat is wrong:\n\nSource:\n`)}`;
    return el("div", { class: "fix" }, el("a", { href: u, target: "_blank", rel: "noopener" }, "Report a correction"));
  }
  function renderRows() {
    const rows = rowsFor();
    const shown = rows.slice(0, F.limit);
    const isEv = F.tab === "events";
    const head = isEv ? ["Date", "State", "Event", "Category", "Stage", "Confidence"] : ["Date", "State", "Instrument", "Type", "Status", "Confidence"];
    const body = shown.map((r) => isEv
      ? el("tr", {},
        el("td", { class: "date" }, fmtDate(r.date)),
        el("td", {}, r.state),
        el("td", { class: "title" },
          el("a", { href: r.url, target: "_blank", rel: "noopener" }, r.title),
          el("div", { class: "summary" }, `${r.source}${r.flags.length ? ` · ${r.flags.join(", ").replace(/_/g, " ")}` : ""}`),
          r.members.length > 1 ? el("details", {}, el("summary", {}, `${r.n} outlets · ${r.members.length} articles`),
            el("ul", {}, ...r.members.map((m) => el("li", {}, el("a", { href: m.u, target: "_blank", rel: "noopener" }, m.t), ` · ${m.s} · ${fmtDate(m.d)}`)))) : null,
          fixLink(r.title, r.id)),
        el("td", {}, D.categories[r.category]),
        el("td", {}, STAGE[r.stage]),
        el("td", {}, conf(r.confidence, r.confidence_note)))
      : el("tr", {},
        el("td", { class: "date" }, fmtDate(r.date, r.precision)),
        el("td", {}, r.state),
        el("td", { class: "title" },
          el("a", { href: r.url, target: "_blank", rel: "noopener" }, r.title),
          el("div", { class: "summary" }, r.summary.length > 220 ? `${r.summary.slice(0, 217)}…` : r.summary),
          fixLink(r.title, r.id)),
        el("td", {}, r.type.replace(/-/g, " ")),
        el("td", {}, r.status.replace(/-/g, " ")),
        el("td", {}, conf(r.confidence, r.confidence_note))));
    $("#table").replaceChildren(el("thead", {}, el("tr", {}, ...head.map((h) => el("th", { scope: "col" }, h)))), el("tbody", {}, ...body));
    $("#count").textContent = `Showing ${nf.format(shown.length)} of ${nf.format(rows.length)} ${isEv ? "news events" : "policy instruments"}`;
    const more = $("#more");
    more.hidden = rows.length <= F.limit;
    more.onclick = () => { F.limit += 50; renderRows(); };
  }
  function renderTable() {
    $("#tab-events").setAttribute("aria-selected", String(F.tab === "events"));
    $("#tab-inst").setAttribute("aria-selected", String(F.tab === "instruments"));
    $("#tab-events").textContent = `News events (${nf.format(events.length)})`;
    $("#tab-inst").textContent = `Policy instruments (${nf.format(insts.length)})`;
    filtersUI();
    renderRows();
  }
  $("#tab-events").addEventListener("click", () => { Object.assign(F, { tab: "events", group: "", limit: 50 }); if (F.state && !focus.some((f) => f.name === F.state)) F.state = ""; renderTable(); renderCards(); });
  $("#tab-inst").addEventListener("click", () => { Object.assign(F, { tab: "instruments", category: "", stage: "", limit: 50 }); renderTable(); renderCards(); });

  renderCards();
  renderMap();
  renderDetail();
  renderMatrix();
  renderMultiples();
  renderFunnel();
  renderTable();
  let t;
  window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(renderMultiples, 150); });
})();
