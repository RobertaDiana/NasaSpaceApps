from __future__ import annotations

from io import BytesIO

import pandas as pd
import requests
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.transform import xy

from extract_romania import BOUNDARIES_URL, REGIONS


def load_boundaries(timeout: int = 120) -> dict[str, dict]:
    response = requests.get(BOUNDARIES_URL, timeout=timeout)
    response.raise_for_status()
    return {
        REGIONS[name]: feature["geometry"]
        for feature in response.json()["features"]
        if (name := feature["properties"]["NAME_1"]) in REGIONS
    }


def raster_points(
    url: str, boundaries: dict[str, dict], timeout: int = 180
) -> pd.DataFrame:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    rows: list[dict] = []
    with MemoryFile(BytesIO(response.content)) as memory_file:
        with memory_file.open() as dataset:
            for region, geometry in boundaries.items():
                values, transform = mask(
                    dataset, [geometry], crop=True, filled=False
                )
                band = values[0]
                valid_rows, valid_columns = band.nonzero()
                for row, column in zip(valid_rows, valid_columns):
                    value = band[row, column]
                    longitude, latitude = xy(transform, row, column)
                    rows.append(
                        {
                            "region": region,
                            "latitude": latitude,
                            "longitude": longitude,
                            "value": float(value),
                        }
                    )
    return pd.DataFrame(rows)
