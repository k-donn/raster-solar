import json
import math
import random
import argparse
from pathlib import Path
import datetime
import pytz

import numpy as np
from shapely.geometry import shape, Point, mapping
from shapely.prepared import prep
from pyproj import Transformer


# ============================================================================
# CONFIG
# ============================================================================

TIMEZONE_DIR = "raw-geojson"
METADATA_JSON = "raw-geojson/timezone-info.json"
OUTPUT_NUMERIC = "processed-geojson/timezones_processed.geojson"
OUTPUT_MONTECARLO = "processed-geojson/timezones_processed_montecarlo.geojson"

SIMPLIFY_TOLERANCE = 0.01  # degrees
N_SAMPLES = 2000           # Monte-Carlo samples per zone
METHOD = "numeric"         # "numeric" or "monte-carlo"


# ============================================================================
# ANGULAR & OFFSET HELPERS
# ============================================================================

def wrap_deg(angle):
    """Wrap angle to (-180, 180]."""
    return ((angle + 180) % 360) - 180


def reference_meridian_from_offset(offset_str: str) -> float:
    """
    Parse '+HH:MM' or '-HH:MM' string into reference meridian degrees.
    1 hour = 15 degrees longitude.
    """
    sign = 1 if offset_str.startswith("+") else -1
    hh, mm = offset_str[1:].split(":")
    hours = int(hh)
    minutes = int(mm)
    return sign * (hours + minutes / 60.0) * 15.0


def circular_mean(deg_values):
    """Circular mean of angles in degrees (for monte-carlo method)."""
    radians = np.radians(deg_values)
    x = np.mean(np.cos(radians))
    y = np.mean(np.sin(radians))
    return math.degrees(math.atan2(y, x))


def circular_mean_offset(longitudes, ref_meridian):
    """
    Circular mean of longitude offsets (for numeric method).
    Returns mean offset in DEGREES.
    """
    sx = 0.0
    sy = 0.0
    n = 0

    for lon in longitudes:
        d = wrap_deg(lon - ref_meridian)
        theta = math.radians(d)
        sx += math.cos(theta)
        sy += math.sin(theta)
        n += 1

    if n == 0:
        return 0.0

    return math.degrees(math.atan2(sy / n, sx / n))


# ============================================================================
# NUMERIC METHOD HELPERS
# ============================================================================

def extract_longitudes(geom):
    """
    Extract all exterior longitudes from Polygon or MultiPolygon.
    """
    lons = []

    if geom.geom_type == "Polygon":
        lons.extend([x for x, y in geom.exterior.coords])

    elif geom.geom_type == "MultiPolygon":
        for poly in geom.geoms:
            lons.extend([x for x, y in poly.exterior.coords])

    return lons


def compute_numeric(geom, ref_std, ref_dst):
    """
    Numeric method: extract boundary coordinates and compute circular mean.
    Returns (offset_std_minutes, offset_dst_minutes).
    """
    lons = extract_longitudes(geom)
    
    mean_offset_deg_std = circular_mean_offset(lons, ref_std)
    offset_std_minutes = -mean_offset_deg_std * 4.0
    
    mean_offset_deg_dst = circular_mean_offset(lons, ref_dst)
    offset_dst_minutes = -mean_offset_deg_dst * 4.0
    
    return offset_std_minutes, offset_dst_minutes


# ============================================================================
# MONTE-CARLO METHOD HELPERS
# ============================================================================

