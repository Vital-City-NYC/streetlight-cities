#!/usr/bin/env python3
"""
500-meter square grid, following Vital City's lighting-and-crime cookbook
(the method behind the New York City satellite map).

The H3 hex path in common.py stays as it is for the other cities. This module
is the square-grid alternative:

  - a grid of 500 m x 500 m squares in a projected coordinate system, aligned
    to round 500 m coordinates;
  - every square that intersects the city boundary is kept, including squares
    with no crime, so empty squares count in the percentiles;
  - each crime goes to the square that contains it (point-in-square in
    projected coordinates);
  - each square is labeled with the neighborhood holding the most of its
    crimes, or, with no crimes, the neighborhood its centroid falls in.

build_squares() writes squares.geojson (WGS84 polygons plus crime counts).
common_sat_bm.build_squares_lighting() then adds the satellite layer.
"""
import json, math, datetime, collections, sys
import numpy as np
from shapely.geometry import shape, box, Point
from shapely.ops import transform, unary_union
from shapely.prepared import prep
from pyproj import Transformer

import common

CELL_M = 500


def load_geojson(url):
    return common.fetch_json(url, timeout=180)


class SquareGrid:
    """Square grid in a projected CRS, clipped to squares touching a boundary."""

    def __init__(self, boundary_wgs84, *, epsg, cell=CELL_M):
        self.epsg, self.cell = epsg, cell
        self.fwd = Transformer.from_crs(4326, epsg, always_xy=True)
        self.inv = Transformer.from_crs(epsg, 4326, always_xy=True)
        b = transform(self.fwd.transform, boundary_wgs84)
        pb = prep(b)
        x0, y0, x1, y1 = b.bounds
        i0, j0 = math.floor(x0 / cell), math.floor(y0 / cell)
        i1, j1 = math.floor(x1 / cell), math.floor(y1 / cell)
        # keys are (i, j): the square's lower-left corner is (i*cell, j*cell) meters
        self.keys = [(i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)
                     if pb.intersects(box(i * cell, j * cell, (i + 1) * cell, (j + 1) * cell))]
        self.index = {k: n for n, k in enumerate(self.keys)}

    def box_utm(self, key):
        i, j = key
        c = self.cell
        return box(i * c, j * c, (i + 1) * c, (j + 1) * c)

    def ring_wgs84(self, key):
        i, j = key
        c = self.cell
        xs = [i * c, (i + 1) * c, (i + 1) * c, i * c, i * c]
        ys = [j * c, j * c, (j + 1) * c, (j + 1) * c, j * c]
        lons, lats = self.inv.transform(xs, ys)
        return [[round(lo, 6), round(la, 6)] for lo, la in zip(lons, lats)]

    def centroid_wgs84(self, key):
        i, j = key
        c = self.cell
        lon, lat = self.inv.transform((i + 0.5) * c, (j + 0.5) * c)
        return lon, lat

    def locate(self, lons, lats):
        """Square index for each point, or -1 for points outside the kept squares."""
        xs, ys = self.fwd.transform(np.asarray(lons, float), np.asarray(lats, float))
        ii = np.floor(np.asarray(xs) / self.cell).astype(int)
        jj = np.floor(np.asarray(ys) / self.cell).astype(int)
        return np.array([self.index.get((i, j), -1) for i, j in zip(ii, jj)])


def _areas_lookup(areas):
    """areas: list of (name, shapely geometry in WGS84). Returns name_at(lon, lat)."""
    polys = [(name, prep(g), g) for name, g in areas]

    def name_at(lon, lat):
        p = Point(lon, lat)
        for name, pg, _ in polys:
            if pg.contains(p):
                return name
        # centroid over water or just outside the city line: nearest area
        return min(polys, key=lambda t: t[2].distance(p))[0]

    return name_at


def build_squares(crimes, *, city, boundary, areas, epsg, out_dir, cell=CELL_M, crime_meta=None):
    """Bin crimes into the square grid and write squares.geojson into out_dir.

    crimes: dicts with lat, lon, date, night (bool), area (str|None)
    boundary: shapely geometry (WGS84) of the city limits
    areas: list of (name, shapely geometry WGS84) used to label crime-free squares
    crime_meta: extra fields for meta["crime"] (e.g. the location filter used)
    """
    grid = SquareGrid(boundary, epsg=epsg, cell=cell)
    n = len(grid.keys)
    idx = grid.locate([c["lon"] for c in crimes], [c["lat"] for c in crimes])

    crime_n = np.zeros(n, int)
    night_n = np.zeros(n, int)
    night_area = [collections.Counter() for _ in range(n)]
    outside = 0
    for c, k in zip(crimes, idx):
        if k < 0:
            outside += 1
            continue
        crime_n[k] += 1
        if c.get("night"):
            night_n[k] += 1
            if c.get("area"):
                night_area[k][c["area"]] += 1
    if outside:
        print(f"  {outside} crimes fell outside the grid (not in any square touching the city)",
              file=sys.stderr)

    name_at = _areas_lookup(areas)
    feats, labeled_by_centroid = [], 0
    for k, key in enumerate(grid.keys):
        if night_area[k]:
            nta = night_area[k].most_common(1)[0][0]
        else:
            nta = name_at(*grid.centroid_wgs84(key))
            labeled_by_centroid += 1
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [grid.ring_wgs84(key)]},
            "properties": {"sq": f"{key[0]}_{key[1]}", "crime_n": int(crime_n[k]),
                           "crime_night_n": int(night_n[k]), "nta": nta, "boro": city}})

    kept = [c for c, k in zip(crimes, idx) if k >= 0]
    ds = sorted(c["date"][:10] for c in kept if c.get("date"))
    meta = {
        "grid": {"type": "square", "cell_m": cell, "crs": f"EPSG:{epsg}",
                 "rule": "every square that intersects the city boundary, including squares with no crime"},
        "generated": datetime.date.today().isoformat(),
        "n_cells": n,
        "labeled_by_centroid": labeled_by_centroid,
        "crime": {
            "first_date": ds[0] if ds else None, "last_date": ds[-1] if ds else None,
            "total_points": len(kept),
            "night_total_points": int(night_n.sum()),
            "outside_grid": outside,
            **(crime_meta or {}),
        },
    }
    with open(f"{out_dir}/squares.geojson", "w") as f:
        json.dump({"type": "FeatureCollection", "meta": meta, "features": feats}, f)
    print(f"  wrote squares.geojson — {n} squares, {int((night_n == 0).sum())} with no night crime",
          file=sys.stderr)
    return meta
