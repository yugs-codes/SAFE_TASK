(() => {
  "use strict";
  const D = window.DATA;
  const M = window.INDIA_MAP;
  const $ = (s) => document.querySelector(s);
  if (!D || !M) {
    $("#lead").textContent = "The data files are missing. Run python pipeline/run.py --offline to build them.";
    return;
  }

  // ---------- helpers (data always goes in through textContent, never innerHTML)
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
  const N = (n) => nf.format(n);
  const plural = (n, one, many = `${one}s`) => `${N(n)} ${n === 1 ? one : many}`;
  const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
  const word = (n) => WORDS[n] || N(n);
  const count = (arr, key) => arr.reduce((m, x) => ((m[x[key]] = (m[x[key]] || 0) + 1), m), {});
  const STAGE = { proposed: "Proposed", announced: "Announced", implemented: "Implemented", unknown: "Unclear" };
  const CONF = { high: "High", medium: "Medium", low: "Low" };
  const DOTS = { high: "●●●", medium: "●●○", low: "●○○" };
  const GROUP = { adopted: "In place", in_progress: "In the works", inactive: "Lapsed or replaced" };
  const POLICY_TYPES = new Set(["policy", "strategy", "mission", "framework"]);
  const ANNOT = [
    { code: "TN", month: "2026-05", label: "New CM, 10 May 2026" },
    { code: "KA", month: "2026-05", label: "CM resigned, 28 May 2026" },
  ];
  // Plain label for tables, a human title and one line for the explainer cards, and a phrase for sentences.
  const CAT = {
    regulation_ethics: { title: "Rules of the road", what: "Guidelines, ethics codes and rules on things like deepfakes.", doing: "writing rules" },
    budget_funding: { title: "Follow the money", what: "Budget lines and money set aside for AI. The clearest sign a state means it.", doing: "putting money down" },
    policy_mission: { title: "The big plans", what: "AI policies, missions and roadmaps that set the direction.", doing: "drawing up big plans" },
    institution: { title: "Bricks and mortar", what: "Centres of excellence, AI cities, labs and data centres.", doing: "building things" },
    partnership_mou: { title: "Deals on the table", what: "MoUs and tie-ups with companies and universities. Easy to sign, harder to deliver.", doing: "signing deals" },
    skilling: { title: "Back to school", what: "Training officials, students and citizens to use AI.", doing: "training people" },
    governance_deployment: { title: "AI at work", what: "Government actually using AI: in hospitals, police stations, farms and offices.", doing: "putting AI to work" },
    other: { title: "Everything else", what: "Speeches, summits and stories that don't fit one bucket.", doing: "other news" },
  };
  const events = D.events;
  const insts = D.instruments;
  const focus = D.focus;
  const stateInfo = Object.fromEntries(D.states.map((s) => [s.code, s]));
  const levelColor = (l) => (l ? `var(--l${l})` : "var(--none)");
  const stages = Object.fromEntries(D.funnel.stages.map((s) => [s.key, s.count]));

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

  // ---------- shared filter state for cards, matrix, map and table
  const F = { tab: "events", state: "", category: "", stage: "", confidence: "", group: "", check: "", q: "", limit: 50 };
  function go(patch) {
    Object.assign(F, { state: "", category: "", stage: "", confidence: "", group: "", check: "", q: "", limit: 50 }, patch);
    renderTable();
    renderCards();
    $("#records").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---------- header
  $("#lead").textContent = `Every state says it wants to lead on AI. We went through ${N(stages.raw)} news search results and ${N(insts.length)} government documents to see who is actually doing something about it.`;
  $("#meta").textContent = `Updated ${fmtDate(D.last_updated.slice(0, 10))} · ${N(events.length)} news events in five states · ${N(insts.length)} policy documents across ${D.states.filter((s) => s.instruments).length} states and UTs`;
  $("#footer-meta").textContent = `Dataset ${D.version}. News since ${fmtDate(D.start_date)}; policy documents from ${D.instrument_provenance}. Map boundaries are approximate and for illustration only.`;

  // ---------- the map
  const byCode = Object.fromEntries(M.states.map((s) => [s.code, s]));
  const FULL = [0, 0, M.w, M.h];
  const map = $("#india");
  let view = FULL.slice();
  let sel = null;
  let anim = 0;
  const marks = {};
  const labels = [];
  const dots = [];

  function applyView(v) {
    view = v;
    map.setAttribute("viewBox", v.map((x) => x.toFixed(1)).join(" "));
    const k = v[2] / M.w;
    labels.forEach((t) => t.setAttribute("font-size", (17 * k).toFixed(2)));
    dots.forEach((c) => c.setAttribute("r", (8 * k).toFixed(2)));
  }
  function animateTo(target) {
    cancelAnimationFrame(anim);
    const from = view.slice();
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dur = reduce ? 0 : 480;
    const t0 = performance.now();
    const step = (now) => {
      const t = dur ? Math.min(1, (now - t0) / dur) : 1;
      const e = 1 - Math.pow(1 - t, 3);
      applyView(from.map((f, i) => f + (target[i] - f) * e));
      if (t < 1) anim = requestAnimationFrame(step);
    };
    anim = requestAnimationFrame(step);
  }
  function boxFor(code) {
    const [x0, y0, x1, y1] = byCode[code].bbox;
    const ar = M.h / M.w;
    let w = Math.max((x1 - x0) * 1.7, 200);
    let h = Math.max((y1 - y0) * 1.7, 200 * ar);
    if (h / w > ar) w = h / ar; else h = w * ar;
    const cx = (x0 + x1) / 2;
    const cy = (y0 + y1) / 2;
    return [cx - w / 2, cy - h / 2, w, h];
  }
  function tipFor(e, code) {
    const s = stateInfo[code];
    const evs = events.filter((x) => x.code === code).length;
    showTip(e, s.name, s.level_label, `${plural(s.instruments, "policy document")}${s.focus ? ` · ${plural(evs, "news event")}` : ""}`);
  }
  function select(code) {
    sel = code;
    map.classList.toggle("zoomed", !!code);
    Object.entries(marks).forEach(([c, nodes]) => nodes.forEach((n) => n.classList.toggle("sel", c === code)));
    $("#jump").value = code || "";
    animateTo(code ? boxFor(code) : FULL);
    renderPanel();
  }
  function buildMap() {
    const gShapes = svg("g");
    const gOutline = svg("g");
    const gDots = svg("g");
    const gLabels = svg("g");
    for (const s of M.states) {
      const info = stateInfo[s.code];
      if (!info) continue;
      const lvl = info.level;
      const hit = { onclick: (e) => { e.stopPropagation(); select(sel === s.code ? null : s.code); } };
      marks[s.code] = [];
      if (s.d) {
        const p = svg("path", { d: s.d, class: `st l${lvl}`, "data-code": s.code });
        p.addEventListener("click", hit.onclick);
        p.addEventListener("pointermove", (e) => tipFor(e, s.code));
        p.addEventListener("pointerleave", hideTip);
        gShapes.append(p);
        marks[s.code].push(p);
        if (info.focus) {
          const o = svg("path", { d: s.d, class: "outline" });
          gOutline.append(o);
          marks[s.code].push(o);
        }
      }
      if (s.area < 400) {
        const c = svg("circle", { cx: s.c[0], cy: s.c[1], r: 6, class: `dot l${lvl}${info.focus ? " focus" : ""}` });
        c.addEventListener("click", hit.onclick);
        c.addEventListener("pointermove", (e) => tipFor(e, s.code));
        c.addEventListener("pointerleave", hideTip);
        gDots.append(c);
        dots.push(c);
        marks[s.code].push(c);
      }
      if (s.area >= 2500) {
        const t = svg("text", { x: s.c[0], y: s.c[1], "dominant-baseline": "central", class: `lbl l${lvl}` }, s.code);
        gLabels.append(t);
        labels.push(t);
        marks[s.code].push(t);
      }
    }
    map.replaceChildren(gShapes, gOutline, gDots, gLabels);
    map.addEventListener("click", () => sel && select(null));
    applyView(FULL);

    const jump = $("#jump");
    jump.replaceChildren(el("option", { value: "" }, "All of India"),
      ...D.states.slice().sort((a, b) => a.name.localeCompare(b.name)).map((s) => el("option", { value: s.code }, s.name)));
    jump.addEventListener("change", () => select(jump.value || null));
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && sel) select(null); });

    $("#map-legend").replaceChildren(
      ...[3, 2, 1, 0].map((l) => el("li", {}, el("span", { class: "swatch", style: { background: levelColor(l) } }), D.levels[l])),
      el("li", {}, el("span", { class: "swatch", style: { boxShadow: "inset 0 0 0 2px var(--ink)" } }), "One of our five focus states"),
    );
    const byLevel = count(D.states, "level");
    const n3 = byLevel[3] || 0, n2 = byLevel[2] || 0, n1 = byLevel[1] || 0, n0 = byLevel[0] || 0;
    $("#map-take").textContent = `${N(n3)} states and UTs have an AI policy in place. ${N(n2)} more have one drafted or announced, ${N(n1)} are running AI projects without a policy, and ${N(n0)} have nothing on record yet.`;
  }

  function rankedDocs(code) {
    // The state's own AI policy first, then whatever is in force, newest first.
    const rank = (i) => [i.aip ? 1 : 0, i.group === "adopted" ? 1 : 0, POLICY_TYPES.has(i.type) ? 1 : 0, i.date];
    return insts.filter((i) => i.code === code).sort((a, b) => {
      const ra = rank(a), rb = rank(b);
      for (let k = 0; k < ra.length; k++) if (ra[k] !== rb[k]) return ra[k] < rb[k] ? 1 : -1;
      return 0;
    });
  }
  function renderPanel() {
    const box = $("#panel");
    if (!sel) {
      const byLevel = count(D.states, "level");
      box.replaceChildren(
        el("p", { class: "over" }, "All of India"),
        el("h3", {}, "Pick a state"),
        el("p", { class: "headline" }, "Click any state or territory on the map, or use the list above it. The map zooms in and the details show up here."),
        el("table", { class: "levels" }, el("tbody", {}, ...[3, 2, 1, 0].map((l) =>
          el("tr", {}, el("td", {}, el("span", { class: "swatch", style: { background: levelColor(l), marginRight: "8px" } }), D.levels[l]), el("td", { class: "n" }, byLevel[l] || 0))))),
      );
      return;
    }
    const s = stateInfo[sel];
    const docs = rankedDocs(sel);
    const evs = events.filter((e) => e.code === sel);
    const kind = s.type === "ut" ? "Union territory" : "State";
    const stats = [
      [docs.length, "policy documents"],
      [docs.filter((d) => d.group === "adopted").length, "in place"],
      [docs.filter((d) => d.group === "in_progress").length, "in the works"],
    ];
    if (s.focus) stats.push([evs.length, "news events"]);
    box.replaceChildren(
      el("p", { class: "over" }, s.focus ? `${kind} · one of our focus states` : kind),
      el("h3", {}, s.name),
      el("div", { class: "stats" }, ...stats.map(([n, l]) => el("div", {}, el("b", {}, N(n)), el("span", {}, l)))),
      el("p", { class: "headline" }, el("span", { class: "swatch", style: { background: levelColor(s.level), marginRight: "8px" } }),
        s.level_label, s.headline_instrument ? `: ${s.headline_instrument}` : ""),
      docs.length ? el("h4", {}, "What's on paper") : el("p", {}, "We found no AI policy document for this one."),
      docs.length ? el("ul", {}, ...docs.slice(0, 5).map((d) => el("li", {},
        el("a", { href: d.url, target: "_blank", rel: "noopener" }, d.title),
        el("span", { class: "m" }, el("span", { class: `chip${d.group === "adopted" ? " ok" : ""}` }, GROUP[d.group] || d.status), `${fmtDate(d.date, d.precision)} · ${CONF[d.confidence]} confidence`)))) : null,
      docs.length > 5 ? el("p", {}, el("button", { class: "linkbtn", onclick: () => go({ tab: "instruments", state: s.name }) }, `See all ${docs.length} documents`)) : null,
      ...(s.focus && evs.length ? [
        el("h4", {}, "Latest in the news"),
        el("ul", {}, ...evs.slice(0, 3).map((e) => el("li", {},
          el("a", { href: e.url, target: "_blank", rel: "noopener" }, e.title),
          el("span", { class: "m" }, `${fmtDate(e.date)} · ${e.source}`)))),
        el("p", {}, el("button", { class: "linkbtn", onclick: () => go({ tab: "events", state: s.name }) }, `Read all ${evs.length} stories`)),
      ] : []),
      el("button", { class: "back", onclick: () => select(null) }, "Back to the whole map"),
    );
  }

  // ---------- five focus states
  function renderCards() {
    $("#cards").replaceChildren(...focus.map((f) => {
      const evs = events.filter((e) => e.code === f.code);
      const cats = Object.entries(count(evs, "category")).filter(([c]) => c !== "other").sort((a, b) => b[1] - a[1]);
      const s = stateInfo[f.code] || { level: 0, level_label: "" };
      const pressed = F.state === f.name && F.tab === "events";
      return el("button", {
        class: "card", "aria-pressed": String(pressed),
        onclick: () => go({ tab: "events", state: pressed ? "" : f.name }),
      },
        el("div", { class: "name" }, f.name),
        el("div", { class: "num" }, N(evs.length)),
        el("div", { class: "unit" }, "news events"),
        el("div", { class: "line" }, el("span", { class: "swatch", style: { background: levelColor(s.level) } }), s.level_label),
        el("div", { class: "line" }, cats.length ? `Busiest area: ${D.categories[cats[0][0]]}` : "No events yet"),
      );
    }));
  }
  function focusTake() {
    const per = focus.map((f) => ({ ...f, n: events.filter((e) => e.code === f.code).length, level: (stateInfo[f.code] || {}).level }));
    per.sort((a, b) => b.n - a.n);
    const top = per[0], low = per[per.length - 1];
    let txt = `${top.name} makes the most noise, with ${plural(top.n, "event")}. ${low.name} has the fewest (${N(low.n)})`;
    txt += low.level === 3 ? `, yet it's one of the states with an AI policy actually in place.` : ".";
    $("#focus-take").textContent = txt;
  }

  // ---------- matrix + category explainers
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
          const open = () => go({ tab: "events", state: f.name, category: c });
          return el("td", {
            class: n ? "" : "zero",
            style: n ? { background: `var(--seq-${st})`, color: st >= 4 ? "var(--seq-ink-hi)" : "var(--ink)" } : {},
            tabindex: n ? "0" : null,
            onpointermove: n ? (e) => showTip(e, plural(n, "event"), `${f.name} · ${D.categories[c]}`) : null,
            onpointerleave: hideTip,
            onclick: n ? open : null,
            onkeydown: n ? (e) => { if (e.key === "Enter") open(); } : null,
          }, n || "·");
        }),
        el("td", { class: "total" }, grid[r].reduce((a, b) => a + b, 0)),
      ))),
    );
    const totals = Object.entries(count(events, "category")).filter(([c]) => c !== "other").sort((a, b) => b[1] - a[1]);
    const [topC, topN] = totals[0];
    const [lowC, lowN] = totals[totals.length - 1];
    const cap = (s) => s[0].toUpperCase() + s.slice(1);
    $("#kinds-take").textContent = `${cap(CAT[topC].doing)} is the most common move, with ${plural(topN, "event")}. ${cap(CAT[lowC].doing)} is the rarest: ${N(lowN)} across all five states.`;

    $("#cats").replaceChildren(...cats.map((c) => {
      const evs = events.filter((e) => e.category === c);
      const per = Object.entries(count(evs, "state")).sort((a, b) => b[1] - a[1]);
      const ex = evs.slice().sort((a, b) => b.n - a.n || (a.date < b.date ? 1 : -1))[0];
      return el("div", { class: "cat" },
        el("p", { class: "over" }, `${D.categories[c]} · ${N(evs.length)}`),
        el("h4", {}, CAT[c].title),
        el("p", {}, CAT[c].what),
        per.length ? el("p", { class: "lead-state" }, `Leading: ${per[0][0]}, with ${N(per[0][1])}`) : null,
        ex ? el("p", { class: "ex" }, "For example: ", el("a", { href: ex.url, target: "_blank", rel: "noopener" }, ex.title),
          el("span", { class: "m" }, ` (${ex.state}, ${fmtDate(ex.date)}${ex.n > 1 ? `, ${ex.n} outlets` : ""})`)) : null,
        evs.length ? el("button", { class: "linkbtn", onclick: () => go({ tab: "events", category: c }) }, `See all ${N(evs.length)}`) : null,
      );
    }));
  }

  // ---------- over time
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
    const probe = el("div", { class: "mrow" }, el("div"), el("div"), el("div"));
    box.replaceChildren(probe);
    const W = Math.max(240, probe.children[1].clientWidth || 800);
    const H = 64;
    const slot = W / ms.length;
    const bw = Math.min(24, slot * 0.7);
    const rows = focus.map((f, r) => {
      const g = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${f.name}: news events per month` });
      g.append(svg("line", { class: "base", x1: 0, x2: W, y1: H - 0.5, y2: H - 0.5 }));
      for (const a of ANNOT.filter((x) => x.code === f.code)) {
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
        p.addEventListener("pointermove", (e) => showTip(e, plural(n, "event"), `${f.name} · ${MON[mm - 1]} ${yy}`));
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

    const totals = ms.map((_, i) => series.reduce((a, s) => a + s[i], 0));
    const busiest = totals.indexOf(Math.max(...totals));
    const [by, bm] = ms[busiest].split("-").map(Number);
    const firstHalf = totals.slice(0, 12).reduce((a, b) => a + b, 0);
    const rest = totals.slice(12).reduce((a, b) => a + b, 0);
    const lead = rest > firstHalf
      ? `Things picked up in 2026: ${N(rest)} events so far this year, against ${N(firstHalf)} in all of 2025.`
      : `2026 has been quieter so far: ${N(rest)} events this year, against ${N(firstHalf)} in all of 2025.`;
    $("#time-take").textContent = `${lead} The busiest month was ${MON[bm - 1]} ${by}, with ${N(totals[busiest])}.`;
  }

  // ---------- funnel
  function renderFunnel() {
    const st = D.funnel.stages;
    const top = st[0].count || 1;
    $("#h-funnel").textContent = `From ${N(stages.raw)} search results to ${N(stages.events)} events`;
    $("#funnel-take").textContent = `Roughly one search result in ${word(Math.round(stages.raw / Math.max(1, stages.events)))} became an event. The rest were repeats, company news, central-government stories, or had nothing to do with AI.`;
    $("#funnel").replaceChildren(...st.map((s, i) => el("div", {
      class: "frow",
      onpointermove: (e) => showTip(e, `${N(s.count)} ${s.label.toLowerCase()}`, ...focus.map((f) => `${f.name}: ${N(D.funnel.per_state[f.code][s.key])}`)),
      onpointerleave: hideTip,
    },
      el("div", {}, s.label),
      el("div", { class: "track" }, el("div", { class: "fill", style: { width: `${(s.count / top) * 100}%` } })),
      el("div", { class: "n" }, N(s.count), i ? el("div", { class: "pct" }, `${Math.round((s.count / (st[i - 1].count || 1)) * 100)}% kept`) : null),
    )));
    const names = { no_ai_term: "no mention of AI", no_gov_term: "no sign of a state government", excluded: "company or market news", central_only: "central government only", out_of_scope_state: "about another state", out_of_window: "from before 2025", override: "removed by hand" };
    const drops = Object.entries(D.funnel.dropped).sort((a, b) => b[1] - a[1]);
    $("#drops").textContent = `Why the rest went: ${drops.map(([k, v]) => `${names[k] || k} (${N(v)})`).join(", ")}. The first three steps count stories by the state we searched for; the last two by the state in the headline.`;
  }

  // ---------- records table
  function filtersUI() {
    const box = $("#filters");
    const isEv = F.tab === "events";
    const opt = (v, label, s) => el("option", { value: v, selected: v === s }, label);
    const select = (key, label, options) => el("select", { "aria-label": label, onchange: (e) => { F[key] = e.target.value; F.limit = 50; renderTable(); renderCards(); } },
      opt("", label, F[key]), ...options.map(([v, l]) => opt(v, l, F[key])));
    const stateNames = isEv ? focus.map((f) => f.name) : [...new Set(insts.map((i) => i.state))].sort();
    const parts = [select("state", "All states", stateNames.map((n) => [n, n]))];
    if (isEv) {
      parts.push(select("category", "All categories", Object.entries(D.categories)));
      parts.push(select("stage", "All stages", Object.entries(STAGE)));
      parts.push(select("check", "Checked or not", [["checked", "Checked by a person"], ["unchecked", "Not checked yet"]]));
    } else {
      parts.push(select("group", "Any status", Object.entries(GROUP)));
    }
    parts.push(select("confidence", "Any confidence", Object.entries(CONF)));
    const q = el("input", { type: "search", placeholder: "Search headlines", value: F.q, "aria-label": "Search headlines" });
    q.addEventListener("input", (e) => { F.q = e.target.value; F.limit = 50; renderRows(); });
    parts.push(q, el("button", { type: "button", onclick: () => { Object.assign(F, { state: "", category: "", stage: "", confidence: "", group: "", check: "", q: "", limit: 50 }); renderTable(); renderCards(); } }, "Clear"));
    box.replaceChildren(...parts);
  }
  function rowsFor() {
    const q = F.q.trim().toLowerCase();
    if (F.tab === "events") {
      return events.filter((e) => (!F.state || e.state === F.state) && (!F.category || e.category === F.category)
        && (!F.stage || e.stage === F.stage) && (!F.confidence || e.confidence === F.confidence)
        && (!F.check || (F.check === "checked") === !!e.chk)
        && (!q || e.title.toLowerCase().includes(q)));
    }
    return insts.filter((i) => (!F.state || i.state === F.state) && (!F.group || i.group === F.group)
      && (!F.confidence || i.confidence === F.confidence) && (!q || i.title.toLowerCase().includes(q)))
      .sort((a, b) => (a.date < b.date ? 1 : -1));
  }
  const conf = (level, note) => el("span", { class: "conf", title: note }, el("span", { class: "dots", "aria-hidden": "true" }, DOTS[level]), " ", CONF[level]);
  const CHECK = {
    ok: ["ok", "✓ Checked by hand", "A person read this one and agreed with how it was sorted."],
    partly: ["warn", "Checked: label off", "A person confirmed it belongs here but found the state or category wrong."],
    wrong: ["warn", "Flagged on review", "A person judged that this one shouldn't count."],
    fixed: ["ok", "Fixed by hand", "A person corrected this record."],
  };
  function badgeFor(chk) {
    if (!chk) return null;
    const [cls, label, why] = CHECK[chk.s];
    return el("div", {}, el("span", { class: `badge ${cls}`, title: chk.note ? `${why} Note: ${chk.note}` : why }, label));
  }
  function fixLink(title, id) {
    if (!D.repo_url) return null;
    const u = `${D.repo_url}/issues/new?title=${encodeURIComponent(`Correction: ${title}`)}&body=${encodeURIComponent(`Record id: ${id}\n\nWhat is wrong:\n\nSource:\n`)}`;
    return el("div", { class: "fix" }, el("a", { href: u, target: "_blank", rel: "noopener" }, "Spot a mistake?"));
  }
  function renderRows() {
    const rows = rowsFor();
    const shown = rows.slice(0, F.limit);
    const isEv = F.tab === "events";
    const head = isEv ? ["Date", "State", "Event", "Category", "Stage", "Confidence"] : ["Date", "State", "Document", "Type", "Status", "Confidence"];
    const body = shown.map((r) => isEv
      ? el("tr", {},
        el("td", { class: "date" }, fmtDate(r.date)),
        el("td", {}, r.state),
        el("td", { class: "title" },
          el("a", { href: r.url, target: "_blank", rel: "noopener" }, r.title),
          el("div", { class: "summary" }, `${r.source}${r.flags.includes("state_from_query") ? " · state taken from the search" : ""}${r.flags.includes("multi_state") ? " · mentions more than one state" : ""}`),
          r.members.length > 1 ? el("details", {}, el("summary", {}, `Covered by ${r.n} outlets`),
            el("ul", {}, ...r.members.map((m) => el("li", {}, el("a", { href: m.u, target: "_blank", rel: "noopener" }, m.t), ` · ${m.s} · ${fmtDate(m.d)}`)))) : null,
          badgeFor(r.chk),
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
    $("#count").textContent = rows.length ? `Showing ${N(shown.length)} of ${N(rows.length)}` : "Nothing matches those filters.";
    const more = $("#more");
    more.hidden = rows.length <= F.limit;
    more.onclick = () => { F.limit += 50; renderRows(); };
  }
  function renderTable() {
    $("#tab-events").setAttribute("aria-selected", String(F.tab === "events"));
    $("#tab-inst").setAttribute("aria-selected", String(F.tab === "instruments"));
    $("#tab-events").textContent = `News events (${N(events.length)})`;
    $("#tab-inst").textContent = `Policy documents (${N(insts.length)})`;
    filtersUI();
    renderRows();
  }
  $("#tab-events").addEventListener("click", () => { Object.assign(F, { tab: "events", group: "", limit: 50 }); if (F.state && !focus.some((f) => f.name === F.state)) F.state = ""; renderTable(); renderCards(); });
  $("#tab-inst").addEventListener("click", () => { Object.assign(F, { tab: "instruments", category: "", stage: "", limit: 50 }); renderTable(); renderCards(); });

  // ---------- human checks
  function renderChecks() {
    const H = D.hand_check || {};
    const pct = (x) => `${Math.round(x * 100)}%`;
    const tiles = [
      ["relevant", "Belong here", "of the sampled events really are a state government acting on AI"],
      ["state", "Right state", "have the correct state attached"],
      ["category", "Right category", "landed in a sensible bucket"],
      ["dropped_ok", "Rightly thrown out", "of the sampled rejects deserved to go"],
      ["pairs_split_ok", "Near-twins kept apart", "of the close-but-separate pairs really are different events"],
      ["known_found", "Known events found", "of the events we knew about turned up in the data"],
    ];
    $("#checks").replaceChildren(...tiles.map(([key, title, line]) => {
      const r = H[key] || { k: 0, n: 0 };
      if (!r.n) return el("div", { class: "check empty" }, el("p", { class: "over" }, title), el("div", { class: "big" }, "Not checked yet"));
      const p = r.k / r.n;
      return el("div", { class: "check" },
        el("p", { class: "over" }, title),
        el("div", { class: "big" }, pct(p)),
        el("div", { class: "sub" }, `${N(r.k)} of ${N(r.n)} ${line}`),
        el("div", { class: "bar", "aria-hidden": "true" }, el("i", { style: { left: pct(r.lo), width: pct(r.hi - r.lo) } }), el("b", { style: { left: `calc(${pct(p)} - 1px)` } })),
        el("div", { class: "range" }, `Likely between ${pct(r.lo)} and ${pct(r.hi)}`));
    }));
    const rel = H.relevant || { n: 0 };
    const checked = events.filter((e) => e.chk).length;
    $("#check-take").textContent = rel.n
      ? `${Math.round((rel.k / rel.n) * 100)}% of the hand-checked sample really belonged here (${N(rel.k)} of ${N(rel.n)}). ${N(checked)} records now carry a person's check.`
      : "The hand-check hasn't been done yet. Once it is, the results land here and on every record a person looked at.";
  }

  // ---------- method numbers
  function bindMethod() {
    const c = count(events, "confidence");
    const drops = D.instrument_drops || {};
    const vals = {
      raw: N(stages.raw), unique: N(stages.unique_articles), relevant: N(stages.relevant), inscope: N(stages.in_scope),
      events: N(stages.events), slices: N((D.collect && D.collect.requests) || 0), inst: N(insts.length),
      drop_union: N(drops.union_level || 0), drop_court: N(drops.judiciary_not_state_executive || 0),
      drop_notai: N(drops.not_ai_specific || 0), drop_ph: N(drops.placeholder_no_ai_instrument || 0),
      sfq: N((D.funnel.flags || {}).state_from_query || 0), merges: N(D.funnel.merges || 0),
      c_high: N(c.high || 0), c_medium: N(c.medium || 0), c_low: N(c.low || 0),
      version: D.version, built: fmtDate(D.last_updated.slice(0, 10)),
    };
    document.querySelectorAll("[data-bind]").forEach((n) => { n.textContent = vals[n.dataset.bind] ?? ""; });
  }

  buildMap();
  renderPanel();
  renderCards();
  focusTake();
  renderMatrix();
  renderMultiples();
  renderFunnel();
  renderChecks();
  renderTable();
  bindMethod();
  let t;
  window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(renderMultiples, 150); });
})();
