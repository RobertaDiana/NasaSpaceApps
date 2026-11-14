# GAEZ v5 Data Dashboard

Dashboard Streamlit pentru explorarea cataloagelor oficiale GAEZ v5 și
exportarea selecțiilor pentru o aplicație web.

## Pornire locală

În PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

La prima încărcare, aplicația citește cataloagele Excel oficiale FAO pentru
RES02 și RES05. Datele sunt păstrate în cache timp de o oră; rasterele GeoTIFF
nu sunt descărcate automat, ci sunt disponibile prin linkurile din tabel.

## Ce poate fi reutilizat

- `data_service.py` conține încărcarea catalogului, construirea URL-urilor și
  filtrarea, fără dependență de interfața Streamlit;
- selecția filtrată poate fi exportată ca CSV;
- fiecare rând păstrează URL-ul public către rasterul original.
- harta interactivă afișează celulele raster GAEZ (nu parcele cadastrale).

## Citarea datelor

FAO & IIASA (2025), *Global Agro-Ecological Zoning version 5*,
https://data.apps.fao.org/gaez/, licență CC BY 4.0.

## Asistent AI local (opțional)

`solutie.html` include un asistent pentru explicarea beneficiilor unei culturi.
Acesta folosește Ollama local, fără API key și fără trimiterea datelor GAEZ către
un serviciu extern.

Instalează Ollama de la https://ollama.com/download/windows, apoi în PowerShell:

```powershell
ollama pull qwen2.5:3b
ollama serve
```

Dacă browserul blochează cererea CORS, repornește Ollama cu:

```powershell
$env:OLLAMA_ORIGINS="*"
ollama serve
```

În dashboard, păstrează modelul `qwen2.5:3b` și apasă **Analizează**.
