from __future__ import annotations

from io import BytesIO
from typing import Final
from urllib.parse import quote

import pandas as pd
import requests

BASE_URL: Final = (
    "https://storage.googleapis.com/"
    "fao-gismgr-gaez-v5-data/DATA/GAEZ-V5/MAPSET"
)

CATALOGS: Final = {
    "RES02 - Potențial agroclimatic": (
        "https://data.apps.fao.org/catalog/dataset/"
        "4316025e-fc69-47bc-a1af-09f140ea8c52/resource/"
        "bc7d61b2-20bc-4691-84fc-06d92cf51266/download/_readme_res02.xlsx"
    ),
    "RES05 - Randament realizabil": (
        "https://data.apps.fao.org/catalog/dataset/"
        "514c92d5-9e01-4c70-814a-80ea1ca9fe6a/resource/"
        "768b08ad-be9c-427a-84be-3a3d6dd7835a/download/_readme_res05.xlsx"
    ),
}

EXPECTED_COLUMNS: Final = (
    "MAPSET_CODE",
    "PERIOD",
    "CLIMATE_DATA_SOURCE",
    "SSP",
    "CROP",
    "INPUT",
    "FILE_NAME",
)


def _clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [str(column).strip().upper() for column in frame.columns]
    for column in frame.columns:
        frame[column] = frame[column].astype("string").str.strip()
        frame.loc[frame[column].isin(["", "NAN", "NONE"]), column] = pd.NA
    return frame.dropna(how="all")


def _read_list_files(excel: BytesIO) -> pd.DataFrame:
    raw = pd.read_excel(excel, sheet_name="LIST_FILES", header=None, dtype=str)
    header_row = None
    best_score = 0

    for index in range(min(40, len(raw))):
        values = {str(value).strip().upper() for value in raw.iloc[index].tolist()}
        score = sum(column in values for column in EXPECTED_COLUMNS)
        if score > best_score:
            best_score = score
            header_row = index

    if header_row is None or best_score < 4:
        raise ValueError("Catalogul GAEZ nu conține un antet LIST_FILES valid.")

    columns = [str(value).strip().upper() for value in raw.iloc[header_row].tolist()]
    catalog = raw.iloc[header_row + 1 :].copy()
    catalog.columns = columns
    catalog = catalog.loc[:, [column for column in catalog.columns if column]]
    missing = [column for column in EXPECTED_COLUMNS if column not in catalog.columns]
    if missing:
        raise ValueError(f"Lipsesc coloane din catalogul GAEZ: {', '.join(missing)}")

    catalog = _clean_frame(catalog[list(EXPECTED_COLUMNS)])
    if "VARIABLE" not in catalog.columns:
        catalog.insert(
            1,
            "VARIABLE",
            catalog["MAPSET_CODE"].astype(str).str.split("-", n=1).str[-1],
        )
    return catalog.dropna(subset=["FILE_NAME"]).reset_index(drop=True)


def build_download_url(row: pd.Series) -> str:
    filename = str(row["FILE_NAME"]).strip()
    if not filename.lower().endswith(".tif"):
        filename += ".tif"
    return f"{BASE_URL}/{quote(str(row['MAPSET_CODE']))}/{quote(filename)}"


def load_catalog(catalog_url: str, timeout: int = 120) -> pd.DataFrame:
    response = requests.get(catalog_url, timeout=timeout)
    response.raise_for_status()
    catalog = _read_list_files(BytesIO(response.content))
    catalog["DOWNLOAD_NAME"] = catalog["FILE_NAME"].astype(str).where(
        catalog["FILE_NAME"].str.lower().str.endswith(".tif"),
        catalog["FILE_NAME"].astype(str) + ".tif",
    )
    catalog["DOWNLOAD_URL"] = catalog.apply(build_download_url, axis=1)
    return catalog


def filter_catalog(catalog: pd.DataFrame, filters: dict[str, list[str]]) -> pd.DataFrame:
    result = catalog
    for column, values in filters.items():
        if values:
            result = result[result[column].isin(values)]
    return result.reset_index(drop=True)
