#!/bin/bash

mkdir raw-geojson
mkdir zips

wget https://www.geoapify.com/data-share/timezones/timezone-info.json -P raw-geojson
wget https://www.geoapify.com/data-share/timezones/timezone-geojson.zip

# thanks ai
sed -i '' 's/−/-/g' raw-geojson/timezone-info.json

unzip -j timezone-geojson.zip 'timezone-geojson/*.geojson' -d raw-geojson

mv timezone-geojson.zip zips/