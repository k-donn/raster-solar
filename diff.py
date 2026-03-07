#!/usr/bin/env python3

import json
import argparse
from math import isclose
from typing import Dict, Any, List, Tuple

EXPECTED_PROPERTIES = [
    "tzid",
    "countryCodes",
    "utfOffsetStandard",
    "utfOffsetDst",
    "referenceMeridianStd",
    "referenceMeridianDst",
    "avgSolarNoonOffsetMinutesStd",
    "avgSolarNoonOffsetMinutesDst",
]

# Tolerances for float comparisons
FLOAT_TOLERANCE = 1e-6


def load_geojson(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def index_by_tzid(geojson: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if geojson.get("type") != "FeatureCollection":
        raise ValueError("Input GeoJSON is not a FeatureCollection")

    index = {}
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        tzid = props.get("tzid")
        if not tzid:
            raise ValueError("Feature missing required 'tzid' property")
        index[tzid] = props

    return index


def compare_values(
    key: str,
    v1: Any,
    v2: Any,
) -> Tuple[bool, str]:
    """
    Returns (is_equal, message)
    """

    # countryCodes: order-insensitive list comparison
    if key == "countryCodes":
        s1 = sorted(v1 or [])
        s2 = sorted(v2 or [])
        if s1 != s2:
            return False, f"{s1} != {s2}"
        return True, ""

    # Floating-point comparisons
    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
        if not isclose(v1, v2, rel_tol=FLOAT_TOLERANCE, abs_tol=FLOAT_TOLERANCE):
            return False, f"{v1} != {v2}"
        return True, ""

    # Fallback: strict equality
    if v1 != v2:
        return False, f"{v1!r} != {v2!r}"

    return True, ""


def compare_timezones(
    tz1: Dict[str, Dict[str, Any]],
    file1: str,
    tz2: Dict[str, Dict[str, Any]],
    file2: str
) -> Dict[str, Any]:
    report = {
        f"missing_in_{file2}": [],
        f"missing_in_{file1}": [],
        "property_differences": {},
    }

    tzids_1 = set(tz1.keys())
    tzids_2 = set(tz2.keys())

    report[f"missing_in_{file2}"] = sorted(tzids_1 - tzids_2)
    report[f"missing_in_{file1}"] = sorted(tzids_2 - tzids_1)

    for tzid in sorted(tzids_1 & tzids_2):
        diffs = {}

        p1 = tz1[tzid]
        p2 = tz2[tzid]

        for prop in EXPECTED_PROPERTIES:
            v1 = p1.get(prop)
            v2 = p2.get(prop)

            equal, msg = compare_values(prop, v1, v2)
            if not equal:
                diffs[prop] = {
                    file1: v1,
                    file2: v2,
                    "difference": msg,
                }

        if diffs:
            report["property_differences"][tzid] = diffs

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Compare two processed timezone GeoJSON files grouped by tzid"
    )
    parser.add_argument("geojson1", help="First processed GeoJSON file")
    parser.add_argument("geojson2", help="Second processed GeoJSON file")
    parser.add_argument(
        "--output",
        help="Write diff report to JSON file (default: stdout)",
    )
    parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="Exit with non-zero status if differences are found",
    )

    args = parser.parse_args()

    g1 = load_geojson(args.geojson1)
    g2 = load_geojson(args.geojson2)

    tz1 = index_by_tzid(g1)
    tz2 = index_by_tzid(g2)

    report = compare_timezones(tz1, args.geojson1, tz2, args.geojson2)

    has_diffs = (
        report[f"missing_in_{args.geojson1}"]
        or report[f"missing_in_{args.geojson2}"]
        or report["property_differences"]
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    else:
        print(json.dumps(report, indent=2))

    if args.fail_on_diff and has_diffs:
        exit(1)


if __name__ == "__main__":
    main()
