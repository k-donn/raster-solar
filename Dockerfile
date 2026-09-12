# syntax=docker/dockerfile:1

ARG BUILDPLATFORM

FROM --platform=$BUILDPLATFORM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update \
	&& apt-get install -y --no-install-recommends ca-certificates unzip wget libexpat1 \
	&& rm -rf /var/lib/apt/lists/*

COPY download_data.sh process_combined.py generate-tiles.py ./

RUN python -m pip install --no-cache-dir \
	numpy shapely pyproj rasterio Pillow mercantile pytz \
	&& bash download_data.sh \
	&& python process_combined.py \
	&& python process_combined.py --method monte-carlo \
	&& python generate-tiles.py \
	&& python generate-tiles.py --dst --tile-dir tiles-dst

FROM dhi.io/caddy:2 AS runtime

COPY Caddyfile /etc/caddy/Caddyfile
COPY index.html /srv/
COPY globe.html /srv/
COPY --from=builder /build/tiles/ /srv/tiles/
COPY --from=builder /build/tiles-dst/ /srv/tiles-dst/
COPY --from=builder /build/processed-geojson/ /srv/processed-geojson/

