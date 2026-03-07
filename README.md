# Solar Timezone Viewer

An interactive web-based visualization tool that maps the difference between actual solar noon and local clock noon across the world. This project helps understand how timezone boundaries relate to the sun's actual position.

## Features

- Interactive global map using Leaflet
- Color-coded visualization of timezone offsets
- Toggle between Standard Time and Daylight Saving Time
- Click on regions to see timezone info
- View equation of time data by clicking on locations
- Real-world time-weighted solar offset calculations
- Fast tile-based rendering for smooth performance

## Project Overview

This project creates a raster tile visualization of solar timezone data. It:

1. **Downloads** timezone boundary data and metadata from Geoapify
2. **Processes** the data to calculate solar noon offsets for each timezone region
3. **Generates** Web Mercator tiles showing the offset differences
4. **Displays** the tiles in an interactive web interface

## Prerequisites

- Python 3.7 or later
- pip (Python package manager)
- wget (for downloading data)
- Approximately 2-3 GB of disk space for raw data and generated tiles

## Installation

### 1. Clone or download the project

```bash
cd raster-solar
```

### 2. Create a Python virtual environment

```bash
python3 -m venv solar-venv
source solar-venv/bin/activate  # On Windows: solar-venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install numpy shapely pyproj rasterio Pillow mercantile pytz
```

## Getting Started

### Step 1: Download timezone data

The first time you run the project, download the raw timezone data:

```bash
bash download_data.sh
```

This script downloads:
- Timezone boundary polygons (GeoJSON format)
- Timezone metadata with standard and DST offsets

### Step 2: Process the timezone data

Convert the raw timezone data into processed GeoJSON with solar noon offset calculations:

```bash
python process_combined.py
```

This creates:
- `processed-geojson/timezones_processed.geojson` - Processed timezone data with calculated offsets
- `processed-geojson/timezones_processed_montecarlo.geojson` - Alternative processing method (if using Monte-Carlo)

### Step 3: Generate visualization tiles

Generate the raster tiles for the web viewer:

```bash
python generate-tiles.py && python generate-tiles.py --dst --tile-dir 'tiles-dst'
```

This creates two sets of tiles:
- `tiles/` - Standard time tiles
- `tiles-dst/` - Daylight saving time tiles

The first command generates tiles showing standard time offsets, the second generates DST tiles.

### Step 4: View the map

Open `index.html` in your web browser:

```bash
open index.html  # On macOS
# or open the file manually in your browser
```

## Usage

### Basic Tile Generation

Generate tiles with default settings:
```bash
python generate-tiles.py
```

### Advanced Options

The `generate-tiles.py` script supports several command-line options:

```bash
python generate-tiles.py \
  --geojson processed-geojson/timezones_processed.geojson \
  --tile-dir tiles \
  --min-zoom 0 \
  --max-zoom 6 \
  --max-offset 40 \
  --dst
```

**Options:**
- `--geojson` (path): Input GeoJSON file (default: `processed-geojson/timezones_processed.geojson`)
- `--tile-dir` (path): Output directory for tiles (default: `tiles`)
- `--min-zoom` (int): Minimum zoom level (default: 0)
- `--max-zoom` (int): Maximum zoom level (default: 6)
- `--tile-size` (int): Tile size in pixels (default: 256)
- `--max-offset` (float): Maximum offset in degrees for color scaling (default: 40)
- `--dst`: Use DST offsets instead of standard time offsets

### Processing Options

The `process_combined.py` script also has configuration options:

```bash
python process_combined.py [--method {numeric|monte-carlo}]
```

The processing method affects how solar noon average offsets are calculated across irregular polygon areas.

## Data Files & Directories

### Input Data
- **raw-geojson/** - Downloaded timezone boundary polygons
  - Individual timezone `.geojson` files
  - `timezone-info.json` - Metadata mapping timezones to offsets

### Processed Data
- **processed-geojson/** - Processed timezone data
  - `timezones_processed.geojson` - Main processed file with calculated offsets

### Output
- **tiles/** - Standard time tile hierarchy
  - Organized by zoom level and tile coordinates
  - Each tile is a 256×256 PNG image
- **tiles-dst/** - Daylight saving time tiles
  - Same structure as `tiles/`

### Supporting Files
- **zips/** - Archive storage for downloaded dataset

## File Descriptions

### Python Scripts

**`generate-tiles.py`**
- Main tile generation script
- Converts timezone GeoJSON into Web Mercator raster tiles
- Colors each pixel based on the solar noon offset for its location
- Uses multiprocessing for performance
- Handles antimeridian (date line) crossing correctly

**`process_combined.py`**
- Data processing pipeline
- Loads raw timezone boundaries and metadata
- Calculates solar noon offset for each timezone region using circular mean
- Computes time-weighted offsets accounting for DST transitions
- Outputs enriched GeoJSON with calculated properties

**`diff.py`**
- Validation utility
- Compares two GeoJSON files for consistency
- Checks for missing or differing properties
- Useful for verifying data integrity

**`download_data.sh`**
- Bash script to download timezone data from Geoapify
- Creates necessary directories
- Fixes encoding issues in metadata

### Web Interface

**`index.html`**
- Interactive Leaflet-based map viewer
- Features:
  - Base map layer
  - Toggle between STD and DST layers
  - Hover popup showing timezone info
  - Click popup with detailed solar offset data
  - Chart visualization of equation of time

**`globe.html`**
- Alternative 3D globe visualization (optional)

## Understanding the Visualization

### Color Scheme

The tiles use a color gradient to represent solar noon offset:
- **Red tones** - Negative offset (solar noon occurs before local noon)
- **Blue/Green tones** - Positive offset (solar noon occurs after local noon)
- **Intensity** - Represents the magnitude of the offset

The offset is measured in degrees of longitude, where:
- 1 degree = 4 minutes of time difference
- 15 degrees = 1 hour

### Solar Noon vs Local Noon

The visualization shows the difference between:
- **Solar noon** - When the sun reaches its highest point (true solar time)
- **Local noon** - 12:00 on the clock (civil time)

Factors affecting this difference:
- **Timezone boundaries** - Boundaries often don't align with meridians
- **Reference meridians** - Standard meridians at 0°, ±15°, ±30°, etc.
- **Equation of time** - Additional 15-minute annual variation

## Performance Notes

- Tile generation can be slow for higher zoom levels (careful with MAX_ZOOM > 6)
- Uses multiprocessing to speed up tile creation
- Each zoom level roughly quadruples the number of tiles
- DST tiles must be generated separately

## Troubleshooting

**ImportError for spatial libraries**
```bash
pip install --upgrade shapely pyproj rasterio
```

**Out of memory during tile generation**
- Reduce `MAX_ZOOM` in `generate-tiles.py`
- Reduce `TILE_SIZE` (trades quality for speed)

**Download script fails**
- Ensure `wget` is installed
- Check internet connection
- Visit https://www.geoapify.com/data-share/timezones/ directly

**Data validation issues**
```bash
python diff.py processed-geojson/timezones_processed.geojson processed-geojson/timezones_processed_montecarlo.geojson
```

## Project Status

This project is **under active development**. See [plan.md](plan.md) for planned features and improvements.

## License

[Add your license here]

## References

- [Geoapify Timezone Data](https://www.geoapify.com/data-share/timezones/)
- [IANA Timezone Database](https://www.iana.org/time-zones)
- [Equation of Time](https://en.wikipedia.org/wiki/Equation_of_time)
- [Leaflet.js Documentation](https://leafletjs.com/)
