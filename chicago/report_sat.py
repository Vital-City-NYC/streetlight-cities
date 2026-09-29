#!/usr/bin/env python3
"""Print the headline numbers for the Chicago satellite map.

usage: python3 report_sat.py [folder holding hexes-sat.geojson] [lighting pctl] [crime pctl]
"""
import sys, os, json, math, collections

d = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
L = int(sys.argv[2]) if len(sys.argv) > 2 else 50
C = int(sys.argv[3]) if len(sys.argv) > 3 else 80
j = json.load(open(os.path.join(d, "hexes-sat.geojson")))
P = [f["properties"] for f in j["features"]]
m = j["meta"]
total = sum(p["crime_n"] for p in P)
n = len(P)

print(f"squares: {n}; with no night outdoor violent crime: {sum(1 for p in P if p['crime_n'] == 0)}")
print(f"night outdoor violent crime: {total}; by type: {m['crime'].get('night_by_type')}")
print(f"window: {m['crime']['first_date']} to {m['crime']['last_date']}; garages included: "
      f"{m['crime'].get('garages_included')}")

flag = [p for p in P if p["light_pctl"] <= L and p["crime_pctl"] >= C]
fc = sum(p["crime_n"] for p in flag)
print(f"flagged at lighting <= {L} and crime >= {C}: {len(flag)} squares "
      f"({100 * len(flag) / n:.1f}% of squares), holding {fc} crimes = {100 * fc / total:.1f}% of night outdoor violent crime")

top = sorted((p["crime_n"] for p in P), reverse=True)[:math.ceil(0.2 * n)]
print(f"top 20% of squares by crime ({len(top)} squares) hold {100 * sum(top) / total:.1f}%")
t80 = [p for p in P if p["crime_pctl"] >= 80]
print(f"squares at or above the 80th crime percentile ({len(t80)}) hold "
      f"{100 * sum(p['crime_n'] for p in t80) / total:.1f}%")

print("community areas with the most flagged squares:")
for name, k in collections.Counter(p["nta"] for p in flag).most_common(12):
    print(f"  {k:>3}  {name}")
fill = m["lighting"].get("fill", {})
print("no-data fill:", {y: v["filled_squares"] for y, v in fill.items()})
