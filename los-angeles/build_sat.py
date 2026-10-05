#!/usr/bin/env python3
"""Los Angeles darkness x crime on the 500 m square grid — VIIRS Black Marble annual
radiance, 2023, 2024 and 2025 averaged (the same three years as the crime window).

Only the inhabited part of the city is ranked: a square counts if it has at
least MIN_RESIDENTS residents in the 2020 census AND at least MIN_SHARE_INSIDE
of its area inside the city line. Each square's lighting is measured only over
the part inside the city, so the ocean doesn't darken beach squares.

Run build.py first (it writes squares.geojson)."""
import sys, os, json, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common, common_sat_bm, common_grid
from shapely.geometry import shape
from shapely.ops import unary_union

MIN_RESIDENTS = 50          # 2020 census residents in the square
MIN_SHARE_INSIDE = 0.5      # share of the square's area inside the city line

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("LA_OUT", HERE)
CITY_BOUNDARY = "https://data.lacity.org/resource/brvb-jr45.geojson"
UTM11N = 26911

# 2020 census blocks with population, from Los Angeles County's public GIS (keyless).
BLOCKS = "https://public.gis.lacounty.gov/public/rest/services/LACounty_Dynamic/Demographics/MapServer/16/query"
BLOCKS_CACHE = os.path.join(HERE, "cache", "census_blocks_2020.geojson")   # not committed (~37 MB)
CITY_POP_2020 = 3_898_747   # 2020 census count for the City of Los Angeles


def census_blocks():
    """2020 blocks around the city: list of (population, geometry). Cached locally."""
    if not os.path.exists(BLOCKS_CACHE):
        os.makedirs(os.path.dirname(BLOCKS_CACHE), exist_ok=True)
        feats, offset = [], 0
        while True:
            q = {"where": "1=1", "geometry": "-118.67,33.70,-118.15,34.34",
                 "geometryType": "esriGeometryEnvelope", "inSR": 4326,
                 "spatialRel": "esriSpatialRelIntersects", "outFields": "OBJECTID,CTCB20,POP20",
                 "orderByFields": "OBJECTID", "resultOffset": offset, "resultRecordCount": 3000,
                 "outSR": 4326, "f": "geojson"}
            page = common.fetch_json(BLOCKS + "?" + urllib.parse.urlencode(q), timeout=300)
            batch = page.get("features", [])
            feats += batch
            print(f"    …{len(feats)} census blocks", file=sys.stderr)
            if len(batch) < 3000:
                break
            offset += 3000
        if not feats:
            raise SystemExit("census block download returned nothing")
        json.dump({"type": "FeatureCollection", "features": feats}, open(BLOCKS_CACHE, "w"))
    fc = json.load(open(BLOCKS_CACHE))
    return [(f["properties"].get("POP20") or 0, shape(f["geometry"]))
            for f in fc["features"] if f.get("geometry")]


def population(boundary, epsg=UTM11N):
    grid = common_grid.SquareGrid(boundary, epsg=epsg)
    pops, total = common_grid.square_population(grid, census_blocks(), boundary)
    off = abs(total - CITY_POP_2020) / CITY_POP_2020
    print(f"  population assigned to squares: {total:,.0f} (2020 census: {CITY_POP_2020:,}; off by {100 * off:.2f}%)",
          file=sys.stderr)
    if off > 0.01:
        raise SystemExit("population is more than 1% off the 2020 census count; stopping")
    return pops


if __name__ == "__main__":
    boundary = unary_union([shape(f["geometry"]) for f in common_grid.load_geojson(CITY_BOUNDARY)["features"]])
    pops = population(boundary)
    common_sat_bm.build_squares_lighting(
        HERE, years=(2023, 2024, 2025), boundary=boundary, epsg=UTM11N,
        lighting_label="VIIRS Black Marble annual radiance, 2023–2025 average",
        out_dir=OUT, clip_lighting_to_boundary=True,
        population=pops, population_source="2020 census blocks (POP20), Los Angeles County GIS",
        min_residents=MIN_RESIDENTS, min_share_inside=MIN_SHARE_INSIDE,
        exact_percentiles=True)
