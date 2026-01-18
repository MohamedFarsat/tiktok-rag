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

## 4) (Optional) Enable fast local LLM answers with Ollama

Install Ollama and pull the default model (CPU-only, local HTTP):

```powershell
ollama pull llama3.2:3b-instruct
```

Fallback model if needed:

```powershell
ollama pull qwen2.5:3b-instruct
```

Check Ollama connectivity:

```powershell
python -m graphrag.cli ollama-check
```

## 5) Start the API server

```powershell
python -m uvicorn graphrag.api:app
```

## 6) Test the /query endpoint

```powershell
Invoke-WebRequest -UseBasicParsing -Method Post -Uri "http://127.0.0.1:8000/query" `
  -ContentType "application/json" `
  -Body '{"question":"Are graphic violence videos allowed?","platforms":["tiktok"],"use_llm":true,"llm_model":"llama3.2:3b-instruct"}' |
  Select-Object -Expand Content
```

To disable the LLM and use the deterministic formatter:

```powershell
Invoke-WebRequest -UseBasicParsing -Method Post -Uri "http://127.0.0.1:8000/query" `
  -ContentType "application/json" `
  -Body '{"question":"Are graphic violence videos allowed?","platforms":["tiktok"],"use_llm":false}' |
  Select-Object -Expand Content
```
