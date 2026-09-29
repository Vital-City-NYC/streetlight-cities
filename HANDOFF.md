# Handoff: street lighting and crime, beyond New York City

This repo is the whole of the attempt to broaden Vital City's New York City lighting-and-crime maps to other cities. It was built May 24-26, 2026 as a draft for review and has not been edited since, apart from a basemap key fix on Sept. 1. Nothing here is linked from anywhere public.

## What exists

Five cities, each with two maps, all on one shared method:

| City | 311 complaints x crime | Satellite darkness x crime |
|---|---|---|
| New York City | `nyc/index.html` | `nyc/satellite.html` |
| Chicago | `chicago/index.html` | `chicago/satellite.html` |
| Philadelphia | `philadelphia/index.html` | `philadelphia/satellite.html` |
| Baltimore | `baltimore/index.html` | `baltimore/satellite.html` |
| Los Angeles | `los-angeles/index.html` | `los-angeles/satellite.html` |

Plus three combined pages at the root:

- `all-cities-311.html` and `all-cities-satellite.html`: one page each with a city tab bar. The satellite one takes a URL hash like `#city=chicago&l=50&c=80` (lighting percentile at or below 50, crime percentile at or above 80).
- `atlas.html`: New York City's real, untouched maps as the main view, with the four comparison cities as live mini maps along the bottom. `?type=311` switches to the 311 view.
- `index.html`: a plain hub linking every per-city map.

Live: https://vital-city-nyc.github.io/streetlight-cities/

