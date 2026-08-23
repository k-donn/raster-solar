#!/usr/bin/env bash

set -euo pipefail

mkdir -p raw-geojson
archive="$(mktemp)"
trap 'rm -f "$archive"' EXIT

wget -O raw-geojson/timezone-info.json \
	https://www.geoapify.com/data-share/timezones/timezone-info.json
wget -O "$archive" \
	https://www.geoapify.com/data-share/timezones/timezone-geojson.zip

sed -i 's/−/-/g' raw-geojson/timezone-info.json

unzip -j "$archive" 'timezone-geojson/*.geojson' -d raw-geojson