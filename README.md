# Running the Backend (Windows / PowerShell)

## 1) Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 2) Install dependencies

```powershell
pip install -r requirements.txt
```

## 3) Set data paths (from repo root)

```powershell
$env:GRAPHRAG_NODES="data\nodes.jsonl"
$env:GRAPHRAG_EDGES="data\edges.jsonl"
```

## 4) Start the API server

```powershell
python -m uvicorn graphrag.api:app
```

## 5) Test the /query endpoint

```powershell
Invoke-WebRequest -UseBasicParsing -Method Post -Uri "http://127.0.0.1:8000/query" `
  -ContentType "application/json" `
  -Body '{"question":"Are graphic violence videos allowed?","platforms":["tiktok"]}' |
  Select-Object -Expand Content
```
