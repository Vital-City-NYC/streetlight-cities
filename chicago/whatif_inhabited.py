#!/usr/bin/env python3
"""What the Los Angeles inhabited-squares rule would do to Chicago's numbers.

Computes, without writing anything: Chicago as published; Chicago with
two-decimal percentiles; and Chicago ranking only squares with at least 50
residents (2020 census) and at least half their area inside the city, with
lighting measured over the part inside the city. The Chicago map is not changed.

usage: python3 whatif_inhabited.py
"""
import sys, os, json, math, collections, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import numpy as np
import common, common_grid, common_sat_bm
from shapely.geometry import shape
from shapely.ops import unary_union

CITY_BOUNDARY = "https://data.cityofchicago.org/api/geospatial/qqq8-j68g?method=export&format=GeoJSON"
UTM16N = 26916
# 2020 census blocks with population (POP100), Census Bureau TIGERweb (keyless)
BLOCKS = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10/query"
BLOCKS_CACHE = os.path.join(HERE, "cache", "census_blocks_2020.geojson")   # not committed
CITY_POP_2020 = 2_746_388
SQ_MI = 0.25 / 2.589988


def census_blocks():
    if not os.path.exists(BLOCKS_CACHE):
        os.makedirs(os.path.dirname(BLOCKS_CACHE), exist_ok=True)
        feats, offset = [], 0
        while True:
            q = {"where": "STATE='17' AND COUNTY IN ('031','043')", "geometry": "-87.95,41.64,-87.52,42.03",
                 "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
                 "outFields": "GEOID,POP100", "orderByFields": "OBJECTID", "resultOffset": offset,
                 "resultRecordCount": 10000, "outSR": 4326, "f": "geojson"}
            batch = common.fetch_json(BLOCKS + "?" + urllib.parse.urlencode(q), timeout=600).get("features", [])
            feats += batch
            print(f"    …{len(feats)} census blocks", file=sys.stderr)
            if len(batch) < 10000:
                break
            offset += 10000
        if not feats:
            raise SystemExit("census block download returned nothing")
        json.dump({"type": "FeatureCollection", "features": feats}, open(BLOCKS_CACHE, "w"))
    return [(f["properties"].get("POP100") or 0, shape(f["geometry"]))
            for f in json.load(open(BLOCKS_CACHE))["features"] if f.get("geometry")]


def summarize(label, meta, feats, total_night):
    P = [f["properties"] for f in feats]
    crime = np.array([p["crime_n"] for p in P]); cp = np.array([p["crime_pctl"] for p in P])
    flag = [p for p in P if p["light_pctl"] <= 50 and p["crime_pctl"] >= 80]
    fc = sum(p["crime_n"] for p in flag)
    ranked_night = int(crime.sum())
    top = sorted(crime, reverse=True)[:math.ceil(0.2 * len(P))]
    light = sorted(p["light_n"] for p in P)
    print(f"\n=== {label}")
    if "ranking" in meta:
        r = meta["ranking"]
        print(f"  ranked squares {r['squares_ranked']} of {r['squares_total']}; left out: "
              f"{r['left_out']['too_few_residents_only']} too few residents, "
              f"{r['left_out']['mostly_outside_boundary_only']} mostly outside, {r['left_out']['both']} both; "
              f"{r['night_incidents_left_out']} incidents in squares left out")
    else:
        print(f"  ranked squares {len(P)} (all)")
    print(f"  median radiance {light[len(light) // 2]:.1f}; incidents to reach the top 20%: {int(crime[cp >= 80].min())}")
    print(f"  flagged {len(flag)} squares, {len(flag) * SQ_MI:.1f} sq mi, {fc} incidents = "
          f"{100 * fc / total_night:.1f}% of all nighttime outdoor violent crime")
    print(f"  top 20% of ranked squares hold {100 * sum(top) / ranked_night:.1f}% of their crime")
    print("  most flagged: " + ", ".join(f"{n} {k}" for n, k in collections.Counter(p["nta"] for p in flag).most_common(10)))


if __name__ == "__main__":
    boundary = unary_union([shape(f["geometry"]) for f in common_grid.load_geojson(CITY_BOUNDARY)["features"]])
    grid = common_grid.SquareGrid(boundary, epsg=UTM16N)
    pops, total = common_grid.square_population(grid, census_blocks(), boundary)
    off = abs(total - CITY_POP_2020) / CITY_POP_2020
    print(f"population assigned to squares: {total:,.0f} (2020 census: {CITY_POP_2020:,}; off by {100 * off:.2f}%)")
    if off > 0.01:
        raise SystemExit("population is more than 1% off the 2020 census count; stopping")
    sq = json.load(open(os.path.join(HERE, "squares.geojson")))
    total_night = sum(f["properties"]["crime_night_n"] for f in sq["features"])

    pub = json.load(open(os.path.join(HERE, "hexes-sat.geojson")))
    summarize("Chicago as published (whole-number percentiles)", pub["meta"], pub["features"], total_night)
    common_args = dict(years=(2023, 2024, 2025), boundary=boundary, epsg=UTM16N, lighting_label="", write=False)
    meta, feats = common_sat_bm.build_squares_lighting(HERE, exact_percentiles=True, **common_args)
    summarize("Chicago, two-decimal percentiles, no other change", meta, feats, total_night)
    meta, feats = common_sat_bm.build_squares_lighting(
        HERE, clip_lighting_to_boundary=True, population=pops, min_residents=50, min_share_inside=0.5,
        exact_percentiles=True, **common_args)
    summarize("Chicago with the Los Angeles rule (50 residents, half inside, lighting clipped, "
              "two-decimal percentiles)", meta, feats, total_night)
