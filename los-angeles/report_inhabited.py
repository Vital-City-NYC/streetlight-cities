#!/usr/bin/env python3
"""Headline numbers for the Los Angeles map's inhabited-squares rule, plus the
same numbers at other population cutoffs (computed, not saved).

usage: python3 report_inhabited.py [lighting pctl] [crime pctl]
"""
import sys, os, json, math, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import numpy as np
import common_grid, common_sat_bm
import build_sat as la
from shapely.geometry import shape, Point
from shapely.ops import unary_union

L = int(sys.argv[1]) if len(sys.argv) > 1 else 50
C = int(sys.argv[2]) if len(sys.argv) > 2 else 80
SQ_MI = 0.25 / 2.589988          # one 500 m square in square miles

# South Los Angeles = the Los Angeles Times Mapping L.A. "South L.A." region
# (28 neighborhoods), via the city's DataLA copy of those boundaries.
MAPPING_LA = ("https://services5.arcgis.com/7nsPwEMP38bSkCjy/arcgis/rest/services/"
              "Aggregation_of_PPP_Loans_in_the_City_of_Los_Angeles_to_LA_Times_City_Neighborhood_Boundaries/"
              "FeatureServer/0/query?where=1%3D1&outFields=name,region&outSR=4326&f=geojson")
hoods = [(f["properties"]["name"], f["properties"]["region"], shape(f["geometry"]))
         for f in common_grid.load_geojson(MAPPING_LA)["features"] if f.get("geometry")]


def hood_of(ring):
    pts = ring[:-1]
    p = Point(sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))
    for name, region, g in hoods:
        if g.contains(p):
            return name, region
    return None, None


def summarize(meta, feats, total_night, label):
    P = [f["properties"] for f in feats]
    r = meta["ranking"]
    light = sorted(p["light_n"] for p in P)
    crime = np.array([p["crime_n"] for p in P]); cp = np.array([p["crime_pctl"] for p in P])
    flag = [i for i, p in enumerate(P) if p["light_pctl"] <= L and p["crime_pctl"] >= C]
    fc = sum(P[i]["crime_n"] for i in flag)
    top = sorted(crime, reverse=True)[:math.ceil(0.2 * len(P))]
    where = [hood_of(feats[i]["geometry"]["coordinates"][0]) for i in flag]
    south = sum(1 for _, reg in where if reg == "south-la")
    print(f"\n=== {label}")
    print(f"(a) ranked squares {r['squares_ranked']} of {r['squares_total']}; left out: "
          f"{r['left_out']['too_few_residents_only']} too few residents only, "
          f"{r['left_out']['mostly_outside_boundary_only']} mostly outside the city only, "
          f"{r['left_out']['both']} both")
    print(f"(b) nighttime incidents: {r['night_incidents_ranked']} in ranked squares, "
          f"{r['night_incidents_left_out']} in squares left out "
          f"({100 * r['night_incidents_left_out'] / total_night:.1f}%)")
    print(f"(c) median radiance {light[len(light) // 2]:.1f}; incidents to reach the top 20%: "
          f"{int(crime[cp >= 80].min())}, top 10%: {int(crime[cp >= 90].min())}")
    print(f"(d) flagged at lighting <= {L}, crime >= {C}: {len(flag)} squares, {len(flag) * SQ_MI:.1f} sq mi, "
          f"{fc} incidents = {100 * fc / total_night:.1f}% of all nighttime outdoor violent crime "
          f"({100 * fc / r['night_incidents_ranked']:.1f}% of the ranked squares')")
    print(f"(e) top 20% of ranked squares hold {100 * sum(top) / r['night_incidents_ranked']:.1f}% of the "
          f"ranked squares' crime ({100 * sum(top) / total_night:.1f}% of all)")
    print(f"(f) flagged by neighborhood council: "
          + ", ".join(f"{n} {k}" for n, k in collections.Counter(P[i]["nta"] for i in flag).most_common()))
    print(f"    in South Los Angeles (Mapping L.A. region): {south} of {len(flag)}; by Mapping L.A. neighborhood: "
          + ", ".join(f"{n} {k}" for n, k in collections.Counter(h for h, _ in where).most_common(8)))
    part = [(P[i]["nta"], P[i]["share_inside"]) for i in flag if P[i]["share_inside"] < 1]
    print(f"(g) flagged squares less than 100% inside the city: {len(part)}"
          + (": " + ", ".join(f"{n} ({100 * s:.0f}%)" for n, s in sorted(part, key=lambda t: t[1])) if part else ""))
    return len(flag), south


if __name__ == "__main__":
    j = json.load(open(os.path.join(HERE, "hexes-sat.geojson")))
    sq = json.load(open(os.path.join(HERE, "squares.geojson")))
    total_night = sum(f["properties"]["crime_night_n"] for f in sq["features"])
    print(f"nighttime outdoor violent incidents in all {len(sq['features'])} squares: {total_night}")
    summarize(j["meta"], j["features"], total_night,
              f"PUBLISHED: {la.MIN_RESIDENTS} residents, {la.MIN_SHARE_INSIDE:.0%} inside, lighting clipped to the city")

    boundary = unary_union([shape(f["geometry"]) for f in common_grid.load_geojson(la.CITY_BOUNDARY)["features"]])
    pops = la.population(boundary)
    def run(min_res, clip):
        return common_sat_bm.build_squares_lighting(
            HERE, years=(2023, 2024, 2025), boundary=boundary, epsg=la.UTM11N, lighting_label="",
            clip_lighting_to_boundary=clip, population=pops, min_residents=min_res,
            min_share_inside=la.MIN_SHARE_INSIDE, exact_percentiles=True, write=False)
    for min_res, clip, label in ((50, False, "50 residents, lighting NOT clipped (your rough test's setup)"),
                                 (0, True, "0 residents (half-inside rule only), lighting clipped"),
                                 (250, True, "250 residents, lighting clipped")):
        meta, feats = run(min_res, clip)
        summarize(meta, feats, total_night, label)
