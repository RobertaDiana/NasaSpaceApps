from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from rasterio.mask import mask
from rasterio.io import MemoryFile

from data_service import CATALOGS, filter_catalog, load_catalog

BOUNDARIES_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_ROU_1.json"
REGIONS = {
    "C\u0103l\u0103ra\u0219i": "Calarasi",
    "Ialomi\u021ba": "Ialomita",
    "Constan\u021ba": "Constanta",
    "Tulcea": "Tulcea",
}


def load_boundaries(timeout: int = 120) -> dict[str, dict]:
    response = requests.get(BOUNDARIES_URL, timeout=timeout)
    response.raise_for_status()
    features = response.json()["features"]
    return {
        REGIONS[feature["properties"]["NAME_1"]]: feature["geometry"]
        for feature in features
        if feature["properties"]["NAME_1"] in REGIONS
    }


def raster_means(
    url: str, geometries: dict[str, dict], timeout: int = 180
) -> dict[str, tuple[float, int, str]]:
    response = requests.get(url, timeout=timeout)
    if response.status_code == 404:
        return {region: (float("nan"), 0, "missing") for region in geometries}
    response.raise_for_status()
    result = {}
    with MemoryFile(BytesIO(response.content)) as memory_file:
        with memory_file.open() as dataset:
            for region, geometry in geometries.items():
                values, _ = mask(dataset, [geometry], crop=True, filled=False)
                valid = values[0].compressed()
                if not len(valid):
                    result[region] = (float("nan"), 0, "no_valid_pixels")
                else:
                    result[region] = (float(valid.mean()), int(len(valid)), "ok")
    return result


def extract(output: Path, period: str = "HP0120", scenario: str = "HIST") -> None:
    boundaries = load_boundaries()
    res05 = load_catalog(CATALOGS["RES05 - Randament realizabil"])
    res02 = load_catalog(CATALOGS["RES02 - Potențial agroclimatic"])

    res05 = filter_catalog(
        res05,
        {
            "PERIOD": [period],
            "SSP": [scenario],
            "MAPSET_CODE": ["RES05-SIX", "RES05-YLX"],
        },
    )
    res02 = filter_catalog(
        res02,
        {
            "PERIOD": [period],
            "SSP": [scenario],
            "MAPSET_CODE": ["RES02-WDE"],
        },
    )

    items = list(pd.concat([res05, res02]).to_dict("records"))

    def process_item(item: dict) -> list[dict]:
        variable = str(item["MAPSET_CODE"])
        region_results = raster_means(item["DOWNLOAD_URL"], boundaries)
        item_rows = []
        for region in boundaries:
            mean, pixels, status = region_results[region]
            item_rows.append(
                {
                    "region": region,
                    "variable": variable,
                    "crop": item["CROP"],
                    "management": item["INPUT"],
                    "period": item["PERIOD"],
                    "scenario": item["SSP"],
                    "value_mean": mean,
                    "valid_pixels": pixels,
                    "status": status,
                    "source_url": item["DOWNLOAD_URL"],
                }
            )
        return item_rows

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_item, item): item for item in items}
        for index, future in enumerate(as_completed(futures), start=1):
            item = futures[future]
            rows.extend(future.result())
            print(f"[{index}/{len(items)}] {item['FILE_NAME']}", flush=True)

    result = pd.DataFrame(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    print(f"Saved {len(result):,} rows to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract GAEZ v5 statistics for Romania.")
    parser.add_argument("--output", type=Path, default=Path("data/romania_gaez.csv"))
    parser.add_argument("--period", default="HP0120")
    parser.add_argument("--scenario", default="HIST")
    args = parser.parse_args()
    extract(args.output, args.period, args.scenario)
