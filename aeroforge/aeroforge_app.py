from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
import os
import random
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = FastAPI(title="AeroForge+", version="2.0")
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


@app.get("/")
def home():
    with open(BASE_DIR / "index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())


def simulate(design):
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
    score = (lift / max(weight, 1e-4)) * glide_ratio * balance_penalty
    return score


def optimize(mode: str, extreme_mode: bool):
    best = {
        "span": 210,
        "chord": 65,
        "angle": 5.0,
        "balance": 0.33,
        "mass": 8.0,
        "velocity": 8.5,
    }
    best_score = simulate(best)

    loops = 400 if extreme_mode else 180
    for _ in range(loops):
        new = {
            "span": min(320, max(120, best["span"] + random.randint(-14, 14))),
            "chord": min(120, max(35, best["chord"] + random.randint(-8, 8))),
            "angle": min(15.0, max(-2.0, best["angle"] + random.uniform(-1.2, 1.2))),
            "balance": min(0.48, max(0.2, best["balance"] + random.uniform(-0.045, 0.045))),
            "mass": min(20.0, max(4.0, best["mass"] + random.uniform(-0.8, 0.8))),
            "velocity": min(18.0, max(4.0, best["velocity"] + random.uniform(-0.6, 0.6))),
        }

        score = simulate(new)
        if mode == "Airtime":
            score *= (new["span"] / new["mass"])
        elif mode == "Distance":
            score *= (new["velocity"] * 0.8)
        elif mode == "Height":
            score *= (new["angle"] + 3)

        if score > best_score:
            best = new
            best_score = score

    return best, best_score


def create_pdf(text: str):
    path = OUTPUT_DIR / "output.pdf"
    doc = SimpleDocTemplate(str(path))
    styles = getSampleStyleSheet()
    story = [Paragraph("AeroForge+ Optimization Report", styles["Heading2"]), Spacer(1, 8)]
    for line in text.splitlines():
        if line.strip():
            story.append(Paragraph(line, styles["BodyText"]))
    doc.build(story)
    return str(path)


@app.post("/optimize")
async def optimize_plane(
    file: UploadFile = File(...),
    mode: str = Form("Hybrid"),
    extreme_mode: bool = Form(False),
):
    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp", ".pdf"}:
        return {"error": "Only image/PDF uploads are supported."}

    contents = await file.read()
    file_size_kb = round(len(contents) / 1024, 2)

    best, score = optimize(mode, extreme_mode)

    result_text = f"""
Mode: {mode}
Extreme mode: {extreme_mode}
Input file: {file.filename}
Input size: {file_size_kb} KB
Span: {best['span']} mm
Chord: {best['chord']} mm
Angle: {best['angle']:.2f} deg
Balance: {best['balance']:.3f}
Mass: {best['mass']:.2f} g
Launch velocity: {best['velocity']:.2f} m/s
Composite Score: {score:.4f}
"""

    pdf_path = create_pdf(result_text)

    return {
        "design": best,
        "score": round(score, 4),
        "mode": mode,
        "extreme_mode": extreme_mode,
        "file_name": file.filename,
        "file_size_kb": file_size_kb,
        "pdf_path": pdf_path,
    }


@app.get("/download")
def download(path: str):
    return FileResponse(path, filename="plane_report.pdf")
