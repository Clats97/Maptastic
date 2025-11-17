# Maptastic Map Tile Downloader (Meshtastic/Meshcore)

High-throughput, integrity-checked offline map tile downloader for Thunderforest tiles, driven by an interactive CLI for devices that require map files such as the T-Deck. There is an executable version for Windows in the releases section.

> ** In typical Python tutorials and basic scripts, map tiles are often fetched sequentially, yielding effective download rates of **no more than ~5 tiles per second**.
> This script uses an optimized `requests` session, aggressive connection pooling, and up to **96 concurrent workers**, and in testing has achieved **sustained download rates in the ~400–600 tiles/second range**, depending on your API plan, network conditions, and target region size.

---

## Table of Contents

* [Overview](#overview)
* [Key Features](#key-features)
* [How It Works (High Level)](#how-it-works-high-level)
* [Requirements](#requirements)
* [Installation](#installation)
* [Configuration](#configuration)

  * [Thunderforest API Key](#thunderforest-api-key)
  * [Performance Tuning](#performance-tuning)
* [Usage](#usage)

  * [Running the Script](#running-the-script)
  * [Interactive Prompts](#interactive-prompts)
* [Region & Zoom Logic](#region--zoom-logic)
* [Tile Integrity & Auto-Recovery](#tile-integrity--auto-recovery)
* [Performance Characteristics](#performance-characteristics)

  * [Why It’s Faster Than Typical Scripts](#why-its-faster-than-typical-scripts)
  * [Measuring Your Own Throughput](#measuring-your-own-throughput)
* [Output Structure](#output-structure)
* [Troubleshooting](#troubleshooting)
* [API Usage, Fair Use & Legal Notes](#api-usage-fair-use--legal-notes)
* [Customization Ideas](#customization-ideas)

---

## Overview

This script allows you to interactively select:

* A **location name** (e.g. *“Ottawa, Ontario”*),
* A **buffer radius** in kilometers around that location,
* A **zoom range** (from 0–22), and
* A **map quality level** (low / medium / high),

and then downloads **Thunderforest raster map tiles** for the computed bounding box at all specified zoom levels.

All downloads are:

* **Multi-threaded**,
* **Connection-pooled**,
* **Retry-aware**, and
* **Integrity-checked** to ensure no tiles are missing or zero-byte.

---

## Key Features

1. **High Throughput Downloading**

   * Uses `ThreadPoolExecutor` with up to **96 workers**.
   * Optimized `requests.Session` with tuned connection pooling and retry logic.
   * In testing, has achieved **400–600 tiles/second**, compared to many basic scripts that do **≤5 tiles/second**.

2. **Interactive Region Selection**

   * Uses **Nominatim (OpenStreetMap geocoding)** to resolve a human-readable location.
   * Lets you specify a **buffer distance** (km) around the central point.
   * Automatically builds a **bounding box** using `geopy.distance.geodesic`.

3. **Flexible Zoom Range**

   * Supports zoom levels from **0 up to 22**.
   * You choose the **minimum** and **maximum** zoom interactively.

4. **Quality-Aware Tile Saving**

   * Supports a **“reduce level”** based on `low` / `medium` / `high` quality:

     * `low` → reduce from zoom ≥ 8
     * `medium` → reduce from zoom ≥ 12
     * `high` → essentially no reduction
   * Uses `Pillow` to quantize high-zoom tiles to 256 colors when reduction is enabled to save space.

5. **Robust Integrity Checking**

   * Keeps a list of **all expected tiles** for the region and zoom range.
   * Verifies:

     * Tile file exists, and
     * File size is **> 0 bytes**.
   * Detects missing and zero-byte tiles, deletes corrupt files, and **automatically re-downloads** them.
   * Retries up to **`MAX_RETRIES`** times with exponential backoff.

6. **User-Friendly CLI Experience**

   * ASCII art banner and branding.
   * Prompts with emojis and clear error messages.
   * Validates input paths and creates directories when needed.

---

## How It Works (High Level)

1. **Banner & Logging**

   * `print_banner()` prints a colored ASCII title and byline.
   * Logging is initialized at `INFO` level for useful runtime feedback.

2. **Geocoding & Region Definition**

   * `get_user_input()`:

     * Prompts for location string and uses `Nominatim` to geocode it.
     * Prompts for buffer distance and zoom range.
     * Computes north/south/east/west points from the center using `geopy.geodesic`.
     * Constructs a bounding box string: `max_lat,min_lon,min_lat,max_lon`.

3. **Tile Enumeration**

   * `InteractiveTileDownloader._tiles_for_bbox()`:

     * Converts lat/lon bounds to tile x/y ranges per zoom level using Web Mercator formulas.
     * Yields all `(z, x, y)` combinations inside the bounding box.

4. **Parallel Downloading**

   * `download_region()`:

     * Aggregates **all required tiles** across all zoom levels.
     * Performs an integrity check, then feeds missing/zero-byte tiles to a `ThreadPoolExecutor`.
     * Each worker uses `download_tile()` to fetch and save a single tile.

5. **Integrity + Retry**

   * After each parallel batch, the script re-checks tile files with `verify_tiles()`.
   * If any are missing or zero-byte, it retries with exponential backoff, up to `MAX_RETRIES`.

---

## Requirements

**Python:** 3.8+ is strongly recommended.

**Python packages:**

* `requests`
* `urllib3` (bundled with requests, but used for `Retry`)
* `Pillow` (`PIL`)
* `geopy`
* `tqdm`

**Other:**

* A valid **Thunderforest API key**.
* Internet connectivity.
* Enough disk space for all requested tiles.

---

## Installation

1. **Clone or copy the script** into a directory on your machine.

2. **Create and activate a virtual environment** (recommended):


3. **Install dependencies:**

```bash
pip install requests pillow geopy tqdm
```

---

## Configuration

### Thunderforest API Key

At the top of the script, set:

```python
HARDCODED_API_KEY = "YOUR_THUNDERFOREST_API_KEY_HERE"
```

> The script will refuse to run if this is blank or very short, and will log a **critical** error.

You can obtain an API key by registering at Thunderforest and selecting an appropriate plan. Be sure to comply with their **terms of service** and **rate limits**.

### Performance Tuning

The following constants control performance characteristics:

```python
MAX_WORKERS = 96
MAX_RETRIES = 50
CONNECT_TIMEOUT = 20
READ_TIMEOUT = 40
POOL_CONNECTIONS = 128
POOL_MAXSIZE = 128
```

* **`MAX_WORKERS`**: Maximum concurrent download threads.
* **`POOL_CONNECTIONS` / `POOL_MAXSIZE`**: Size of the HTTP connection pool.
* **`MAX_RETRIES`**: Total integrity-check rounds allowed (not per-tile retries inside `requests`).
* **`CONNECT_TIMEOUT` / `READ_TIMEOUT`**: Network timeouts in seconds.

You may want to **lower `MAX_WORKERS`** and pool sizes if:

* You are on a slow or unstable network, or
* You want to be extra conservative about load on Thunderforest’s infrastructure.

---

## Usage

### Running the Script

Git clone in your terminal (with the virtual environment active, if used), or download the repo as a zip file:

You will see the ASCII banner followed by an introduction:

```text
--- 🗺️ Meshtastic Map Tile Downloader ---
```

### Interactive Prompts

You will be walked through a series of prompts:

1. **Location Name**

   ```text
   📍 Enter the location name (e.g., 'Ottawa, Ontario'):
   ```

   * Example: `Ottawa, Ontario`
   * If the location is ambiguous, you’ll be asked to try again.

2. **Buffer Distance (km)**

   ```text
   📏 Enter a buffer distance in kilometers (e.g., 10):
   ```

   * This specifies how far from the center point to expand in all directions.
   * Values must be **≥ 0**.

3. **Zoom Levels**

   **Minimum zoom:**

   ```text
   🔍 Enter your minimum zoom level (0–22):
   ```

   **Maximum zoom:**

   ```text
      Enter your maximum zoom level (min–22):
   ```

   * `zoom_start` must be between 0 and 22.
   * `zoom_end` must be between `zoom_start` and 22.

4. **Quality (Reduction Level)**

   ```text
   🎨 Choose map quality [low, medium, high]:
   ```

   Mapped internally to:

   ```python
   quality_map = {"low": 8, "medium": 12, "high": 100}
   ```

   * For `low` and `medium`, tiles at zoom ≥ `reduce_level` are quantized to 256 colors.
   * `high` effectively disables aggressive reduction.

5. **Output Directory**

   ```text
   📂 Paste the full path for the download folder (e.g., C:\Users\Me\Desktop\Maps):
   ```

   * If the directory exists: it is used.
   * If not: the script attempts to create it.
   * On failure: you’ll be asked to specify another path.

---

## Region & Zoom Logic

Given:

* A central coordinate `(lat, lon)` from geocoding, and
* A buffer distance `buffer_km`,

the script computes:

* `north_point` (bearing 0°),
* `south_point` (bearing 180°),
* `east_point` (bearing 90°),
* `west_point` (bearing 270°),

via `geodesic(kilometers=buffer_km).destination(center_point, bearing)`.

From these, it derives:

* `max_lat = north_point.latitude`
* `min_lat = south_point.latitude`
* `min_lon = west_point.longitude`
* `max_lon = east_point.longitude`

This defines a **bounding box**:

```text
max_lat, min_lon, min_lat, max_lon
```

For each zoom level `z` in your selected range, the script converts these lat/lon bounds into tile indices `(x, y)` using standard Web Mercator formulas:

* `long_to_tile_x(lon, z)`
* `lat_to_tile_y(lat, z)`

It then enumerates **every tile** `(z, x, y)` that falls within the bounding box.

---

## Tile Integrity & Auto-Recovery

The script maintains a list of **all expected tiles** for the chosen region and zoom levels, and uses:

* `_check_tile_file(z, x, y)`
* `verify_tiles(tiles)`

to classify each tile’s file as:

* `"missing"` → file does not exist
* `"zero"` → file exists but size is 0 bytes or unreadable
* `"ok"` → file exists and size > 0

Any tile that is `"missing"` or `"zero"` is scheduled for (re)download.

On download:

* If a tile file already exists but is 0 bytes, it is **deleted** and **re-fetched**.
* If the HTTP status is 200 with non-empty content:

  * For zoom ≥ `reduce_level`, the image is quantized and re-encoded as PNG.
  * Otherwise, it is saved directly or converted to PNG if needed.
* HTTP status 404 is treated as a **missing tile**, logged but not fatal for the entire run.

After each batch:

* Another integrity pass is run.
* If tiles are still missing or zero, the script retries up to `MAX_RETRIES` times with exponential backoff.

If, after all retries, some tiles remain unresolved, the script logs:

* A summary of unresolved tile count, and
* Sample tile indices up to the first 5,000 unresolved tiles.

---

## Performance Characteristics

### Why It’s Faster Than Typical Scripts

Many basic map-downloader examples:

* Use a **single `requests.get()` loop**,
* Do **no connection pooling**, and
* Perform **no concurrency**.

As a result, they often top out around **a few tiles per second**, especially when using higher timeouts or when TLS setup dominates each new connection.

This script:

1. Uses a **single `Session`** with an `HTTPAdapter` configured for:

   * Large connection pools (`POOL_CONNECTIONS`, `POOL_MAXSIZE`).
   * Automatic retries for transient errors / rate limits.

2. Launches up to **`MAX_WORKERS`** download tasks in parallel via `ThreadPoolExecutor`.

3. Streams progress via **`tqdm`**, showing:

   * Total tiles downloaded,
   * Elapsed time,
   * Estimated remaining time, and
   * Live tiles/second rate.

> Under favorable conditions (good network, reasonable API allowance, nearby Thunderforest edge, and moderately sized regions), this script has demonstrated **sustained effective download rates of about 400–600 tiles per second**, whereas simple non-pooled, non-concurrent scripts often manage **no more than ~5 tiles per second**.

Actual performance will depend on:

* Your CPU,
* Your network bandwidth and latency,
* Current Thunderforest load and your plan limits,
* Size and shape of the requested region, and
* Selected zoom range.

### Measuring Your Own Throughput

The script already logs total elapsed time:

```text
Program finished successfully! Total time: X.XX seconds.
```

You can estimate tiles/sec as:

```text
tiles_per_second ≈ total_tiles / elapsed_seconds
```

Where `total_tiles` is logged as:

```text
Total tiles expected for integrity: N
```

For more granular metrics, you could add timing around each batch or around each worker, but for most use cases the global rate is sufficient.

---

## Output Structure

Downloaded tiles are stored in:

```text
<output_directory>/<MAP_PROVIDER>/<MAP_STYLE>/<z>/<x>/<y>.png
```

With current settings:

* `MAP_PROVIDER = "thunderforest"`
* `MAP_STYLE = "atlas"`

Example:

```text
C:\Maps\thunderforest\atlas\12\2175\1425.png
```

This folder structure is compatible with many applications that expect standard XYZ/Web-Mercator tile layouts.

---

## Troubleshooting

**1. “Location not found”**

* Make the search string more specific (e.g., `Ottawa, Ontario, Canada` instead of `Ottawa`).
* Ensure you have an Internet connection.
* Nominatim can rate limit excessive queries; avoid rapid repeated searches.

**2. API Key Errors**

* If the script logs that the API key is missing or invalid:

  * Confirm you’ve correctly updated `HARDCODED_API_KEY`.
  * Check that there are no leading/trailing spaces or quotes in your key.
  * Ensure your Thunderforest account is active and not over quota.

**3. Very Slow Downloads**

* This may be due to:

  * Local bandwidth constraints,
  * Thunderforest rate limits,
  * High latency to the server.

Potential mitigations:

* Reduce `MAX_WORKERS` (to be more polite and reduce local contention).
* Decrease zoom range (fewer total tiles).
* Reduce buffer radius.

**4. Frequent HTTP 429 or 5xx Errors**

* These usually indicate rate limiting or server issues.
* The built-in `Retry` configuration should handle occasional failures.
* If they persist:

  * Reduce concurrency (`MAX_WORKERS`),
  * Increase backoff, or
  * Schedule downloads at a less busy time.

**5. Zero-Byte Tiles After Completion**

* The script’s integrity check should automatically clean and re-download zero-byte tiles.
* If zero-byte files still appear:

  * Check disk health (e.g., permission issues or full disk).
  * Consider lowering concurrency.

---

## API Usage, Fair Use & Legal Notes

* Respect **Thunderforest’s terms of service**, rate limits, and licensing restrictions.
* Large-scale tile downloading may require a specific **plan** or **license**.
* Some uses (e.g., redistribution, commercial applications) may have specific contractual requirements.
* Nominatim usage is governed by the OpenStreetMap / Nominatim usage policies; avoid abusive querying.

---

## Customization Ideas

Here are some straightforward ways you could extend this script:

1. **Command-Line Arguments**

   * Allow passing location, buffer, zooms, and output directory via CLI flags instead of interactive prompts.

2. **Rate-Limit Aware Backoff**

   * Parse `Retry-After` headers more explicitly and adapt concurrency on the fly.

3. **Per-Zoom Folder Size Summary**

   * After download, summarize bytes used per zoom level to understand storage costs.

4. **Resume by Region File**

   * Save the list of expected tiles to a JSON file and allow resuming later without re-geocoding.

5. **Multi-Provider Support**

   * Abstract provider URLs so that other XYZ tile providers could be used with their own API keys and terms.

---tiles into a Meshtastic/LoRa mapping workflow).

