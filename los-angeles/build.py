#!/usr/bin/env python3
"""Los Angeles fetch adapter — Socrata (data.lacity.org), keyless.

Writes, into this folder (or $LA_OUT):
  hexes.geojson + chronic.json   H3 hexes for the 311 map (common.build)
  squares.geojson                500 m squares for the satellite map (common_grid)
Then run build_sat.py to add the lighting layer to the squares.

Crime spans two LAPD record systems. LAPD moved to a new records system on
March 7, 2024, built to the FBI's National Incident-Based Reporting System
(NIBRS). The old file (2nrs-mtv8) is complete through February 2024 and then
tapers off; the new file (k7nn-b2ep) starts in March 2024. Together they give a
steady monthly count, so this build takes both for the whole window and drops
new-file cases that duplicate an old-file record (same date, time and block).
"""
import sys, os, csv, urllib.parse, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common, common_grid
import numpy as np
import shapely
from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("LA_OUT", HERE)

# Fixed window: calendar 2023 through 2025, the same three years as the
# satellite lighting (VNP46A4 annual composites 2023, 2024 and 2025).
WIN_START = "2023-01-01"
WIN_END = "2026-01-01"            # exclusive
RES = "https://data.lacity.org/resource"
CRIME_OLD = "2nrs-mtv8"           # Crime Data from 2020 to 2024 (old records system)
CRIME_NIBRS = "k7nn-b2ep"         # LAPD NIBRS Offenses Dataset (new records system, March 2024 on)
# MyLA311 publishes one file per year; the 2025 file stops on July 4, 2025.
SR_FILES = {"2023": "4a4x-mna2", "2024": "b7dx-7gc3", "2025": "h73f-gn57"}
SR_TYPES = ["Single Streetlight Issue", "Multiple Streetlight Issue"]

# Crime categories. Old file: the categories this map has always used (assault,
# battery, robbery and homicide descriptions, sex crimes excluded). New file:
# the matching NIBRS offenses — aggravated assault (13A), simple assault (13B),
# robbery (120) and murder (09A) — minus brandishing, which the old file files
# under a separate category this map never counted.
OLD_WHERE = ("(upper(crm_cd_desc) like '%ASSAULT%' OR upper(crm_cd_desc) like '%ROBBERY%' "
             "OR upper(crm_cd_desc) like '%HOMICIDE%' OR upper(crm_cd_desc) like '%BATTERY%') "
             "AND upper(crm_cd_desc) not like '%SEXUAL%'")
NIBRS_CODES = ["09A", "120", "13A", "13B"]       # most serious first
NIBRS_WHERE = ("nibr_code in(" + ",".join(f"'{c}'" for c in NIBRS_CODES) + ") "
               "AND upper(nibr_description) not like '%BRANDISH%'")


def old_bucket(desc):
    d = (desc or "").upper()
    if "HOMICIDE" in d: return "homicide"
    if "ROBBERY" in d: return "robbery"
    if "AGGRAVATED" in d or "DEADLY WEAPON" in d: return "aggravated assault"
    return "simple assault and battery"


NIBRS_BUCKET = {"09A": "homicide", "120": "robbery", "13A": "aggravated assault",
                "13B": "simple assault and battery"}

# Outdoor allow-list: location-codes.csv sorts every premise label either file
# used for these crimes in the window into IN, GARAGE or OUT (with notes).
# GARAGE covers parking lots and garages in both files; the switch decides
# whether they count, so both record systems move together.
INCLUDE_GARAGES = os.environ.get("LA_GARAGES", "1") != "0"
with open(os.path.join(HERE, "location-codes.csv")) as f:
    _codes = {(r["source"].split()[0], r["premis_desc"]): r["decision"] for r in csv.DictReader(f)}
def outdoor(src, premise):
    d = _codes.get((src, premise))
    return d == "IN" or (d == "GARAGE" and INCLUDE_GARAGES), d is not None

CITY_BOUNDARY = "https://data.lacity.org/resource/brvb-jr45.geojson"
NEIGHBORHOOD_COUNCILS = ("https://services5.arcgis.com/7nsPwEMP38bSkCjy/arcgis/rest/services/"
                         "Neighborhood_Council_Boundaries_2018_City_of_Los_Angeles/FeatureServer/0/query"
                         "?where=1%3D1&outFields=Name&outSR=4326&f=geojson")
UTM11N = 26911


def socrata(path, params):
    offset, limit = 0, 50000
    while True:
        q = dict(params); q["$limit"] = limit; q["$offset"] = offset
        q.setdefault("$order", ":id")           # stable paging
        batch = common.fetch_json(f"{RES}/{path}?" + urllib.parse.urlencode(q), timeout=300)
        if not batch:
            break
        yield from batch
        if len(batch) < limit:
            break
        offset += limit
        print(f"    …{offset} {path}", file=sys.stderr)


def hour_of(t):
    t = (t or "").strip()
    return int(t) // 100 if t.isdigit() else 12


