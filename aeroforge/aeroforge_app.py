from __future__ import annotations

import importlib.util
import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if importlib.util.find_spec("fastapi"):
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.responses import FileResponse, HTMLResponse
else:
    from lightweight_fastapi import FastAPI, UploadFile, File, Form
    from lightweight_fastapi_responses import HTMLResponse, FileResponse

if importlib.util.find_spec("reportlab"):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
else:
    from lightweight_reportlab import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        getSampleStyleSheet,
    )

app = FastAPI(title="AeroForge+", version="2.2")
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}
SUPPORTED_MODES = {"Distance", "Airtime", "Height", "Hybrid"}

LEADERBOARD: list[dict[str, Any]] = []


def build_ability_stats(design: dict[str, float], score: float) -> dict[str, float]:
    return {
        "lift": round(min(100.0, design["span"] / 3.2), 2),
        "speed": round(min(100.0, design["velocity"] * 5.5), 2),
        "stability": round(max(0.0, 100.0 - abs(design["balance"] - 0.33) * 320), 2),
        "efficiency": round(min(100.0, (design["span"] / max(design["mass"], 0.1)) * 2.4), 2),
        "ai_confidence": round(min(100.0, score * 2.2), 2),
    }


@app.get("/")
def home():
    with open(BASE_DIR / "index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())


def simulate(design: dict[str, float]) -> float:
    span_m = design["span"] / 1000
    chord_m = design["chord"] / 1000
    wing_area = span_m * chord_m
    mass = design["mass"] / 1000
    velocity = design["velocity"]
    rho = 1.225

    cl = max(0.05, 0.4 + 0.08 * design["angle"])
    cd = 0.02 + (cl**2) / (3.14 * 4.2 * 0.82)

    lift = 0.5 * rho * velocity**2 * wing_area * cl
    drag = 0.5 * rho * velocity**2 * wing_area * cd
    weight = mass * 9.81

    balance_penalty = max(0.05, 1 - abs(design["balance"] - 0.33) * 2.2)
    glide_ratio = max(0.05, lift / max(drag, 1e-4))
    return (lift / max(weight, 1e-4)) * glide_ratio * balance_penalty


def optimize(mode: str, extreme_mode: bool) -> tuple[dict[str, float], float]:
    best = {
        "span": 210.0,
        "chord": 65.0,
        "angle": 5.0,
        "balance": 0.33,
        "mass": 8.0,
        "velocity": 8.5,
    }
    best_score = simulate(best)

    loops = 600 if extreme_mode else 220
    for _ in range(loops):
        new = {
            "span": min(320.0, max(120.0, best["span"] + random.randint(-14, 14))),
            "chord": min(120.0, max(35.0, best["chord"] + random.randint(-8, 8))),
            "angle": min(15.0, max(-2.0, best["angle"] + random.uniform(-1.2, 1.2))),
            "balance": min(0.48, max(0.2, best["balance"] + random.uniform(-0.045, 0.045))),
            "mass": min(20.0, max(4.0, best["mass"] + random.uniform(-0.8, 0.8))),
            "velocity": min(18.0, max(4.0, best["velocity"] + random.uniform(-0.6, 0.6))),
        }

        score = simulate(new)
        if mode == "Airtime":
            score *= new["span"] / new["mass"]
        elif mode == "Distance":
            score *= new["velocity"] * 0.8
        elif mode == "Height":
            score *= new["angle"] + 3

        if score > best_score:
            best = new
            best_score = score

    return best, best_score


def create_pdf(text: str) -> str:
    unique_name = f"report_{uuid.uuid4().hex}.pdf"
    path = OUTPUT_DIR / unique_name
    doc = SimpleDocTemplate(str(path))
    styles = getSampleStyleSheet()
    story = [Paragraph("AeroForge+ Optimization Report", styles["Heading2"]), Spacer(1, 8)]
    for line in text.splitlines():
        if line.strip():
            story.append(Paragraph(line, styles["BodyText"]))
    doc.build(story)
    return unique_name


@app.post("/optimize")
async def optimize_plane(
    file: UploadFile = File(...),
    mode: str = Form("Hybrid"),
    extreme_mode: bool = Form(False),
):
    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        return {"error": "Only image/PDF uploads are supported."}

    if mode not in SUPPORTED_MODES:
        return {"error": f"Unsupported mode '{mode}'."}

    contents = await file.read()
    file_size_kb = round(len(contents) / 1024, 2)

    best, score = optimize(mode, extreme_mode)

    result_text = f"""
Timestamp: {datetime.now(timezone.utc).isoformat()}
Mode: {mode}
Extreme mode: {extreme_mode}
Input file: {file.filename}
Input size: {file_size_kb} KB
Span: {best['span']:.2f} mm
Chord: {best['chord']:.2f} mm
Angle: {best['angle']:.2f} deg
Balance: {best['balance']:.3f}
Mass: {best['mass']:.2f} g
Launch velocity: {best['velocity']:.2f} m/s
Composite Score: {score:.4f}
"""

    pdf_name = create_pdf(result_text)
    abilities = build_ability_stats(best, score)

    LEADERBOARD.append({"mode": mode, "score": round(score, 4), "file": file.filename or "unknown"})
    LEADERBOARD.sort(key=lambda x: x["score"], reverse=True)
    del LEADERBOARD[10:]

    return {
        "design": best,
        "score": round(score, 4),
        "mode": mode,
        "extreme_mode": extreme_mode,
        "file_name": file.filename,
        "file_size_kb": file_size_kb,
        "pdf_path": pdf_name,
        "abilities": abilities,
        "leaderboard_rank": next((i + 1 for i, row in enumerate(LEADERBOARD) if row["score"] == round(score, 4) and row["file"] == (file.filename or "unknown")), None),
    }


@app.get("/download")
def download(path: str):
    safe_name = Path(path).name
    requested = OUTPUT_DIR / safe_name
    if not requested.exists():
        if importlib.util.find_spec("fastapi"):
            raise HTTPException(status_code=404, detail="Report not found")
        return {"error": "Report not found"}
    return FileResponse(str(requested), filename="plane_report.pdf")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "app": app.title, "version": app.version, "python": "3"}


@app.get("/leaderboard")
def leaderboard() -> dict[str, Any]:
    return {"top_runs": LEADERBOARD}


@app.get("/auth/microsoft")
def auth_microsoft() -> dict[str, str]:
    return {"provider": "microsoft", "status": "stub", "message": "Configure OAuth client to enable Microsoft login."}


@app.get("/auth/google")
def auth_google() -> dict[str, str]:
    return {"provider": "google", "status": "stub", "message": "Configure OAuth client to enable Google login."}