def sample_points_equal_area(geom, n_samples):
    """
    Uniform random sampling inside polygon using an equal-area projection.
    Returns list of (lon, lat).
    """
    # Global equal-area projection
    fwd = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)
    inv = Transformer.from_crs("EPSG:6933", "EPSG:4326", always_xy=True)

    # Reproject geometry to equal-area
    def project_coords(coords):
        return [fwd.transform(x, y) for x, y in coords]

    if geom.geom_type == "Polygon":
        geom_eq = type(geom)(project_coords(geom.exterior.coords))
    else:  # MultiPolygon
        geom_eq = type(geom)([
            type(p)(project_coords(p.exterior.coords))
            for p in geom.geoms
        ])

    minx, miny, maxx, maxy = geom_eq.bounds
    prepared = prep(geom_eq)

    points = []
    while len(points) < n_samples:
        x = random.uniform(minx, maxx)
        y = random.uniform(miny, maxy)
        p = Point(x, y)

        if prepared.contains(p):
            lon, lat = inv.transform(x, y)
            points.append((lon, lat))

    return points


def average_solar_offset_minutes(geom, ref_meridian_deg, n_samples):
    """
    Monte-Carlo method: area-weighted circular mean.
    Returns average solar-noon offset in minutes.
    """
    samples = sample_points_equal_area(geom, n_samples)

    diffs = []
    for lon, _ in samples:
        diffs.append(wrap_deg(lon - ref_meridian_deg))

    mean_deg = circular_mean(diffs)
    return -mean_deg * 4.0


def compute_montecarlo(geom, ref_std, ref_dst, n_samples):
    """
    Monte-Carlo method: sample points and compute circular mean.
    Returns (offset_std_minutes, offset_dst_minutes).
    """
    avg_std = average_solar_offset_minutes(geom, ref_std, n_samples)
    avg_dst = average_solar_offset_minutes(geom, ref_dst, n_samples)
    return avg_std, avg_dst


def compute_time_weighted_offset(tzid, avg_std_minutes, avg_dst_minutes, year=None, resolution_minutes=60):
    """
    Compute a time-weighted average of solar-noon offsets (in minutes) for a timezone.
    Uses `pytz` to determine whether local times are in DST and weights `avg_std_minutes`
    and `avg_dst_minutes` by the fraction of the year spent in DST.

    Parameters:
    - tzid: timezone identifier string (e.g., 'America/New_York')
    - avg_std_minutes: average offset (minutes) during standard time
    - avg_dst_minutes: average offset (minutes) during DST (may be None)
    - year: calendar year to evaluate (defaults to current year)
    - resolution_minutes: sampling resolution in minutes (default 60)

    Returns: (weighted_minutes, fraction_dst)
    """
    if year is None:
        year = datetime.datetime.now().year

    try:
        tz = pytz.timezone(tzid)
    except Exception:
        # Unknown timezone — fall back to no DST
        print("Unknown timezone")
        return (avg_std_minutes, 0.0)
    
    start = None
    end = None

    for point in tz._utc_transition_times:
        if point.year == year:
            if start is None:
                start = point
            elif end is None:
                end = point

    fraction_dst = (end - start) / datetime.timedelta(days=360)

    weighted = (1.0 - fraction_dst) * avg_std_minutes + fraction_dst * avg_dst_minutes
    return weighted, fraction_dst, start.timetuple().tm_yday, end.timetuple().tm_yday


# ============================================================================
# COMMAND LINE ARGS
# ============================================================================

