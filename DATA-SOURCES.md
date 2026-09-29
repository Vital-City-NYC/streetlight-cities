# Where the data came from

Plain-language documentation for the multi-city street-lighting and crime maps
(New York City, Chicago, Philadelphia, Baltimore and Los Angeles). Everything
below is open data pulled from public sources. The comparison-city maps are
drafts for review, not published work.

Last built: May 2026. Chicago and Los Angeles rebuilt Sept. 29, 2026 (see their notes in sections 2, 4, 6 and 7).

---

## 1. What each map shows

Every city has two companion maps:

- **311 complaints × crime** — resident-reported streetlight-outage complaints
  (311 service requests) crossed with violent crime.
- **Satellite darkness × crime** — calibrated nighttime-lights satellite radiance
  crossed with violent crime.

Both put the city on a grid (hexagons of about a few blocks each; Chicago's
satellite map uses 500-meter squares instead, see section 6) and, for every
cell, count the events that fall inside it. The maps then compare hexagons by
percentile, so "high crime" or "dark" always means high or dark *relative to the
rest of that same city*. You should not read the absolute numbers across cities
as equivalent — only the within-city rankings.

---

## 2. Crime data (the shared layer on both maps)

Each city's own police department, via that city's open-data portal. We keep
street-level violent categories (the violence street lighting most plausibly
affects) and exclude sex crimes.

**Time of day — nighttime only.** Every map here counts only nighttime violent
crime, **8 PM – 6 AM** by the incident timestamp. Darkness is a nighttime
condition, so daytime incidents are excluded on both the 311 maps and the
satellite maps.

**Indoor vs outdoor.** Where the data carries an indoor/outdoor field, incidents
flagged as indoors are excluded so the map reflects street-level events:
**New York City, Chicago, Los Angeles and Baltimore** all exclude indoor crime.
**Chicago uses an explicit allow-list** rather than a keyword screen: only the
Chicago Police Department (CPD) `location_description` values for public
outdoor places count. The list is modeled on the New York City cookbook's
outdoor premises (streets, highways, bridges, tunnels, open lots, parks,
playgrounds, cemeteries, parking lots, bus stops and terminals, ferry
terminals, taxis, marinas and piers, mobile food, outdoor mailboxes and
construction sites). Every code CPD used for these crime types in 2023-2025,
with its count and the decision, is in `chicago/location-codes.csv`. In short:
streets, sidewalks, alleys, highways, bridges, parks, forest preserves, the
lakefront, vacant lots, Chicago Housing Authority grounds and lots, bus stops,
construction sites, cemeteries, taxis, ride-share vehicles, private and
commercial vehicles and the airport curbside are in. Homes (including porches,
yards and driveways), businesses, gas stations, schools, hospitals, police
stations, and Chicago Transit Authority (CTA) trains, buses, stations and
platforms are out. CPD's single code for parking lots and garages
(`PARKING LOT / GARAGE (NON RESIDENTIAL)`, plus the CTA and airport lot codes)
is behind a switch in `chicago/build.py` (`CHI_GARAGES`, on by default),
because CPD and NYPD both lump open lots with enclosed garages. CPD homicide
records use an older set of location codes (AUTO, YARD, PORCH, DRIVEWAY,
GANGWAY, PARKING LOT and so on); each is paired with its current counterpart
so homicides get the same treatment.
**Philadelphia is the exception** — its police file has no indoor/outdoor field,
so its crime layer includes indoor incidents and is therefore not directly
comparable on that axis.

Counts in the table below are nighttime incidents (8 PM – 6 AM) over each city's
window — the numbers the maps actually use.

| City | Source / portal | Dataset | Categories kept | Window | Night incidents |
|------|-----------------|---------|-----------------|--------|-----------------|
| New York City | NYPD via NYC Open Data | NYPD complaint data | Felony assault, misdemeanor assault, robbery, murder | Jan 2024 – Mar 2026 | 45,368 |
| Chicago | Chicago Police via data.cityofchicago.org | `ijzp-q8t2` | Assault, battery, robbery, homicide (public outdoor places only) | Jan 2023 – Dec 2025 | 33,486 |
| Philadelphia | Philadelphia Police via phl.carto.com | `incidents_part1_part2` | Aggravated assault (firearm and non-firearm), other assaults, robbery (firearm and non-firearm), criminal homicide | Jan 2023 – Apr 2026 | 64,838 |
| Baltimore | Baltimore Police via Open Baltimore (ArcGIS) | `Part1_Crime_Beta` | Assault, robbery, shooting, homicide (outdoor only) | Jan 2023 – Dec 2024 | 12,832 |
| Los Angeles | Los Angeles Police Department (LAPD) via data.lacity.org | `2nrs-mtv8` (old records system) and `k7nn-b2ep` (NIBRS, March 2024 on) | Assault, battery, robbery, homicide (sex crimes excluded; public outdoor places only) | Jan 2023 – Dec 2025 | 26,665 |