The repo moved from the `vitalcity-nyc` account to the `Vital-City-NYC` organization on Sept. 29, 2026 (https://github.com/Vital-City-NYC/streetlight-cities). The old address, vitalcity-nyc.github.io/streetlight-cities/, no longer works; GitHub does not redirect Pages sites. The organization's earlier code-only mirror was renamed `streetlight-cities-old-mirror` to make room and can be deleted.

## Sept. 29, 2026: Los Angeles satellite map rebuilt the same way

`los-angeles/satellite.html` now follows the same rules as Chicago's (below): 500-meter squares (UTM zone 11N), area-weighted lighting averaged over 2023-2025, crime from Jan. 1, 2023 through Dec. 31, 2025 at night in public outdoor places, and an outdoor allow-list in `los-angeles/location-codes.csv`.

What's different from Chicago:

- **Two crime files.** LAPD changed records systems on March 7, 2024. The old file (`2nrs-mtv8`) runs through early 2024; the new NIBRS file (`k7nn-b2ep`) starts in March 2024 and now has block-level coordinates, which it lacked in May. Their monthly totals join smoothly. The build counts each NIBRS case once and drops 51 that duplicate old-file records.
- **Labels** are neighborhood councils, matched by point-in-polygon, since LAPD records carry only police divisions.
- **311 stops July 4, 2025**, when the city's public 311 file ends.

Headline numbers (garages on; garages off in brackets), from `python3 chicago/report_sat.py los-angeles`:

- 5,470 squares; 2,604 [2,701] with no nighttime outdoor violent crime.
- 26,665 [23,212] nighttime outdoor violent incidents on the map: 10,093 simple assault and battery, 10,069 aggravated assault, 6,183 robbery, 351 homicide (31 more fell just outside the city's squares).
- 96 [95] squares flagged at the default sliders, holding 3.5% [3.6%] of the crime. The old hex map flagged 45 hexes holding 8.1%.
- The top 20% of squares hold 83.3% [84.2%] of the crime, more concentrated than New York City (about 79%) or Chicago (about 65%).
- Most flagged squares: Empowerment Congress Central (9), Reseda (7), United Neighborhoods and LA32 (6 each), Lake Balboa and Coastal San Pedro (5 each).

Open questions for Los Angeles:

- **Coastal squares.** Nine flagged squares are partly outside the city line, mostly along the beach in Venice, Playa del Rey and San Pedro; two are more than half ocean. The dark water pulls their lighting down, the same shoreline question as Chicago's lakefront.
- **Splicing two record systems.** NIBRS counts are built differently from the old system's. The monthly totals line up, but a reader comparing 2023 with 2025 is comparing two systems.
- **The 311 map** shares the crime data, so its crime layer also changed.

## Sept. 29, 2026: Chicago satellite map rebuilt to follow the cookbook

`chicago/satellite.html` now follows Vital City's lighting-and-crime cookbook (the method behind the New York City satellite map) for its grid, time window and outdoor definition. The other cities were unchanged at the time.

What changed, and why:

- **500-meter squares instead of H3 hexes**, to match the cookbook's grid. Squares are built in UTM zone 16N (EPSG:26916), aligned to round 500 m coordinates, and every square that touches the city boundary is kept, including the 615 of 2,650 with no nighttime crime. The old build dropped empty cells, so they never counted in the percentiles. New module: `common_grid.py`. The H3 path in `common.py` is untouched.
- **Lighting per square is an area-weighted mean** of the satellite pixels that overlap it, instead of a 3x3 pixel block (about 1.4 km across) around a hex's center. It averages the 2023, 2024 and 2025 annual composites with equal weight and fills any square with no valid pixels in a year from its three nearest valid squares, as the cookbook does. No square needed the fill. New function: `common_sat_bm.build_squares_lighting`.
- **A fixed window, Jan. 1, 2023 through Dec. 31, 2025**, so crime and lighting cover the same three calendar years. Before, the window's end floated to the start of the current month. The 311 map and chronic spots use the same window.
- **An outdoor allow-list replaces the indoor keyword screen.** The old screen dropped outdoor places the cookbook counts (the ride-share and police-lot codes contain the word VEHICLE) and kept places it doesn't (CTA trains and stations, gas stations, OTHER (SPECIFY)). `chicago/location-codes.csv` lists every CPD location code for these crime types in the window, with counts and the decision. Parking lots and garages share one CPD code, so they sit behind a switch (`CHI_GARAGES=0` turns them off; on by default).
- **Kept as before, on purpose:** annual composites (VNP46A4) rather than the cookbook's 36 monthly composites (VNP46A3), and night as 8 PM to 6 AM rather than civil twilight. Battery stays in, as the counterpart of New York's misdemeanor assault.
- **Page wording:** `template-sat.html` and `all-cities-satellite.html` now read the grid wording (`gridName`, `gridLimit`) and an optional outdoor definition (`outdoorDef`) from each city's config, falling back to the old hex wording. `template.html` reads `outdoorDef` too. Only Chicago's copies were regenerated; the other cities' `index.html` and `satellite.html` are the older copies and render the same text as before.

Headline numbers, from `python3 chicago/report_sat.py` (garages on; garages off in brackets):

- 2,650 squares; 615 [637] with no nighttime outdoor violent crime.
- 33,486 [31,951] nighttime outdoor violent incidents: 16,705 [15,938] battery, 9,148 [8,724] robbery, 7,034 [6,690] assault, 599 [599] homicide.
- At the default sliders (lighting at or below the 50th percentile, crime at or above the 80th), 126 [132] squares are flagged, holding 12.3% [12.9%] of nighttime outdoor violent crime. The old hex map flagged 34 hexes holding 9.5%.
- The top 20% of squares hold 64.7% [65.1%] of the crime. The old hex map's top 20% of hexes held 59.5%; New York City's figure is about 79%.

Community areas with the most flagged squares: Austin and South Shore (12 each), New City (11), Greater Grand Crossing (9), Englewood, Roseland and South Chicago (8 each), Auburn Gresham (7), Chatham (6) and West Englewood (5). The old hex map's list had the same names, except that Woodlawn (2 flagged squares now) drops out of the top ten.

Open questions:

- **Lakefront squares are partly water.** Their lighting average includes dark lake pixels. None of the 238 squares that are mostly outside the city line are flagged, but three flagged squares in Rogers Park, Uptown and Hyde Park are 66% to 90% inside it, so the lake may be pulling their lighting down. One fix is to average only the part of each square inside the city. We don't know what the New York City build did at the shoreline.
- **Parking lots and garages.** We still don't know whether the New York City analysis counted NYPD's parking lot/garage codes. The switch barely moves Chicago's results (126 flagged squares with them, 132 without).
- **The 311 map's crime layer changed too.** `chicago/build.py` feeds both Chicago maps, so `chicago/index.html` now uses the same outdoor list and window.
- **New York City's 79%.** Chicago's top 20% of squares hold about 65% of the crime. The remaining gap may be real (crime more spread out in Chicago) or may come from the two differences we kept (annual composites, 8 PM to 6 AM).

## Where the research is

- `DATA-SOURCES.md` is the plain-language methodology: every dataset, field, filter, window and caveat per city. Read this first.
- The rest of this file records the dead ends and decisions that never made it into the code. The original working session's transcript is gone, so this is the only written record of them.

## Decisions that shaped the method

- **Nighttime crime only, 8 PM to 6 AM.** Josh's call: darkness is a nighttime condition. The New York City originals count all hours. This is the one methodological split between the originals and the new cities.
- **Indoor incidents excluded** wherever the police file has an indoor/outdoor field. Philadelphia is the only city that has none, so its crime layer includes indoor events.
- **Street-level violent crime only**: assault, robbery, homicide, plus battery where a city uses that category. Sex crimes are excluded everywhere.
- **Each map's two layers share one time window.** Windows differ between cities because the data does. Comparisons are within-city percentiles, never absolute counts across cities.
- **New York City's satellite layer was rebuilt** from the same NASA Black Marble source as the other four so the lighting is apples to apples. The original New York City satellite map uses a different raster (a 2022-2024 composite, provenance credited to Shu Wang, brightness scale running much higher). That original is untouched and still live at its own address.

## Dead ends, so nobody repeats them

- **Miami is blocked.** Miami-Dade County publishes 311 streetlight requests (ArcGIS, split by year), but there is no public point-level crime feed for the City of Miami or the county. The police crime map is a LexisNexis vendor viewer with no download, and Florida crime data is mostly aggregated at the state level. At most Miami could get a 311-only outage map.
- **Free NASA GIBS tiles do not work for this.** The first satellite build (`common_sat.py`, kept but unused) sampled the keyless GIBS nighttime tiles. Those are display-stretched images that saturate across dense cities: in Philadelphia 75 to 90 percent of crime hexes pinned at the palette maximum, leaving no usable within-city darkness variation. GIBS also only keeps about six months of nighttime tiles, so historical matching is impossible there anyway.
- **The fix was calibrated radiance** (`common_sat_bm.py`): NASA Black Marble VNP46A4 annual composites, found via the Common Metadata Repository granule search and downloaded from the LAADS archive with a free Earthdata token. Real radiance runs about 2 to 275 nanowatts per square centimeter per steradian and gives clean terciles.
- **Los Angeles 2024 crime is gutted.** LAPD's mid-2024 records-system change left about 17,000 violent incidents in the coordinate-bearing dataset versus roughly 58,000 in each of 2022 and 2023. The newer NIBRS feed has no coordinates at all. That is why Los Angeles uses calendar 2023 for both layers. (Superseded Sept. 29, 2026: the consolidated NIBRS file `k7nn-b2ep` now has coordinates, and the Los Angeles satellite map covers 2023-2025.)
- **Baltimore's legacy crime file ends in 2019.** Use `Part1_Crime_Beta`, not `Part1_Crime`. Its object ID field is `ESRI_OID`, and asking ArcGIS to sort by `OBJECTID` fails silently and returns zero rows. Page with `resultOffset` instead.
- **Los Angeles 311 is split by year** (2023, 2024 and 2025 are separate Socrata datasets) and those yearly sets do not show up in the federated Socrata catalog search. The IDs are hardcoded in `los-angeles/build.py`.
- **Philadelphia's feeds have no neighborhood field.** `label_neighborhoods.py` assigns names by point-in-polygon against `philadelphia/neighborhoods.geojson`. Do not fetch the OpenDataPhilly neighborhoods download endpoint blind; one candidate URL turned out to be a 526 MB building-footprints file.

## The one finding worth knowing before you extend this

In every city, dark and high-crime hexes are rare. Violent crime concentrates in the brightest, busiest areas, the commercial cores, and the darkest areas are low-crime. That matches the criminology (crime follows activity) and it is the honest result. The New York City originals show the same pattern.

## How the code fits together

- `common.py`: shared H3 hex binning (resolution 8 for the four comparison cities, 9 for New York City), tercile bivariate classes, top-20 chronic complaint addresses. Writes `hexes.geojson` and `chronic.json`.
- `<city>/build.py`: a fetch adapter per city, each hitting a different open-data platform (Socrata for Chicago and Los Angeles, Carto SQL for Philadelphia, ArcGIS for Baltimore). All keyless. Sets the window and the crime and complaint filters.
- `common_sat_bm.py` and `<city>/build_sat.py`: add the darkness layer to an existing `hexes.geojson`, writing `hexes-sat.geojson` with per-cell lighting and crime percentiles plus the quantile arrays the sliders read.
- `template.html` and `template-sat.html`: the two page templates. Each city's `index.html` and `satellite.html` are copies, parameterized by `config.js` and `config-sat.js` (bounds, center, copy, caveats).
- `label_neighborhoods.py`: pure-Python point-in-polygon labeling, reusable for any city whose feeds lack a neighborhood field.
- `common_grid.py`: the 500-meter square grid used by Chicago's satellite map. `chicago/build.py` writes `squares.geojson` with it, and `chicago/build_sat.py` adds the lighting and writes `hexes-sat.geojson` (the name is kept so every page reads it unchanged).
- `nyc/` has no `build.py`. Its hexes were pulled live from the existing `bivariate-lighting-crime` repo's `hexes.geojson` and only the satellite layer was added.

## Rebuilding

Python 3 with `h3`, `numpy`, `h5py` and `Pillow`, plus `shapely` and `pyproj` for Chicago's square grid. The satellite builds need a free NASA Earthdata download token in `~/.edl_token` (create one at urs.earthdata.nasa.gov). Downloaded Black Marble tiles cache in `/tmp/blackmarble`, which the operating system clears, so the first run per city downloads again. Earthdata tokens expire after about 60 days; a 401 "invalid_token" from the download server means it's time for a new one.

```bash
cd chicago && python3 build.py && python3 build_sat.py
```

Preview with any static server (the pages fetch their own GeoJSON, so `file://` will not work). Leaflet, the CARTO dark basemap and the Photon geocoder are loaded from CDNs.

## Related New York City tools this grew out of

These are the originals. They were deliberately not modified during this work.

- Lighting-crime map (satellite, Mapbox): https://vitalcity-nyc.github.io/street-lighting-map/
- Bivariate lighting-crime map (311, Leaflet): https://vitalcity-nyc.github.io/bivariate-lighting-crime/
- Lighting evidence browser (the research literature): https://vitalcity-nyc.github.io/street-lighting-crime/
- Lighting design deep-dive: https://vitalcity-nyc.github.io/rubber-meets-road/

## Not done

- The mini-tile gallery inside the New York City originals (the original end vision) was never started, by design, until the concept was judged.
- No city beyond these five was attempted except Miami.
- Data is frozen at May 2026. Re-running the build scripts refreshes it from the live sources.
