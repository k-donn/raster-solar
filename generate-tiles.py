import json
import os
import time
import argparse
import numpy as np
from shapely.geometry import shape
from shapely.ops import transform as shp_transform
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from PIL import Image
import mercantile
from multiprocessing import Pool

# --------------------------------
# Configuration
# --------------------------------
GEOJSON_PATH = "processed-geojson/timezones_processed.geojson"
TILE_DIR = "tiles"

MIN_ZOOM = 0
MAX_ZOOM = 6          # raise carefully; grows fast
TILE_SIZE = 256

MAX_OFFSET_DEG = 40
USE_DST = False  # Flag to use DST properties instead of STD

def offset_to_rgb(delta, max_offset):
    delta = max(-max_offset, min(max_offset, delta))

    if delta < 0:
        t = (delta + max_offset) / max_offset
        r = 255
        g = int(255 * t)
        b = int(255 * t)
    else:
        t = delta / max_offset
        r = int(255 * (1 - t))
        g = 255
        b = int(255 * (1 - t))

    return r, g, b

# --------------------------------
# Tile rendering
# --------------------------------
def process_tile(args):
    """Process a single tile and save as PNG."""
    tile, zones, tile_size, max_offset, tile_dir = args
    x, y, z = tile.x, tile.y, tile.z
    
    bounds_ll = mercantile.bounds(tile)
    bounds_merc = mercantile.xy_bounds(tile)

    transform = from_bounds(
        bounds_merc.left,
        bounds_merc.bottom,
        bounds_merc.right,
        bounds_merc.top,
        tile_size,
        tile_size
    )

    r = np.zeros((tile_size, tile_size), dtype=np.uint8)
    g = np.zeros((tile_size, tile_size), dtype=np.uint8)
    b = np.zeros((tile_size, tile_size), dtype=np.uint8)
    a = np.zeros((tile_size, tile_size), dtype=np.uint8)

    # build an array of longitudes for each column, handling tiles that cross
    # the antimeridian. mercantile.bounds may return a west value greater than
    # east in that case, so boost the east value by 360 for spacing. After
    # generating the linearly spaced values we wrap them back into the
    # [-180,180] range so that subsequent difference math behaves correctly.
    west = bounds_ll.west
    east = bounds_ll.east
    if east < west:
        east += 360
    lon_cols = np.linspace(west, east, tile_size)
    # wrap longitudes into the standard range
    lon_cols = ((lon_cols + 180) % 360) - 180

    for zone in zones:
        geom = zone["geom"]
        if not geom.intersects(shape({
            "type": "Polygon",
            "coordinates": [[
                (bounds_merc.left, bounds_merc.bottom),
                (bounds_merc.right, bounds_merc.bottom),
                (bounds_merc.right, bounds_merc.top),
                (bounds_merc.left, bounds_merc.top),
                (bounds_merc.left, bounds_merc.bottom)
            ]]
        })):
            continue

        mask = rasterize(
            [(geom, 1)],
            out_shape=(tile_size, tile_size),
            transform=transform,
            fill=0,
            dtype=np.uint8
        )

        rows, cols = np.where(mask == 1)
        for row, col in zip(rows, cols):
            # compute angular difference accounting for wrapping at the
            # antimeridian.  we want the signed shortest distance from the
            # reference meridian to the pixel longitude.
            raw = lon_cols[col] - zone["ref_lon"]
            delta = (raw + 180) % 360 - 180
            cr, cg, cb = offset_to_rgb(delta, max_offset)
            r[row, col] = cr
            g[row, col] = cg
            b[row, col] = cb
            a[row, col] = 255

    out_dir = os.path.join(tile_dir, str(z), str(x))
    os.makedirs(out_dir, exist_ok=True)

    Image.fromarray(np.dstack([r, g, b, a]), "RGBA").save(
        os.path.join(out_dir, f"{y}.png")
    )

    return f"{z}/{x}/{y}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate tiles from timezone geojson")
    parser.add_argument("--geojson", type=str, default=GEOJSON_PATH,
                        help=f"Path to processed geojson file (default: {GEOJSON_PATH})")
    parser.add_argument("--tile-dir", type=str, default=TILE_DIR,
                        help=f"Output directory for tiles (default: {TILE_DIR})")
    parser.add_argument("--min-zoom", type=int, default=MIN_ZOOM,
                        help=f"Minimum zoom level (default: {MIN_ZOOM})")
    parser.add_argument("--max-zoom", type=int, default=MAX_ZOOM,
                        help=f"Maximum zoom level (default: {MAX_ZOOM})")
    parser.add_argument("--tile-size", type=int, default=TILE_SIZE,
                        help=f"Tile size in pixels (default: {TILE_SIZE})")
    parser.add_argument("--max-offset", type=float, default=MAX_OFFSET_DEG,
                        help=f"Maximum offset in degrees (default: {MAX_OFFSET_DEG})")
    parser.add_argument("--dst", action="store_true", default=USE_DST,
                        help="Use DST properties instead of STD properties")
    
    args = parser.parse_args()
    
    # Override globals with command line args
    GEOJSON_PATH = args.geojson
    TILE_DIR = args.tile_dir
    MIN_ZOOM = args.min_zoom
    MAX_ZOOM = args.max_zoom
    TILE_SIZE = args.tile_size
    MAX_OFFSET_DEG = args.max_offset
    USE_DST = args.dst
    
    # Create projection transformer
    to_merc = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform
    
    # Load and project timezones
    with open(GEOJSON_PATH) as f:
        geojson = json.load(f)

    zones = []
    for feat in geojson["features"]:
        geom = shape(feat["geometry"])
        geom_merc = shp_transform(to_merc, geom)

        meridian_key = "referenceMeridianDst" if USE_DST else "referenceMeridianStd"
        ref_lon = feat["properties"][meridian_key]

        zones.append({
            "geom": geom_merc,
            "ref_lon": ref_lon
        })
    
    # Collect all tiles and zones
    tiles_to_process = []
    
    for z in range(MIN_ZOOM, MAX_ZOOM + 1):
        for tile in mercantile.tiles(-180, -85, 180, 85, [z]):
            tiles_to_process.append((tile, zones, TILE_SIZE, MAX_OFFSET_DEG, TILE_DIR))

    # Process tiles in parallel
    completed = 0
    total = int((4 ** (MAX_ZOOM + 1) - 4 ** MIN_ZOOM)/3)
    total_strlen = len(str(total))
    start_time = time.time()
    with Pool() as pool:
        zoom_levels = pool.imap_unordered(process_tile, tiles_to_process)

        for z in zoom_levels:
            completed += 1
            print(f"\033[2J\033[H", end="")  # Clear screen
            print(f"Completed {z:>10}: {completed:>{total_strlen}}/{total} ({100*completed/total:.1f}%)")
    
    print(f"All tiles processed: {completed} done")
    print(f"Processing speed: {completed/(time.time() - start_time):.5f} tiles/sec")