Notes:
- **New York City** crime comes from the existing New York City bivariate map's
  prepared data, not re-fetched.
- **Crime locations are approximate.** Most departments snap each incident to a
  block midpoint or nearest intersection for privacy, so a point can sit a
  hexagon away from where it actually happened.

---

## 3. The 311 streetlight-complaint layer

Resident-reported streetlight problems, from each city's 311 / service-request
system.

| City | Dataset | Complaint types kept | Complaints |
|------|---------|----------------------|------------|
| New York City | NYC 311 (Street Light Condition) | Street light out, multiple lights out, dim, missing lamp, damaged fixture | 50,856 |
| Chicago | `v6vf-nfxy` (Jan 2023 – Dec 2025) | Street light out, alley light out, viaduct light out | 134,798 |
| Philadelphia | `public_cases_fc` | "Street Light Outage" service request | 33,561 |
| Baltimore | `311_Customer_Service_Requests_2023` and `_2024` | Street light out, knocked-down or missing-pole reports | 31,496 |
| Los Angeles | `4a4x-mna2`, `b7dx-7gc3`, `h73f-gn57` (MyLA311 2023-2025; the public file ends July 4, 2025) | Single- and multiple-streetlight issues | 92,927 |

The "show chronic complaint spots" toggle marks the addresses with the most
streetlight complaints in each city's window.

> **311 caveat.** Complaint volume reflects who calls 311 as much as actual
> outage rates, so some neighborhoods are under-reported.

---

## 4. The satellite darkness layer (one identical source for all five cities)

- **Source:** NASA Black Marble, product **VNP46A4** — the annual,
  moonlight-corrected nighttime Day/Night Band radiance composite from the
  Visible Infrared Imaging Radiometer Suite (VIIRS), measured in nanowatts per
  square centimeter per steradian.
- **Year used: 2023 for New York City, Philadelphia and Baltimore.**
  **Chicago and Los Angeles use the average of 2023, 2024 and 2025**, matching
  their crime windows (see below).
- **How it was obtained:** NASA's Common Metadata Repository (CMR) granule search
  located the tiles covering each city; the files were downloaded from the
  Land, Atmosphere Near real-time Capability for EOS (LAADS) Distributed Active
  Archive Center using a free NASA Earthdata login. The "all-angle snow-free
  composite" band was read, sampled at each hexagon, log-scaled, then ranked
  into percentiles.

> **Resolution caveat.** VIIRS pixels are about 500 metres, and the band
> captures all upward light — signage, lit lots, headlights, stadiums — not
> streetlights alone. A bright hexagon is not necessarily well lit for a
> pedestrian on a side street.

### About Chicago's darkness layer specifically (rebuilt Sept. 29, 2026)

Chicago follows Vital City's lighting-and-crime cookbook more closely than the
other comparison cities:

- **Grid:** 500 m x 500 m squares in UTM zone 16N (EPSG:26916), aligned to
  round 500 m coordinates. Every square that intersects the City of Chicago
  boundary (Chicago Data Portal `qqq8-j68g`) is kept: 2,650 squares, 615 of
  them with no nighttime outdoor violent crime. Empty squares count in the
  percentiles.
- **Lighting per square:** the area-weighted mean radiance of the
  15-arc-second VNP46A4 pixels that overlap the square (same field,
  `AllAngle_Composite_Snow_Free`, same fill-value handling and scale factor as
  the other cities). Computed separately for 2023, 2024 and 2025, then
  averaged with equal weight. A square with no valid pixels in a year takes
  the mean of its three nearest valid squares for that year; in this build no
  square needed that fill.
- **Percentiles** of lighting (0 = darkest) and nighttime crime are ranked over
  all 2,650 squares.
- **Window:** crime runs Jan. 1, 2023 through Dec. 31, 2025, the same three
  calendar years as the lighting. The 311 layer and chronic spots use the same
  window.
- **Still different from the cookbook:** annual composites (VNP46A4) rather
  than 36 monthly composites (VNP46A3), and night defined as 8 PM to 6 AM
  rather than by civil twilight.
- **Labels:** each square is labeled with the community area holding most of
  its nighttime crimes, or, with none, the community area its center falls in
  (community area boundaries: Chicago Data Portal `igwz-8jzy`).

### About New York City's darkness layer specifically

New York City's *original* published satellite map uses a different,
"VIIRS-equivalent" raster spanning 2022–2024 on a square grid, prepared
separately, whose brightness scale runs much higher (up to ~931 nanowatts versus
~240–370 for the Black Marble composite). To make all five cities strictly
comparable, **the New York City darkness layer in this atlas was rebuilt from the
same Black Marble VNP46A4 2023 source as the other cities** — it is not the
original raster. New York's real crime and 311 data are unchanged. The original
New York City map remains live and untouched at its own address.

### About Los Angeles's darkness layer specifically (rebuilt Sept. 29, 2026)

