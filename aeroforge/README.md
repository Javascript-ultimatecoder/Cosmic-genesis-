# AeroForge+

Insane v2 FastAPI app for paper airplane optimization with upload support, physics-inspired simulation, and PDF reporting.

## Features
- Upload image or PDF design references
- Multi-objective optimization modes (Distance / Airtime / Height / Hybrid)
- Extreme search mode for wider optimization loops
- Unique downloadable PDF optimization report per run
- Mobile-friendly modern UI with radar/pentagon ability chart
- Live in-memory leaderboard endpoint and UI panel
- Microsoft/Google login stub endpoints for OAuth integration
- Ready for Render deployment

## Python version
- Python **3.11+** recommended (Python 3 required).

## Run locally
```bash
cd aeroforge
pip install -r requirements.txt
python3 -m uvicorn aeroforge_app:app --reload
```

## Deploy on Render
- **Build Command**
```bash
pip install -r requirements.txt
```
- **Start Command**
```bash
python3 -m uvicorn aeroforge_app:app --host 0.0.0.0 --port $PORT
```

## API
- `POST /optimize` → Optimize based on uploaded file + options and returns `pdf_path`.
- `GET /download?path=<pdf_path>` → Download generated report.
- `GET /health` → Service health check.


## New endpoints
- `GET /leaderboard` → Returns top optimization runs.
- `GET /auth/microsoft` → OAuth integration stub metadata.
- `GET /auth/google` → OAuth integration stub metadata.
