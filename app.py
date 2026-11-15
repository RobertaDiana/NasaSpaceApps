from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st

from data_service import CATALOGS, filter_catalog, load_catalog
from map_service import load_boundaries, raster_points

st.set_page_config(
    page_title="GAEZ v5 Data Dashboard",
    page_icon="🌾",
    layout="wide",
)

st.title("🌾 GAEZ v5 Data Dashboard")
st.caption(
    "The official FAO/IIASA catalog for exploration, filtering, and reuse "
    "in web applications."
)


@st.cache_data(ttl=3600, show_spinner="Loading the GAEZ catalog from FAO...")
def get_catalog(dataset_name: str) -> pd.DataFrame:
    return load_catalog(CATALOGS[dataset_name])


with st.sidebar:
    st.header("Dataset")
    dataset_name = st.selectbox("Choose a dataset", list(CATALOGS))
    st.divider()
    st.markdown(
        "**Source:** [GAEZ v5 Platform]"
        "(https://data.apps.fao.org/gaez/?lang=en)  \n"
        "**License:** CC BY 4.0"
    )

try:
    catalog = get_catalog(dataset_name)
except Exception as error:
    st.error(f"The catalog could not be loaded: {error}")
    st.stop()

with st.sidebar:
    st.header("Filters")

    def options(column: str) -> list[str]:
        return sorted(catalog[column].dropna().astype(str).unique())

    selected_variables = st.multiselect("Variable", options("VARIABLE"))
    selected_periods = st.multiselect("Period", options("PERIOD"))
    selected_climates = st.multiselect(
        "Climate source", options("CLIMATE_DATA_SOURCE")
    )
    selected_ssps = st.multiselect("SSP scenario", options("SSP"))
    selected_crops = st.multiselect("Crop", options("CROP"))
    selected_inputs = st.multiselect("Management / water", options("INPUT"))

filtered = filter_catalog(
    catalog,
    {
        "VARIABLE": selected_variables,
        "PERIOD": selected_periods,
        "CLIMATE_DATA_SOURCE": selected_climates,
        "SSP": selected_ssps,
        "CROP": selected_crops,
        "INPUT": selected_inputs,
    },
)

metric_columns = st.columns(4)
metric_columns[0].metric("Available files", f"{len(catalog):,}")
metric_columns[1].metric("Filtered results", f"{len(filtered):,}")
metric_columns[2].metric("Variables", filtered["VARIABLE"].nunique())
metric_columns[3].metric("Crops", filtered["CROP"].nunique())

st.subheader("Selection distribution")
chart_columns = st.columns(2)
with chart_columns[0]:
    st.caption("Files by period")
    st.bar_chart(filtered["PERIOD"].value_counts().sort_index())
with chart_columns[1]:
    st.caption("Files by crop — top 20")
    st.bar_chart(filtered["CROP"].value_counts().head(20))

regional_path = "data/romania_gaez_hp0120_hist.csv"
try:
    regional = pd.read_csv(regional_path)
except FileNotFoundError:
    regional = pd.DataFrame()

if not regional.empty:
    st.subheader("🗺️ Interactive Romania map")
    st.info(
        "Choose a county, crop, and indicator. The map is centered on "
        "Călărași, Ialomița, Constanța, or Tulcea. Cells are GAEZ pixels "
        "of approximately 5 arc-minutes, not cadastral cells."
    )
    map_columns = st.columns(4)
    region_labels = {
        "Calarasi": "Călărași",
        "Ialomita": "Ialomița",
        "Constanta": "Constanța",
        "Tulcea": "Tulcea",
    }
    region = map_columns[0].selectbox(
        "County / region",
        sorted(regional["region"].unique()),
        index=0,
        format_func=lambda value: region_labels.get(value, value),
        key="map_region",
    )
    map_variable = map_columns[1].selectbox(
        "Map indicator",
        ["RES05-SIX", "RES05-YLX", "RES02-WDE"],
        format_func=lambda value: {
            "RES05-SIX": "Suitability index",
            "RES05-YLX": "Attainable yield",
            "RES02-WDE": "WDe / water deficit",
        }[value],
        key="map_variable",
    )
    map_crop = map_columns[2].selectbox(
        "Crop",
        sorted(regional[regional["variable"] == map_variable]["crop"].unique()),
        key="map_crop",
    )
    map_management = map_columns[3].selectbox(
        "Management",
        sorted(regional["management"].unique()),
        key="map_management",
    )

    selected_rows = regional[
        (regional["region"] == region)
        & (regional["variable"] == map_variable)
        & (regional["crop"] == map_crop)
        & (regional["management"] == map_management)
        & (regional["status"] == "ok")
    ]
    if selected_rows.empty:
        st.warning("No raster is available for the selected combination.")
    else:
        selected = selected_rows.iloc[0]
        st.metric("Regional average", f"{selected['value_mean']:.2f}")
        boundaries = load_boundaries()
        points = raster_points(
            selected["source_url"], {region: boundaries[region]}
        )
        if points.empty:
            st.warning("The raster contains no valid pixels in the selected area.")
        else:
            deck = pdk.Deck(
                map_style=None,
                initial_view_state=pdk.ViewState(
                    latitude=points["latitude"].mean(),
                    longitude=points["longitude"].mean(),
                    zoom=8,
                ),
                layers=[
                    pdk.Layer(
                        "ScatterplotLayer",
                        data=points,
                        get_position="[longitude, latitude]",
                        get_radius=4500,
                        get_fill_color="[30, 136, 229, 170]",
                        pickable=True,
                    )
                ],
                tooltip={"text": "Value: {value}\nRegion: {region}"},
            )
            st.pydeck_chart(deck, use_container_width=True)
            st.caption(
                f"{len(points)} GAEZ cells displayed for "
                f"{region_labels.get(region, region)}."
            )

st.subheader("Filtered catalog")
st.caption(
    "Links open the original GeoTIFF raster. Download the CSV to "
    "share the selection with another application."
)

download_frame = filtered.copy()
download_frame["DOWNLOAD"] = download_frame["DOWNLOAD_URL"].map(
    lambda url: f'<a href="{url}" target="_blank">GeoTIFF</a>'
)
display_columns = [
    "MAPSET_CODE",
    "VARIABLE",
    "PERIOD",
    "CLIMATE_DATA_SOURCE",
    "SSP",
    "CROP",
    "INPUT",
    "DOWNLOAD",
]
st.write(
    download_frame[display_columns]
    .head(500)
    .to_html(escape=False, index=False),
    unsafe_allow_html=True,
)
if len(filtered) > 500:
    st.info("Showing the first 500 results. The CSV export includes all results.")

csv_bytes = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download CSV selection",
    data=csv_bytes,
    file_name="gaez_v5_selection.csv",
    mime="text/csv",
)

st.divider()
st.caption(
    "Data source: FAO & IIASA (2025), Global Agro-Ecological Zoning version 5. "
    "Accessed through the public FAO catalog."
)
