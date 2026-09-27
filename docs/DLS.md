# Alberta DLS map approximation

Wellspring places a marker near the centre of an Alberta legal subdivision
(LSD) when the **surface location** has a supported DLS description. This is
an approximate grid position, not the wellhead's surveyed surface coordinate.
It must be labelled `approximate` in the UI. The marker is unsuitable for
navigation, land decisions, or measurement.

The parser produces `dls = {lsd, section, township, range, meridian}` from
`surface_location`. `enrich_event(record)` uses that dictionary, or parses
`surface_location` when the dictionary is absent. It never derives a surface
position from UWI, well name, or bottomhole text. Missing, invalid, or
unsupported descriptions return null latitude and longitude plus a
`location_reason`. A null position is never replaced with `(0, 0)`.

## Method

The [Government of Alberta ATS diagram](https://www.alberta.ca/system/files/custom_downloaded_images/energy-alberta-township-survey.pdf)
states that meridians 4, 5, and 6 lie at 110, 114, and 118 degrees west;
ranges and townships are about six miles wide; a township has 36 sections;
and a section has 16 LSDs. The
[Alberta Land Titles numbering diagram](https://www.servicealberta.ca/pdf/ltmanual/SUR-1-APPENDIXA.PDF)
provides the alternating section and LSD row order used in `wellspring/geo.py`.

The formula places the LSD at its nominal grid centre. With `t` as township
number and `y` as miles north within its township:

```text
latitude = 48.99948 + 0.087374(t-1) - 0.0000007(t-1)^2 + 0.0873 y/6
```

With `r` as range, `x` as miles west within the township, and `M` as the
meridian longitude (110, 114, or 118):

```text
west_km   = 9.77(r-1) + 9.77 x/6
longitude = -M - meridian_offset - west_km / (111.32 cos(latitude))
```

The longitude offsets are 0.0050, 0.0016, and 0.0005 degrees for W4, W5,
and W6. These constants and the 9.77 km effective range pitch are empirical
approximations from public Alberta ATS polygon positions, including road
allowances. The latitude expression accommodates a small change in township
spacing toward the north. This is a display model of the grid, not a survey
transformation. It does not consume a map service at runtime.

## Public reference checks and limits

`fixtures/dls-reference.json` contains source-linked polygons from the
[Government of Alberta ATS Legal SubDivision layer](https://geospatial.alberta.ca/titan/rest/services/ags_apps/ags_apps_alberta_township_system/MapServer/3).
Each entry records the government polygon's object ID and a direct query URL.
The reference latitude and longitude are the centroid calculated from that
polygon's WGS84 vertices. They are independent of Wellspring's formula. The
source credits the Government of Alberta. The fixture records which polygons
were set aside as verification checks.

The [ATS Township layer](https://geospatial.alberta.ca/titan/rest/services/ags_apps/ags_apps_alberta_township_system/MapServer/0)
also supplies a maximum observed range for each township and meridian. A
compact, offline copy of those limits prevents extrapolation past the mapped
township fabric. The exact aggregate query is linked in the fixture. This
township check cannot prove the requested section or LSD exists inside a
partially surveyed edge township.

For the 77 stored polygons, including seven verification checks spread
across all three meridians, the greatest centre-to-centre error was
**1.201 km** and the mean was **0.192 km**. The test rejects any stored
reference with error of 1.5 km or more. These are measured errors at sampled
legal subdivisions, not a claim of a universal section-level guarantee.
Survey irregularities, correction lines, road allowances, and missing legal
subdivisions can move an actual parcel or wellhead away from this nominal
grid position. A well's true surface coordinate may differ even when the
grid-centre approximation is close to its LSD polygon centre.

The converter returns coordinates only within these sampled operating bands,
and only when the range is no higher than the ATS Township layer's maximum
for that township:

| Meridian | Township | Range |
| --- | --- | --- |
| W4 | 1 to 120 | 1 to 26 |
| W5 | 1 to 120 | 1 to 25 |
| W6 | 60 to 120 | 1 to 15 |

The bands prevent extrapolation into areas with little or no sampled ATS
coverage, especially south of township 60 in W6. They do not guarantee that
every DLS inside a band exists as a surveyed LSD. For that determination, use
the provincial ATS polygon data directly. Values outside the bands remain
null with `location_reason = "outside_validated_grid"`; values beyond the
township fabric cap use `"outside_surveyed_township_grid"`.