def parse_args():
    global TIMEZONE_DIR, METADATA_JSON, OUTPUT_NUMERIC, OUTPUT_MONTECARLO
    global SIMPLIFY_TOLERANCE, N_SAMPLES, METHOD
    
    parser = argparse.ArgumentParser(
        description="Process timezone geometries and compute solar noon offsets"
    )
    parser.add_argument(
        "--timezone-dir", type=str, default=TIMEZONE_DIR,
        help=f"Directory with timezone geojson files (default: {TIMEZONE_DIR})"
    )
    parser.add_argument(
        "--metadata", type=str, default=METADATA_JSON,
        help=f"Path to timezone metadata JSON (default: {METADATA_JSON})"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output geojson path (default: depends on method)"
    )
    parser.add_argument(
        "--method", type=str, default=METHOD, choices=["numeric", "monte-carlo"],
        help=f"Computation method: 'numeric' (boundary coordinates) or 'monte-carlo' (point sampling) (default: {METHOD})"
    )
    parser.add_argument(
        "--simplify-tolerance", type=float, default=SIMPLIFY_TOLERANCE,
        help=f"Geometry simplification tolerance in degrees (default: {SIMPLIFY_TOLERANCE})"
    )
    parser.add_argument(
        "--samples", type=int, default=N_SAMPLES,
        help=f"Number of Monte-Carlo samples per zone (only for monte-carlo method) (default: {N_SAMPLES})"
    )
    
    args = parser.parse_args()
    
    TIMEZONE_DIR = args.timezone_dir
    METADATA_JSON = args.metadata
    METHOD = args.method
    SIMPLIFY_TOLERANCE = args.simplify_tolerance
    N_SAMPLES = args.samples
    
    # Determine output path if not specified
    if args.output:
        OUTPUT_NUMERIC = args.output
        OUTPUT_MONTECARLO = args.output
    
    return args


# ============================================================================
# MAIN PROCESSING
# ============================================================================

if __name__ == "__main__":
    args = parse_args()

# Load metadata
with open(METADATA_JSON, "r", encoding="utf-8") as f:
    metadata = {
        entry["tzIdentifier"]: entry
        for entry in json.load(f)
    }

# Determine output path
if args.output:
    output_path = args.output
elif METHOD == "monte-carlo":
    output_path = OUTPUT_MONTECARLO
else:
    output_path = OUTPUT_NUMERIC

# Process all timezone files
features_out = []

for geojson_path in Path(TIMEZONE_DIR).glob("*.geojson"):
    with open(geojson_path, "r", encoding="utf-8") as f:
        feature = json.load(f)

    tzid = feature["properties"]["tzid"]

    if tzid not in metadata:
        print(f"⚠️  Missing metadata for {tzid}, skipping")
        continue

    meta = metadata[tzid]
    geom = shape(feature["geometry"])

    # Simplify geometry
    geom_simplified = geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)

    # Reference meridians
    ref_std = reference_meridian_from_offset(meta["utcOffsetStandard"])
    ref_dst = reference_meridian_from_offset(
        meta.get("utcOffsetDst", meta["utcOffsetStandard"])
    )

    # Compute offsets using selected method
    if METHOD == "monte-carlo":
        avg_std, avg_dst = compute_montecarlo(geom, ref_std, ref_dst, N_SAMPLES)
    else:  # numeric
        avg_std, avg_dst = compute_numeric(geom_simplified, ref_std, ref_dst)
    # Compute time-weighted offset using pytz DST information
    if ref_dst != ref_std:
        weighted_offset_minutes, dst_fraction, start, end = compute_time_weighted_offset(tzid, avg_std, avg_dst)
    else:
        weighted_offset_minutes, dst_fraction, start, end = avg_std, 0.0, 0, 0


    # Build output feature
    features_out.append({
        "type": "Feature",
        "geometry": mapping(geom_simplified),
        "properties": {
            "tzid": tzid,
            "countryCodes": meta.get("countryCodes", []),
            "utcOffsetStandard": meta["utcOffsetStandard"],
            "utcOffsetDst": meta.get("utcOffsetDst"),
            "referenceMeridianStd": ref_std,
            "referenceMeridianDst": ref_dst,
            "avgSolarNoonOffsetMinutesStd": avg_std,
            "avgSolarNoonOffsetMinutesDst": avg_dst,
            "avgSolarNoonOffsetMinutesWeighted": weighted_offset_minutes,
            "dstFractionOfYear": dst_fraction,
            "dstStart": start,
            "dstEnd": end
        }
    })

    print(f"✓ processed {tzid}")

# Write output
with open(output_path, "w", encoding="utf-8") as f:
    json.dump({
        "type": "FeatureCollection",
        "features": features_out
    }, f)

print(f"\n✅ Wrote {len(features_out)} zones to {output_path} (method: {METHOD})")