Los Angeles follows the same method as Chicago above: 500 m squares in UTM zone
11N (EPSG:26911), every square touching the city boundary (data.lacity.org
`brvb-jr45`) kept, 5,470 squares in all, 2,604 of them with no nighttime
outdoor violent crime; area-weighted lighting averaged over 2023, 2024 and
2025 (no square needed the no-data fill); crime Jan. 1, 2023 through Dec. 31,
2025, at night (8 PM to 6 AM) in public outdoor places.

- **Two crime files.** LAPD moved to a new records system built to the FBI's
  National Incident-Based Reporting System (NIBRS) on March 7, 2024. The old
  file (`2nrs-mtv8`) is complete through February 2024 and then tapers off;
  the new file (`k7nn-b2ep`, block-level coordinates) starts in March 2024.
  Their monthly totals join smoothly, so the build takes both for the whole
  window. NIBRS lists each offense in a case separately, so each case counts
  once, under its most serious offense. New-file cases matching an old-file
  record on date, time and block (51) are dropped as duplicates. Nighttime
  outdoor incidents by year: 9,573 in 2023, 8,918 in 2024 and 8,205 in 2025.
- **Crime categories.** Old file: the assault, battery, robbery and homicide
  descriptions this map has always used, sex crimes excluded. New file:
  aggravated assault (13A), simple assault (13B), robbery (120) and murder
  (09A), minus brandishing, which the old file files under a category this map
  never counted.
- **Outdoor list.** Both files' premise labels are sorted in
  `los-angeles/location-codes.csv` using the same rules as Chicago. Parking lots
  and garages in both files sit behind `LA_GARAGES` (on by default).
- **Labels.** Each crime is matched to a neighborhood council (EmpowerLA's
  2018 boundaries, 99 councils); each square takes the council holding most of
  its nighttime crimes, or the one its center falls in.

### Why 2023 lighting elsewhere

Because no single year falls inside every original city's crime window (New
York is 2024 onward), 2023 lighting is used for the other cities. For New
York that is about a year before its crime window — immaterial, since nighttime
lights change very little year to year.

---

## 5. Neighborhood names

Used only for labels in tooltips and the flagged-locations list.

- **New York City:** neighborhood tabulation areas (in the source data).
- **Chicago:** community areas (in the source data).
- **Baltimore:** neighborhood field (in the source data).
- **Los Angeles:** neighborhood-council name. The 311 map uses the name in the 311 data; crimes and the satellite map's squares are matched to EmpowerLA's neighborhood council boundaries by point-in-polygon.
- **Philadelphia:** the source data has no neighborhood field, so each hexagon
  was matched to a Philadelphia neighborhood by point-in-polygon against an
  OpenStreetMap-derived neighborhoods file (the blackmad/neighborhoods
  Philadelphia boundaries).

---

## 6. Supporting services

- **Basemap:** CARTO dark base tiles (built on OpenStreetMap).
- **Address search:** Photon geocoder (komoot, built on OpenStreetMap).
- **Hexagon grid:** Uber's H3 system — resolution 9 (~a block) for New York City,
  resolution 8 (~a few blocks) for the other four. Chicago's 311 map still uses
  H3 resolution 8.
- **Square grid (Chicago and Los Angeles satellite maps):** 500-meter squares in
  UTM zones 16N and 11N, built by `common_grid.py`. The file keeps the name `hexes-sat.geojson`
  so the pages read it unchanged.

---

## 7. The most important caveats, by city

- **Los Angeles — two record systems.** The old LAPD file (`2nrs-mtv8`) thins
  out after LAPD's March 2024 records-system change. Until 2026 the new NIBRS
  file had no coordinates, so the map used calendar 2023 only. The consolidated
  NIBRS file (`k7nn-b2ep`) now carries block-level coordinates, and the Sept.
  29, 2026 rebuild joins the two for 2023–2025 (see section 4). The city's
  public 311 file ends July 4, 2025.
- **Baltimore — crime end date.** Baltimore Police Part 1 coordinates run only
  through the end of 2024, so both layers cover **2023–2024**.
- **Philadelphia — no indoor flag.** Unlike the other cities, the Philadelphia
  police file has no indoor/outdoor field, so indoor incidents are not separated
  out.
- **Windows differ between cities** because the available data does. Within any
  single map, the crime and the other layer share the same window.
- **Comparisons are within-city.** Brightness and crime are ranked against each
  city's own distribution; absolute values are not comparable city to city.

---

## 8. Reproducibility

Every map is built by a small script kept in this repository:
`<city>/build.py` fetches the 311 and crime data and bins it; `common_sat_bm.py`
adds the Black Marble darkness layer; `common.py` holds the shared binning and
percentile logic; `common_grid.py` builds Chicago's square grid.
`chicago/report_sat.py` prints Chicago's headline numbers from the built file. Re-running a city's scripts rebuilds its data files from the
live open-data sources.
