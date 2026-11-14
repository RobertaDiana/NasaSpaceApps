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
    "Catalogul oficial FAO/IIASA pentru explorare, filtrare și reutilizare "
    "în aplicații web."
)


@st.cache_data(ttl=3600, show_spinner="Se încarcă catalogul GAEZ de la FAO...")
def get_catalog(dataset_name: str) -> pd.DataFrame:
    return load_catalog(CATALOGS[dataset_name])


with st.sidebar:
    st.header("Dataset")
    dataset_name = st.selectbox("Alege tema", list(CATALOGS))
    st.divider()
    st.markdown(
        "**Sursă:** [GAEZ v5 Platform]"
        "(https://data.apps.fao.org/gaez/?lang=en)  \n"
        "**Licență:** CC BY 4.0"
    )

try:
    catalog = get_catalog(dataset_name)
except Exception as error:
    st.error(f"Catalogul nu a putut fi încărcat: {error}")
    st.stop()

with st.sidebar:
    st.header("Filtre")

    def options(column: str) -> list[str]:
        return sorted(catalog[column].dropna().astype(str).unique())

    selected_variables = st.multiselect("Variabilă", options("VARIABLE"))
    selected_periods = st.multiselect("Perioadă", options("PERIOD"))
    selected_climates = st.multiselect(
        "Sursă climatică", options("CLIMATE_DATA_SOURCE")
    )
    selected_ssps = st.multiselect("Scenariu SSP", options("SSP"))
    selected_crops = st.multiselect("Cultură", options("CROP"))
    selected_inputs = st.multiselect("Management / apă", options("INPUT"))

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
metric_columns[0].metric("Fișiere disponibile", f"{len(catalog):,}")
metric_columns[1].metric("Rezultate filtrate", f"{len(filtered):,}")
metric_columns[2].metric("Variabile", filtered["VARIABLE"].nunique())
metric_columns[3].metric("Culturi", filtered["CROP"].nunique())

st.subheader("Distribuția selecției")
chart_columns = st.columns(2)
with chart_columns[0]:
    st.caption("Fișiere pe perioadă")
    st.bar_chart(filtered["PERIOD"].value_counts().sort_index())
with chart_columns[1]:
    st.caption("Fișiere pe cultură — primele 20")
    st.bar_chart(filtered["CROP"].value_counts().head(20))

regional_path = "data/romania_gaez_hp0120_hist.csv"
try:
    regional = pd.read_csv(regional_path)
except FileNotFoundError:
    regional = pd.DataFrame()

if not regional.empty:
    st.subheader("🗺️ Harta interactivă România")
    st.info(
        "Alege un județ, o cultură și un indicator. Harta este centrată pe "
        "Călărași, Ialomița, Constanța sau Tulcea. Celulele sunt pixeli GAEZ "
        "de aproximativ 5 arc-minute, nu parcele cadastrale."
    )
    map_columns = st.columns(4)
    region_labels = {
        "Calarasi": "Călărași",
        "Ialomita": "Ialomița",
        "Constanta": "Constanța",
        "Tulcea": "Tulcea",
    }
    region = map_columns[0].selectbox(
        "Județ / zonă",
        sorted(regional["region"].unique()),
        index=0,
        format_func=lambda value: region_labels.get(value, value),
        key="map_region",
    )
    map_variable = map_columns[1].selectbox(
        "Indicator hartă",
        ["RES05-SIX", "RES05-YLX", "RES02-WDE"],
        format_func=lambda value: {
            "RES05-SIX": "Suitability index",
            "RES05-YLX": "Attainable yield",
            "RES02-WDE": "WDe / water deficit",
        }[value],
        key="map_variable",
    )
    map_crop = map_columns[2].selectbox(
        "Cultură",
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
        st.warning("Nu există un raster disponibil pentru combinația selectată.")
    else:
        selected = selected_rows.iloc[0]
        st.metric("Media regională", f"{selected['value_mean']:.2f}")
        boundaries = load_boundaries()
        points = raster_points(
            selected["source_url"], {region: boundaries[region]}
        )
        if points.empty:
            st.warning("Rasterul nu conține pixeli valizi în zona selectată.")
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
                tooltip={"text": "Valoare: {value}\nRegiune: {region}"},
            )
            st.pydeck_chart(deck, use_container_width=True)
            st.caption(
                f"{len(points)} celule GAEZ afișate pentru "
                f"{region_labels.get(region, region)}."
            )

st.subheader("Catalog filtrat")
st.caption(
    "Linkurile deschid rasterul GeoTIFF original. Descarcă CSV-ul pentru "
    "a transmite selecția către o altă aplicație."
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
    st.info("Se afișează primele 500 de rezultate. Exportul CSV include toate rezultatele.")

csv_bytes = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Descarcă selecția CSV",
    data=csv_bytes,
    file_name="gaez_v5_selection.csv",
    mime="text/csv",
)

st.divider()
st.caption(
    "Sursa datelor: FAO & IIASA (2025), Global Agro-Ecological Zoning version 5. "
    "Accesată prin catalogul public FAO."
)
