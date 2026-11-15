# GAEZ v5 Data Dashboard

Streamlit dashboard for exploring official GAEZ v5 catalogs and exporting
selections for a web application.

## Local setup

In PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

On first load, the app reads the official FAO Excel catalogs for RES02 and
RES05. Data is cached for one hour; GeoTIFF rasters are not downloaded
automatically, but are available through the links in the table.

## Reusable components

- `data_service.py` handles catalog loading, URL construction, and filtering
  without depending on the Streamlit interface;
- filtered selections can be exported as CSV;
- each row retains the public URL to the original raster;
- the interactive map displays GAEZ raster cells (not cadastral cells).

## Data citation

FAO & IIASA (2025), *Global Agro-Ecological Zoning version 5*,
https://data.apps.fao.org/gaez/, licensed under CC BY 4.0.

## Local AI assistant (optional)

`index.html` includes an assistant that explains crop recommendations.
It uses local Ollama without an API key or sending GAEZ data to an external
service.

Install Ollama from https://ollama.com/download/windows, then run in PowerShell:

```powershell
ollama pull qwen2.5:3b
ollama serve
```

If the browser blocks the CORS request, restart Ollama with:

```powershell
$env:OLLAMA_ORIGINS="*"
ollama serve
```

In the dashboard, keep the `qwen2.5:3b` model and click **Analyze**.
