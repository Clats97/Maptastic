import logging
import time
from math import floor, pi, tan, cos, log as ln
from os import makedirs, remove
from os.path import join as join_path, exists, isdir, getsize
from sys import exit
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from PIL import Image
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from tqdm import tqdm

HARDCODED_API_KEY = "YOUR_THUNDERFOREST_API_KEY_HERE"
MAX_WORKERS = 96
MAX_RETRIES = 50
MAP_PROVIDER = "thunderforest"
MAP_STYLE = "atlas"
CONNECT_TIMEOUT = 20
READ_TIMEOUT = 40
POOL_CONNECTIONS = 128
POOL_MAXSIZE = 128


def print_banner():
    red = "\033[31m"
    blue = "\033[34m"
    reset = "\033[0m"

    ascii_art = [
        "███╗   ███╗ █████╗ ██████╗ ████████╗ █████╗ ███████╗████████╗██╗ ██████╗",
        "████╗ ████║██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗██╔════╝╚══██╔══╝██║██╔════╝",
        "██╔████╔██║███████║██████╔╝   ██║   ███████║███████╗   ██║   ██║██║     ",
        "██║╚██╔╝██║██╔══██║██╔═══╝    ██║   ██╔══██║╚════██║   ██║   ██║██║     ",
        "██║ ╚═╝ ██║██║  ██║██║        ██║   ██║  ██║███████║   ██║   ██║╚██████╗",
        "╚═╝     ╚═╝╚═╝  ╚═╝╚═╝        ╚═╝   ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝ ╚═════╝",
    ]

    subtitle_text = "M A P   T I L E   D O W N L O A D E R"
    version_text = "Version 1.00"
    byline_text = "By Joshua M Clatney - Ethical Pentesting Enthusiast"

    try:
        columns = shutil.get_terminal_size(fallback=(120, 30)).columns
    except Exception:
        columns = 120

    for line in ascii_art:
        print(red + line.center(columns) + reset)

    combined = subtitle_text
    spacing = "   "
    colored_line = blue + subtitle_text + reset + spacing + red + version_text + reset
    total_length = len(subtitle_text) + len(spacing) + len(version_text)
    padding = max(0, (columns - total_length) // 2)
    print(" " * padding + colored_line)

    print(byline_text.center(columns))


class InteractiveTileDownloader:
    def __init__(self, api_key, output_directory, reduce_level):
        if not api_key:
            raise ValueError("API key cannot be empty.")
        self.api_key = api_key
        self.output_directory = output_directory
        self.reduce_level = reduce_level
        self.provider_url = "https://tile.thunderforest.com/{style}/{z}/{x}/{y}.png?apikey={key}"
        self.session = self._build_session()

    @staticmethod
    def _build_session() -> Session:
        session = Session()
        retry = Retry(
            total=8,
            connect=6,
            read=6,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504, 520, 522, 524],
            allowed_methods=["GET", "HEAD"],
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(
            pool_connections=POOL_CONNECTIONS,
            pool_maxsize=POOL_MAXSIZE,
            max_retries=retry,
        )
        session.mount("https://", adapter)
        session.headers.update(
            {
                "User-Agent": "MapTileDownloader/2.0 (+https://thunderforest.com; contact: user@example)",
                "Accept": "image/avif,image/webp,image/*;q=0.8,*/*;q=0.5",
                "Cache-Control": "no-cache",
            }
        )
        return session

    @staticmethod
    def long_to_tile_x(lon, zoom):
        return int(floor(((lon + 180.0) / 360.0) * (2 ** zoom)))

    @staticmethod
    def lat_to_tile_y(lat, zoom):
        return int(
            floor(
                ((1.0 - ln(tan((lat * pi) / 180.0) + 1.0 / cos((lat * pi) / 180.0)) / pi) / 2.0)
                * (2 ** zoom)
            )
        )

    def tile_path(self, z, x, y):
        return join_path(self.output_directory, MAP_PROVIDER, MAP_STYLE, str(z), str(x), f"{y}.png")

    @staticmethod
    def _process_image(image_bytes):
        img = Image.open(BytesIO(image_bytes))
        return img.convert("RGB") if getattr(img, "has_transparency_data", False) else img

    def _reduce_and_save_tile(self, image_bytes, destination):
        image = self._process_image(image_bytes)
        quantized_image = image.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        quantized_image.save(destination, format="PNG", optimize=True)

    def _save_tile(self, image_bytes, destination, content_type):
        if not (content_type or "").startswith("image/png"):
            image = self._process_image(image_bytes)
            image.save(destination, format="PNG", optimize=True)
        else:
            with open(destination, "wb") as file:
                file.write(image_bytes)

    def _url_for(self, z: int, x: int, y: int) -> str:
        return self.provider_url.format(style=MAP_STYLE, z=z, x=x, y=y, key=self.api_key)

    def download_tile(self, zoom, x, y):
        tile_path = self.tile_path(zoom, x, y)

        if exists(tile_path):
            try:
                size = getsize(tile_path)
            except OSError:
                size = 0
            if size > 0:
                return True
            try:
                remove(tile_path)
                logging.warning(f"Zero-byte or unreadable tile detected and removed before re-download: {zoom}/{x}/{y}")
            except OSError as e:
                logging.error(f"Failed to remove corrupt tile {zoom}/{x}/{y}: {e}")

        tile_dir = join_path(self.output_directory, MAP_PROVIDER, MAP_STYLE, str(zoom), str(x))
        makedirs(tile_dir, exist_ok=True)
        url = self._url_for(zoom, x, y)

        try:
            resp = self.session.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            if resp.status_code == 200 and resp.content:
                if zoom >= self.reduce_level:
                    self._reduce_and_save_tile(resp.content, tile_path)
                else:
                    self._save_tile(resp.content, tile_path, resp.headers.get("content-type", ""))
                return True
            if resp.status_code == 404:
                logging.error(f"Missing tile (404) {zoom}/{x}/{y}")
                return False
            logging.error(f"Failed tile {zoom}/{x}/{y}: HTTP {resp.status_code}")
            return False
        except Exception as e:
            logging.error(f"Failed tile {zoom}/{x}/{y}: {e}")
            return False

    def _tiles_for_bbox(self, max_lat, min_lon, min_lat, max_lon, zoom):
        start_x = self.long_to_tile_x(min_lon, zoom)
        end_x = self.long_to_tile_x(max_lon, zoom)
        start_y = self.lat_to_tile_y(max_lat, zoom)
        end_y = self.lat_to_tile_y(min_lat, zoom)
        x0, x1 = sorted((start_x, end_x))
        y0, y1 = sorted((start_y, end_y))
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                yield {"z": zoom, "x": x, "y": y}

    def _check_tile_file(self, z, x, y):
        path = self.tile_path(z, x, y)
        if not exists(path):
            return "missing"
        try:
            size = getsize(path)
        except OSError:
            return "zero"
        if size <= 0:
            return "zero"
        return "ok"

    def verify_tiles(self, tiles):
        missing_or_zero = []
        missing_count = 0
        zero_count = 0

        for t in tiles:
            status = self._check_tile_file(t["z"], t["x"], t["y"])
            if status == "missing":
                missing_or_zero.append(t)
                missing_count += 1
            elif status == "zero":
                missing_or_zero.append(t)
                zero_count += 1

        if missing_count or zero_count:
            logging.warning(
                f"Integrity check: {missing_count} tiles missing, {zero_count} tiles zero bytes or unreadable."
            )
        else:
            logging.info("Integrity check: all expected tiles are present and non-empty.")

        return missing_or_zero

    def download_region(self, region_coords: str, zoom_levels: range):
        max_lat, min_lon, min_lat, max_lon = list(map(float, region_coords.split(",")))

        all_required_tiles = []
        for z in zoom_levels:
            all_required_tiles.extend(self._tiles_for_bbox(max_lat, min_lon, min_lat, max_lon, z))

        if not all_required_tiles:
            logging.warning("No tiles found for the specified region and zoom levels.")
            return True

        logging.info(f"Total tiles expected for integrity: {len(all_required_tiles)}")

        for attempt in range(MAX_RETRIES + 1):
            missing = self.verify_tiles(all_required_tiles)
            if not missing:
                logging.info("Verification complete. All tiles have been successfully downloaded and verified.")
                return True

            if attempt == 0:
                logging.info(f"Starting initial download for {len(missing)} tiles.")
            else:
                logging.warning(
                    f"{len(missing)} tiles still missing or zero-byte. Retrying download (attempt {attempt}/{MAX_RETRIES})."
                )

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [executor.submit(self.download_tile, t["z"], t["x"], t["y"]) for t in missing]
                pbar_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
                desc = f"Retrying (Att. {attempt})" if attempt > 0 else "Downloading Tiles"
                with tqdm(total=len(futures), desc=desc, bar_format=pbar_format, unit="tile") as pbar:
                    for fut in as_completed(futures):
                        _ = fut.result()
                        pbar.update(1)

            if attempt < MAX_RETRIES:
                sleep_s = min(30, 2 ** min(attempt, 5)) + (0.25 * attempt)
                time.sleep(sleep_s)

        final_missing = self.verify_tiles(all_required_tiles)
        if final_missing:
            logging.error(
                f"Download failed. {len(final_missing)} tiles remain missing or zero-byte after {MAX_RETRIES} retries."
            )
            for t in final_missing[:5000]:
                logging.error(f"Unresolved tile after retries: z={t['z']} x={t['x']} y={t['y']}")
        else:
            logging.info("All tiles appear present and non-empty after final integrity check, despite retry exhaustion.")
        return False


def get_user_input():
    geolocator = Nominatim(user_agent="map-tile-downloader")
    location = None
    while not location:
        try:
            location_str = input("📍 Enter the location name (e.g., 'Ottawa, Ontario'): ").strip()
            location = geolocator.geocode(location_str, timeout=15)
            if not location:
                print("❌ Location not found. Please be more specific.")
        except Exception as e:
            print(f"An error occurred during geocoding: {e}")

    print(f"✅ Location found: {location.address} ({location.latitude:.4f}, {location.longitude:.4f})")

    buffer_km = -1
    while buffer_km < 0:
        try:
            buffer_km = float(input("📏 Enter a buffer distance in kilometers (e.g., 10): "))
            if buffer_km < 0:
                print("❌ Distance must be a positive number.")
        except ValueError:
            print("❌ Invalid input. Please enter a number.")

    max_possible_zoom = 22

    while True:
        try:
            zoom_start = int(input("🔍 Enter your minimum zoom level (0–22): "))
            if 0 <= zoom_start <= max_possible_zoom:
                break
            print("❌ Zoom must be between 0 and 22.")
        except ValueError:
            print("❌ Invalid input. Please enter a whole number.")

    while True:
        try:
            zoom_end = int(input(f"   Enter your maximum zoom level ({zoom_start}–22): "))
            if zoom_start <= zoom_end <= max_possible_zoom:
                break
            print(f"❌ End zoom must be between {zoom_start} and 22.")
        except ValueError:
            print("❌ Invalid input. Please enter a whole number.")

    quality_map = {"low": 8, "medium": 12, "high": 100}
    reduce_level = 0
    while reduce_level == 0:
        quality = input("🎨 Choose map quality [low, medium, high]: ").lower().strip()
        if quality in quality_map:
            reduce_level = quality_map[quality]
        else:
            print("❌ Invalid choice. Please enter 'low', 'medium', or 'high'.")

    output_path = ""
    while not output_path:
        path_str = input(r"📂 Paste the full path for the download folder (e.g., C:\Users\Me\Desktop\Maps): ").strip().strip('"')
        if isdir(path_str):
            output_path = path_str
            print("✅ Path is valid.")
        else:
            try:
                makedirs(path_str, exist_ok=True)
                output_path = path_str
                print("✅ Path did not exist, but was created successfully.")
            except OSError as e:
                print(f"❌ Invalid path. Could not create directory. Please try again. Error: {e}")

    center_point = (location.latitude, location.longitude)
    north_point = geodesic(kilometers=buffer_km).destination(center_point, 0)
    south_point = geodesic(kilometers=buffer_km).destination(center_point, 180)
    east_point = geodesic(kilometers=buffer_km).destination(center_point, 90)
    west_point = geodesic(kilometers=buffer_km).destination(center_point, 270)

    max_lat = north_point.latitude
    min_lat = south_point.latitude
    min_lon = west_point.longitude
    max_lon = east_point.longitude

    region_str = f"{max_lat},{min_lon},{min_lat},{max_lon}"

    return {
        "region": region_str,
        "zoom_range": range(zoom_start, zoom_end + 1),
        "reduce_level": reduce_level,
        "output_path": output_path,
    }


def main():
    print_banner()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    print("--- 🗺️ Meshtastic Map Tile Downloader ---")

    if not HARDCODED_API_KEY or len(HARDCODED_API_KEY) < 20:
        logging.critical("API key is missing or invalid. Please edit the script and set HARDCODED_API_KEY.")
        exit(1)

    try:
        user_config = get_user_input()
        downloader = InteractiveTileDownloader(
            api_key=HARDCODED_API_KEY,
            output_directory=user_config["output_path"],
            reduce_level=user_config["reduce_level"],
        )

        logging.info(f"Starting download for region: {user_config['region']}")
        logging.info(f"Zoom levels: {user_config['zoom_range'].start} to {user_config['zoom_range'].stop - 1}")
        logging.info(f"Output directory: {user_config['output_path']}")

        start_time = time.time()
        success = downloader.download_region(
            region_coords=user_config["region"], zoom_levels=user_config["zoom_range"]
        )
        end_time = time.time()

        if success:
            logging.info(f"Program finished successfully! Total time: {end_time - start_time:.2f} seconds.")
            logging.info(f"Your maps are saved in: {user_config['output_path']}")
        else:
            logging.error("Program finished with errors. Some map tiles could not be downloaded or verified.")

    except (KeyboardInterrupt, SystemExit):
        logging.info("Process interrupted by user. Exiting.")
        exit(0)
    except Exception as e:
        logging.critical(f"An unexpected error occurred: {e}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    main()