if __name__ == "__main__":
    print("Los Angeles: fetching 311 streetlight requests…", file=sys.stderr)
    sr_filter = " OR ".join(f"requesttype='{t}'" for t in SR_TYPES)
    outages = []
    for year, rid in SR_FILES.items():
        for r in socrata(f"{rid}.json", {
                "$select": "createddate,requesttype,address,latitude,longitude,ncname",
                "$where": f"({sr_filter}) AND createddate>='{WIN_START}T00:00:00' AND createddate<'{WIN_END}T00:00:00'"}):
            lat, lon = common.fnum(r.get("latitude")), common.fnum(r.get("longitude"))
            if lat and lon:
                outages.append({"lat": lat, "lon": lon, "date": r.get("createddate"),
                                "addr": r.get("address"), "area": r.get("ncname")})
    print(f"  {len(outages)} complaints with coords "
          f"({min(o['date'] for o in outages)[:10]} to {max(o['date'] for o in outages)[:10]})", file=sys.stderr)

    crimes, dropped, unknown = [], collections.Counter(), collections.Counter()
    night_by_type, night_by_year = collections.Counter(), collections.Counter()

    def keep(src, premise, lat, lon, date, hour, bucket):
        premise = premise or "(blank)"
        ok, known = outdoor(src, premise)
        if not known:
            unknown[(src, premise)] += 1
        if not ok:
            dropped["not an outdoor location"] += 1
            return None
        if not (lat and lon):
            dropped["no coordinates"] += 1
            return None
        night = common.is_night(hour)
        return {"lat": lat, "lon": lon, "date": date, "night": night, "bucket": bucket, "src": src}

    print("Los Angeles: fetching crime, old records system…", file=sys.stderr)
    old_keys = set()
    for r in socrata(f"{CRIME_OLD}.json", {
            "$select": "dr_no,crm_cd_desc,date_occ,time_occ,lat,lon,premis_desc",
            "$where": f"lat!=0 AND date_occ>='{WIN_START}T00:00:00' AND date_occ<'{WIN_END}T00:00:00' AND {OLD_WHERE}"}):
        lat, lon = common.fnum(r.get("lat")), common.fnum(r.get("lon"))
        c = keep("legacy", r.get("premis_desc"), lat, lon, r.get("date_occ"),
                 hour_of(r.get("time_occ")), old_bucket(r.get("crm_cd_desc")))
        if lat and lon:
            old_keys.add(((r.get("date_occ") or "")[:10], (r.get("time_occ") or "").strip(),
                          round(lat, 3), round(lon, 3)))
        if c:
            crimes.append(c)

    print("Los Angeles: fetching crime, NIBRS records system…", file=sys.stderr)
    cases = {}
    rank = {c: i for i, c in enumerate(NIBRS_CODES)}
    for r in socrata(f"{CRIME_NIBRS}.json", {
            "$select": "caseno,nibr_code,date_occ,time_occ,premis_desc,hndrdth_lat,hndrdth_lon",
            "$where": f"date_occ>='{WIN_START}T00:00:00' AND date_occ<'{WIN_END}T00:00:00' AND {NIBRS_WHERE}"}):
        k = r.get("caseno")
        # one record per case (NIBRS lists each offense separately); keep the most serious
        if k not in cases or rank[r["nibr_code"]] < rank[cases[k]["nibr_code"]]:
            cases[k] = r
    dup = 0
    for r in cases.values():
        lat, lon = common.fnum(r.get("hndrdth_lat")), common.fnum(r.get("hndrdth_lon"))
        if lat and lon and ((r.get("date_occ") or "")[:10], (r.get("time_occ") or "").strip(),
                            round(lat, 3), round(lon, 3)) in old_keys:
            dup += 1
            continue
        c = keep("NIBRS", r.get("premis_desc"), lat, lon, r.get("date_occ"),
                 hour_of(r.get("time_occ")), NIBRS_BUCKET[r["nibr_code"]])
        if c:
            crimes.append(c)
    print(f"  NIBRS: {len(cases)} cases; {dup} dropped as duplicates of old-system records", file=sys.stderr)

    if unknown:
        print(f"  WARNING: {sum(unknown.values())} records with premise labels not in location-codes.csv "
              f"(excluded): {dict(unknown.most_common(20))}", file=sys.stderr)

    # clip to the city and label each crime with its neighborhood council
    boundary = unary_union([shape(f["geometry"]) for f in common_grid.load_geojson(CITY_BOUNDARY)["features"]])
    ncs = common_grid.load_geojson(NEIGHBORHOOD_COUNCILS)["features"]
    areas = [(f["properties"]["Name"].strip(), shape(f["geometry"])) for f in ncs]
    tree = STRtree([g for _, g in areas])
    pts = shapely.points([c["lon"] for c in crimes], [c["lat"] for c in crimes])
    pi, gi = tree.query(pts, predicate="within")
    for p, g in zip(pi, gi):
        crimes[p].setdefault("area", areas[g][0])
    for c in crimes:
        if c["night"]:
            night_by_type[c["bucket"]] += 1
            night_by_year[c["date"][:4]] += 1
    by_src = collections.Counter(c["src"] for c in crimes if c["night"])
    print(f"  {len(crimes)} outdoor violent crimes with coords (garages {'IN' if INCLUDE_GARAGES else 'OUT'}); "
          f"dropped {dict(dropped)}; night by type {dict(sorted(night_by_type.items()))}; "
          f"night by year {dict(sorted(night_by_year.items()))}; night by file {dict(by_src)}", file=sys.stderr)

    common.build(outages, crimes, city="Los Angeles", win_start=WIN_START, out_dir=OUT,
                 bbox=(-118.69, 33.68, -118.13, 34.36))

    print("Los Angeles: building the 500 m square grid…", file=sys.stderr)
    common_grid.build_squares(crimes, city="Los Angeles", boundary=boundary, areas=areas, epsg=UTM11N, out_dir=OUT,
                              crime_meta={"night_by_type": dict(sorted(night_by_type.items())),
                                          "night_by_year": dict(sorted(night_by_year.items())),
                                          "night_by_records_system": {"old (2nrs-mtv8)": by_src.get("legacy", 0),
                                                                      "NIBRS (k7nn-b2ep)": by_src.get("NIBRS", 0)},
                                          "nibrs_duplicates_dropped": dup,
                                          "location_filter": "outdoor allow-list, los-angeles/location-codes.csv",
                                          "garages_included": INCLUDE_GARAGES})
