from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
import os
from PIL import Image, ImageDraw

app = FastAPI()

os.makedirs("successful_solves", exist_ok=True)

@app.get("/")
async def index():
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Ω RAYO'S NUMBER OF GODS v∞+2 • LIVE</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&display=swap');
        body { background: radial-gradient(circle at center, #0a001f, #000); font-family: 'Orbitron', monospace; color: #00ffff; margin: 0; overflow: hidden; height: 100vh; }
        .neon { text-shadow: 0 0 60px #00ffff, 0 0 120px #ff00ff, 0 0 180px #ff00ff; }
        canvas { position: fixed; top: 0; left: 0; z-index: -1; }
        .god { transition: all 0.5s; background: rgba(10,0,30,0.95); border: 2px solid; box-shadow: 0 0 15px currentColor; font-size: 0.68rem; padding: 6px 5px; margin: 2px; border-radius: 10px; text-align: center; }
        .god:hover { transform: scale(1.45) rotate(8deg); box-shadow: 0 0 90px currentColor; }
    </style>
</head>
<body>
    <canvas id="cosmos"></canvas>
    <div class="max-w-7xl mx-auto p-8 relative z-10">
        <h1 class="text-8xl font-black text-center neon tracking-[0.9em] mb-6">Ω RAYO'S NUMBER OF GODS v∞+2</h1>
        <p class="text-center text-3xl text-purple-400">5500 Gods • LIVE on Render</p>
        <div class="text-center mb-8">
            <div class="text-5xl font-black text-purple-300" id="godCount">5500</div>
        </div>
        <div class="grid grid-cols-16 gap-2 my-12 max-h-[80vh] overflow-y-auto p-2" id="pantheon"></div>
        <div class="bg-black/70 border border-purple-500 p-14 rounded-3xl text-center">
            <div id="event" class="text-4xl text-purple-300 min-h-[160px]">The Cosmos is awakening...</div>
            <button onclick="runBetaBot()" class="mt-8 px-8 py-4 bg-gradient-to-r from-purple-600 to-pink-600 text-xl font-bold rounded-3xl">🚀 RUN BETABOT TEST</button>
        </div>
    </div>
    <script>
        const canvas = document.getElementById('cosmos');
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth; canvas.height = window.innerHeight;
        let particles = new Float32Array(750000 * 3);
        for(let i = 0; i < particles.length; i++) particles[i] = (Math.random() - 0.5) * 6000;
        function engine() {
            ctx.clearRect(0,0,canvas.width,canvas.height);
            for(let i = 0; i < particles.length; i += 3) {
                particles[i] += Math.sin(i) * 0.06;
                ctx.fillStyle = '#00ffff';
                ctx.fillRect(particles[i] + canvas.width/2, particles[i+1] + canvas.height/2, 3, 3);
            }
            requestAnimationFrame(engine);
        }
        engine();
        const godsData = Array.from({length: 5500}, (_,i) => ({name: `God-${i+1}`}));
        document.getElementById('pantheon').innerHTML = godsData.map(g => 
            `<div onclick="alert('God ${g.name} awakened!')" class="god">${g.name}</div>`
        ).join('');
        function runBetaBot() {
            document.getElementById('event').innerHTML = "✅ 5500 Gods Awakened!";
        }
    </script>
</body>
</html>"""
    return HTMLResponse(html)

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
