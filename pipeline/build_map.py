"""Turn the state boundary TopoJSON into ready-to-draw SVG paths (docs/india-map.js).

Projection: Lambert conformal conic, standard parallels 12°N and 32°N, central
meridian 82.5°E (India's standard meridian). Done once in Python so the page needs
no mapping library and still opens offline. Lakshadweep is not in the boundary
file, so it is drawn as a point.

usage: python pipeline/build_map.py
"""
from __future__ import annotations

import json
from math import cos, log, pi, radians, sin, tan

from common import DATA, DOCS, log as say, read_json

W = 1000            # viewBox width; height follows the map's aspect ratio
PAD = 16
PHI1, PHI2, LAM0 = radians(12), radians(32), radians(82.5)
_N = log(cos(PHI1) / cos(PHI2)) / log(tan(pi / 4 + PHI2 / 2) / tan(pi / 4 + PHI1 / 2))
_F = cos(PHI1) * tan(pi / 4 + PHI1 / 2) ** _N / _N
_RHO0 = _F / tan(pi / 4) ** _N  # latitude of origin 0°
POINTS = {"Lakshadweep": (72.64, 10.57)}  # (lon, lat) for territories missing from the boundary file


def lcc(lon: float, lat: float) -> tuple[float, float]:
    rho = _F / tan(pi / 4 + radians(lat) / 2) ** _N
    t = _N * (radians(lon) - LAM0)
    return rho * sin(t), -(_RHO0 - rho * cos(t))  # y flipped for SVG


def rings_of(geom: dict, arcs: list) -> list[list[list[float]]]:
    def arc(i):
        a = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
        return a

    def ring(idx):
        pts = []
        for k, i in enumerate(idx):
            a = arc(i)
            pts.extend(a if k == 0 else a[1:])
        return pts

    if geom["type"] == "Polygon":
        return [ring(r) for r in geom["arcs"]]
    return [ring(r) for poly in geom["arcs"] for r in poly]


def shoelace(pts):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        cr = x0 * y1 - x1 * y0
        a += cr
        cx += (x0 + x1) * cr
        cy += (y0 + y1) * cr
    a /= 2
    if abs(a) < 1e-12:
        return 0.0, pts[0]
    return abs(a), (cx / (6 * a), cy / (6 * a))


def run() -> None:
    topo = read_json(DATA / "geo" / "india-states.topo.json")
    jur = read_json(DATA / "instruments" / "source" / "jurisdictions.json")
    code_by_map = {j["map_name"]: j["code"] for j in jur if j.get("map_name")}
    code_by_map.update({j["name"]: j["code"] for j in jur})

    shapes = []
    for g in topo["objects"]["states"]["geometries"]:
        name = g["properties"]["st_nm"]
        rings = [[lcc(x, y) for x, y in r] for r in rings_of(g, topo["arcs"])]
        shapes.append({"name": name, "code": code_by_map[name], "rings": rings})
    for name, (lon, lat) in POINTS.items():
        shapes.append({"name": name, "code": code_by_map[name], "point": lcc(lon, lat)})

    xs = [x for s in shapes for r in s.get("rings", [[s.get("point")]]) for x, _ in r]
    ys = [y for s in shapes for r in s.get("rings", [[s.get("point")]]) for _, y in r]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    k = (W - 2 * PAD) / (x1 - x0)
    H = round((y1 - y0) * k + 2 * PAD)
    fit = lambda p: (round((p[0] - x0) * k + PAD, 1), round((p[1] - y0) * k + PAD, 1))  # noqa: E731

    out = []
    for s in shapes:
        if "point" in s:
            cx, cy = fit(s["point"])
            out.append({"code": s["code"], "name": s["name"], "d": "", "c": [cx, cy], "bbox": [cx - 6, cy - 6, cx + 6, cy + 6], "area": 0})
            continue
        parts, area, best = [], 0.0, (0.0, None)
        bx0 = by0 = 1e9
        bx1 = by1 = -1e9
        for r in s["rings"]:
            pts, prev = [], None
            for p in r:
                q = fit(p)
                if q != prev:
                    pts.append(q)
                    prev = q
            if len(pts) < 3:
                continue
            a, c = shoelace(pts)
            area += a
            if a > best[0]:
                best = (a, c)
            bx0, by0 = min(bx0, *(x for x, _ in pts)), min(by0, *(y for _, y in pts))
            bx1, by1 = max(bx1, *(x for x, _ in pts)), max(by1, *(y for _, y in pts))
            parts.append("M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z")
        if best[1] is None:  # too small to have a measurable area at this scale
            raw = [fit(p) for r in s["rings"] for p in r]
            bx0, by0 = min(x for x, _ in raw), min(y for _, y in raw)
            bx1, by1 = max(x for x, _ in raw), max(y for _, y in raw)
            best = (0.0, ((bx0 + bx1) / 2, (by0 + by1) / 2))
        out.append({
            "code": s["code"], "name": s["name"], "d": "".join(parts),
            "c": [round(best[1][0], 1), round(best[1][1], 1)],
            "bbox": [round(bx0, 1), round(by0, 1), round(bx1, 1), round(by1, 1)],
            "area": round(area),
        })
    DOCS.mkdir(exist_ok=True)
    (DOCS / "india-map.js").write_text(
        "window.INDIA_MAP = " + json.dumps({"w": W, "h": H, "states": out}, separators=(",", ":")) + ";\n",
        encoding="utf-8", newline="\n")
    say(f"map: {len(out)} shapes, viewBox 0 0 {W} {H}")


if __name__ == "__main__":
    run()
