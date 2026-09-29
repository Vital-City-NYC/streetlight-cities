#!/usr/bin/env python3
"""
Satellite-darkness x crime build using CALIBRATED VIIRS radiance.

Source: NASA Black Marble VNP46A4 (annual, moonlight-adjusted nighttime lights),
distributed as HDF5 on LAADS DAAC. Unlike the display tiles in common_sat.py,
this gives true radiance (nW/cm2/sr) with full dynamic range, so intra-city
darkness variation survives. Radiance is log-scaled before binning.

Requires a NASA Earthdata download token saved at ~/.edl_token.

Reuses each city's existing hexes.geojson (crime already binned to the H3 grid
and time-windowed), adds the darkness layer, writes hexes-sat.geojson in the
shape template-sat.html consumes (darkness bin in light_t).
"""
import os, sys, json, math, datetime, collections, bisect, urllib.request, urllib.parse
import numpy as np
import h5py

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
CACHE = "/tmp/blackmarble"
SUBDATASET = "AllAngle_Composite_Snow_Free"   # primary annual radiance field


def _token():
    p = os.path.expanduser("~/.edl_token")
    if not os.path.exists(p):
        raise SystemExit("Missing ~/.edl_token — create a NASA Earthdata token first.")
    return open(p).read().strip()


def _get(url, token=None, dest=None):
    headers = {"User-Agent": "streetlight-cities/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=600) as r:
        data = r.read()
    if dest:
        open(dest, "wb").write(data)
        return dest
    return data


def _granule_urls(bbox, year):
    """Find VNP46A4 annual tiles covering bbox for `year` via CMR (public search)."""
    w, s, e, n = bbox
    q = urllib.parse.urlencode({
        "short_name": "VNP46A4",
        "temporal": f"{year}-01-01T00:00:00Z,{year}-12-31T23:59:59Z",
        "bounding_box": f"{w},{s},{e},{n}", "page_size": 100})
    entries = json.loads(_get(f"{CMR}?{q}").decode())["feed"]["entry"]
    urls = {}
    for g in entries:
        gid = g.get("producer_granule_id", "") or g.get("title", "")
        if f".A{year}001." not in gid:   # keep the requested annual composite only
            continue
        for l in g.get("links", []):
            href = l.get("href", "")
            if href.endswith(".h5") and href.startswith("http"):
                urls[gid] = href
                break
    return list(urls.values())


def _download(url, token):
    os.makedirs(CACHE, exist_ok=True)
    local = f"{CACHE}/{os.path.basename(url)}"
    if os.path.exists(local) and os.path.getsize(local) > 10000:
        return local
    print(f"  downloading {os.path.basename(url)} …", file=sys.stderr)
    return _get(url, token, local)


def _open_grid(path):
    """Return (radiance 2D float array with NaN fill, lon_min, lat_max) for a tile."""
    f = h5py.File(path, "r")
    # find the subdataset wherever it lives in the HDFEOS tree
    found = []
    f.visititems(lambda name, obj: found.append(name) if name.endswith(SUBDATASET) else None)
    if not found:
        raise SystemExit(f"{SUBDATASET} not found in {path}")
    ds = f[found[0]]
    arr = ds[:].astype(float)
    fill = ds.attrs.get("_FillValue")
    scale = ds.attrs.get("scale_factor", 1.0)
    if fill is not None:
        arr[arr == float(np.array(fill).ravel()[0])] = np.nan
    arr *= float(np.array(scale).ravel()[0])
    # tile origin from filename hHHvVV
    base = os.path.basename(path)
    hi = base.index("h");
    h = int(base[hi+1:hi+3]); v = int(base[hi+4:hi+6])
    return arr, h * 10 - 180, 90 - v * 10


def _centroid(ring):
    pts = ring[:-1]
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def build(city_dir, *, year, lighting_label):
    token = _token()
    src = json.load(open(f"{city_dir}/hexes.geojson"))
    feats = src["features"]
    lons = [c[0] for f in feats for c in f["geometry"]["coordinates"][0]]
    lats = [c[1] for f in feats for c in f["geometry"]["coordinates"][0]]
    bbox = (min(lons), min(lats), max(lons), max(lats))

    urls = _granule_urls(bbox, year)
    if not urls:
        raise SystemExit(f"CMR found no VNP46A4 tiles for {year} over {bbox}")
    grids = []
    for url in urls:
        p = _download(url, token)
        arr, lon0, lat0 = _open_grid(p)
        rows, cols = arr.shape
        grids.append((arr, lon0, lat0, rows, cols))

    def radiance_at(lon, lat):
        for arr, lon0, lat0, rows, cols in grids:
            if lon0 <= lon < lon0 + 10 and lat0 - 10 < lat <= lat0:
                c = int((lon - lon0) / 10 * cols)
                r = int((lat0 - lat) / 10 * rows)
                win = arr[max(0, r-1):r+2, max(0, c-1):c+2]
                win = win[~np.isnan(win)]
                if win.size:
                    return float(win.mean())
        return None

    rad = []
    for f in feats:
        lon, lat = _centroid(f["geometry"]["coordinates"][0])
        f["_rad"] = radiance_at(lon, lat)
        if f["_rad"] is not None:
            rad.append(f["_rad"])

    # --- percentile model -----------------------------------------------------
    # lighting percentile: 0 = darkest, 100 = brightest (radiance, ascending).
    # crime percentile:    0 = lowest, 100 = highest. NIGHT-ONLY violent crime
    # (8 PM-6 AM) — darkness is a nighttime condition, so daytime crime is excluded.
    def night_count(p_):
        return p_.get("crime_night_n", p_.get("crime_n", 0))
    rad_sorted = sorted(rad)
    crime_sorted = sorted(night_count(f["properties"]) for f in feats)

    def pctl(sorted_vals, v):
        if v is None or not sorted_vals:
            return None
        return max(0, min(100, round(100 * bisect.bisect_right(sorted_vals, v) / len(sorted_vals))))

    def quantiles(sorted_vals):
        # 101 values: value at each percentile 0..100
        n = len(sorted_vals)
        return [round(sorted_vals[min(n - 1, int(round(p / 100 * (n - 1))))], 1) for p in range(101)]

    out = []
    for f in feats:
        p = f["properties"]
        nc = night_count(p)
        out.append({"type": "Feature", "geometry": f["geometry"], "properties": {
            "light_n": None if f["_rad"] is None else round(f["_rad"], 1),
            "light_pctl": pctl(rad_sorted, f["_rad"]),
            "crime_n": nc,                              # night-only violent crime count
            "crime_pctl": pctl(crime_sorted, nc),
            "nta": p.get("nta"), "boro": p.get("boro")}})

    meta = dict(src["meta"]); meta.pop("outages", None)
    meta["generated"] = datetime.date.today().isoformat()
    meta.pop("class_counts", None)
    meta["n_cells"] = len(out)
    meta["crime"]["time_of_day"] = "night only (8 PM - 6 AM)"
    meta["percentile_method"] = ("Each cell gets a lighting percentile (satellite radiance, 0 = darkest) "
                                 "and a NIGHTTIME violent-crime percentile (8 PM-6 AM, 0 = lowest); the "
                                 "sliders flag cells at or below a lighting percentile AND at or above a "
                                 "crime percentile")
    meta["lightingQ"] = quantiles(rad_sorted)
    meta["crimeQ"] = quantiles(crime_sorted)
    meta["lighting"] = {"label": lighting_label, "year": year,
                        "source": "NASA Black Marble VNP46A4 annual radiance (LAADS DAAC)",
                        "units": "nW/cm2/sr"}
    json.dump({"type": "FeatureCollection", "meta": meta, "features": out},
              open(f"{city_dir}/hexes-sat.geojson", "w"))
    print(f"  wrote hexes-sat.geojson — {len(out)} cells; "
          f"radiance min/med/max = {min(rad):.1f}/{rad_sorted[len(rad)//2]:.1f}/{max(rad):.1f}",
          file=sys.stderr)
    return meta


# --- square grid (cookbook method) --------------------------------------------
# The functions above sample a 3x3 pixel block around each hex centroid (about
# 1.4 km across). The square-grid path below instead takes, for every 500 m
# square, the area-weighted mean of the 15-arc-second pixels that overlap it,
# averages several annual composites with equal weight, and fills squares with
# no valid radiance in a year from their three nearest valid neighbors.

PIX_PER_DEG = 240          # VNP46A4: 2400 pixels across a 10-degree tile = 15 arc-seconds


def _tile_origin(path):
    base = os.path.basename(path)
    hi = base.index(".h") + 1
    h = int(base[hi+1:hi+3]); v = int(base[hi+4:hi+6])
    return h * 10 - 180, 90 - v * 10


def _pixel_weights(grid, keys, lon0, lat0, rows, cols):
    """For each square, [(row, col, overlap area in m2), ...] over the pixels it touches.

    Pixels are lon/lat boxes (pixel-is-area, tile upper-left corner at lon0, lat0);
    each is projected to the grid's CRS and intersected with the square.
    """
    from shapely.geometry import Polygon
    out = []
    for key in keys:
        sq = grid.box_utm(key)
        ring = grid.ring_wgs84(key)
        lons = [p[0] for p in ring]; lats = [p[1] for p in ring]
        c0 = int(math.floor((min(lons) - lon0) * PIX_PER_DEG))
        c1 = int(math.floor((max(lons) - lon0) * PIX_PER_DEG))
        r0 = int(math.floor((lat0 - max(lats)) * PIX_PER_DEG))
        r1 = int(math.floor((lat0 - min(lats)) * PIX_PER_DEG))
        w = []
        for r in range(max(0, r0 - 1), min(rows, r1 + 2)):
            for c in range(max(0, c0 - 1), min(cols, c1 + 2)):
                pl0, pl1 = lon0 + c / PIX_PER_DEG, lon0 + (c + 1) / PIX_PER_DEG
                pa1, pa0 = lat0 - r / PIX_PER_DEG, lat0 - (r + 1) / PIX_PER_DEG
                xs, ys = grid.fwd.transform([pl0, pl1, pl1, pl0], [pa0, pa0, pa1, pa1])
                a = Polygon(zip(xs, ys)).intersection(sq).area
                if a > 0:
                    w.append((r, c, a))
        out.append(w)
    return out


def build_squares_lighting(city_dir, *, years, lighting_label, boundary, epsg,
                           out_dir=None):
    """Add the lighting layer to squares.geojson and write hexes-sat.geojson.

    hexes-sat.geojson keeps its name so the page templates, the tabbed
    all-cities page and the atlas read it unchanged; for this city it holds squares.
    """
    import common_grid
    out_dir = out_dir or city_dir
    token = _token()
    src = json.load(open(f"{out_dir}/squares.geojson"))
    feats = src["features"]
    grid = common_grid.SquareGrid(boundary, epsg=epsg, cell=src["meta"]["grid"]["cell_m"])
    keys = [tuple(int(v) for v in f["properties"]["sq"].split("_")) for f in feats]
    if keys != grid.keys:
        raise SystemExit("squares.geojson does not match the grid rebuilt from the boundary")
    lons = [c[0] for f in feats for c in f["geometry"]["coordinates"][0]]
    lats = [c[1] for f in feats for c in f["geometry"]["coordinates"][0]]
    bbox = (min(lons), min(lats), max(lons), max(lats))

    # square centroids in projected meters, for the nearest-neighbor fill
    cxy = np.array([((i + 0.5) * grid.cell, (j + 0.5) * grid.cell) for i, j in keys])

    per_year, fill_report, weights, tile_used = {}, {}, None, None
    for year in years:
        urls = _granule_urls(bbox, year)
        if len(urls) != 1:
            raise SystemExit(f"expected one VNP46A4 tile over {bbox} for {year}, CMR returned {len(urls)}; "
                             "the square-grid path handles single-tile cities only")
        p = _download(urls[0], token)
        arr, lon0, lat0 = _open_grid(p)
        if (lon0, lat0) != _tile_origin(p):
            raise SystemExit("tile origin mismatch")
        tile = os.path.basename(p).split(".")[2]
        if weights is None:
            rows, cols = arr.shape
            weights = _pixel_weights(grid, keys, lon0, lat0, rows, cols)
            tile_used = tile
        elif tile != tile_used:
            raise SystemExit(f"tile changed between years ({tile_used} vs {tile})")

        vals = np.full(len(keys), np.nan)
        partial = 0
        for k, w in enumerate(weights):
            num = den = 0.0
            for r, c, a in w:
                v = arr[r, c]
                if not np.isnan(v):
                    num += v * a; den += a
            if den > 0:
                vals[k] = num / den
                if den < sum(a for _, _, a in w) - 1e-6:
                    partial += 1
        missing = np.where(np.isnan(vals))[0]
        valid = np.where(~np.isnan(vals))[0]
        for k in missing:   # cookbook no-data fill: mean of the 3 nearest valid squares that year
            d = np.hypot(*(cxy[valid] - cxy[k]).T)
            vals[k] = vals[valid[np.argsort(d)[:3]]].mean()
        per_year[year] = vals
        fill_report[str(year)] = {"filled_squares": int(len(missing)),
                                  "partly_fill_pixels": partial,
                                  "granule": os.path.basename(p)}
        print(f"  {year}: {len(missing)} squares filled from neighbors, "
              f"{partial} averaged over partly missing pixels", file=sys.stderr)

    light = np.mean([per_year[y] for y in years], axis=0)   # equal weight per year

    def night_count(p_):
        return p_.get("crime_night_n", 0)
    rad_sorted = sorted(light.tolist())
    crime_sorted = sorted(night_count(f["properties"]) for f in feats)

    def pctl(sorted_vals, v):
        return max(0, min(100, round(100 * bisect.bisect_right(sorted_vals, v) / len(sorted_vals))))

    def quantiles(sorted_vals):
        n = len(sorted_vals)
        return [round(sorted_vals[min(n - 1, int(round(p / 100 * (n - 1))))], 1) for p in range(101)]

    out = []
    for f, v in zip(feats, light):
        p = f["properties"]
        nc = night_count(p)
        out.append({"type": "Feature", "geometry": f["geometry"], "properties": {
            "light_n": round(float(v), 1),
            "light_pctl": pctl(rad_sorted, float(v)),
            "crime_n": nc,                              # night-only violent crime count
            "crime_pctl": pctl(crime_sorted, nc),
            "nta": p.get("nta"), "boro": p.get("boro")}})

    meta = dict(src["meta"])
    meta["generated"] = datetime.date.today().isoformat()
    meta["n_cells"] = len(out)
    meta["crime"]["time_of_day"] = "night only (8 PM - 6 AM)"
    meta["percentile_method"] = ("Each 500 m square gets a lighting percentile (satellite radiance, 0 = darkest) "
                                 "and a NIGHTTIME violent-crime percentile (8 PM-6 AM, 0 = lowest), both "
                                 "ranked over every square in the city including squares with no crime; the "
                                 "sliders flag squares at or below a lighting percentile AND at or above a "
                                 "crime percentile")
    meta["lightingQ"] = quantiles(rad_sorted)
    meta["crimeQ"] = quantiles(crime_sorted)
    meta["lighting"] = {"label": lighting_label, "years": list(years), "tile": tile_used,
                        "source": "NASA Black Marble VNP46A4 annual radiance (LAADS DAAC)",
                        "field": SUBDATASET, "units": "nW/cm2/sr",
                        "method": "area-weighted mean of the 15-arc-second pixels overlapping each square, "
                                  "per year; squares with no valid pixels in a year take the mean of the "
                                  "3 nearest valid squares; years averaged with equal weight",
                        "fill": fill_report}
    json.dump({"type": "FeatureCollection", "meta": meta, "features": out},
              open(f"{out_dir}/hexes-sat.geojson", "w"))
    print(f"  wrote hexes-sat.geojson — {len(out)} squares; radiance min/med/max = "
          f"{rad_sorted[0]:.1f}/{rad_sorted[len(rad_sorted)//2]:.1f}/{rad_sorted[-1]:.1f}", file=sys.stderr)
    return meta
