#!/usr/bin/env python3
"""Los Angeles darkness x crime on the 500 m square grid — VIIRS Black Marble annual
radiance, 2023, 2024 and 2025 averaged (the same three years as the crime window).

Run build.py first (it writes squares.geojson)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common_sat_bm, common_grid
from shapely.geometry import shape
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("LA_OUT", HERE)
CITY_BOUNDARY = "https://data.lacity.org/resource/brvb-jr45.geojson"

boundary = unary_union([shape(f["geometry"]) for f in common_grid.load_geojson(CITY_BOUNDARY)["features"]])
common_sat_bm.build_squares_lighting(HERE, years=(2023, 2024, 2025), boundary=boundary, epsg=26911,
                                     lighting_label="VIIRS Black Marble annual radiance, 2023–2025 average",
                                     out_dir=OUT)
