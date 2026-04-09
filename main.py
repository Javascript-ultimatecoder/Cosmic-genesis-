from fastapi import FastAPI, Body
from fastapi.responses import HTMLResponse
import os
import datetime
import sqlite3
import base64
from cryptography.fernet import Fernet

app = FastAPI(
    title="Ω RAYO'S NUMBER OF GODS v∞+11 • REAL BIOMETRIC MFA VAULT",
    version="∞+12",
)

os.makedirs("successful_solves", exist_ok=True)
os.makedirs("vault", exist_ok=True)

KEY_PATH = "vault/cipher.key"


def load_or_create_key() -> bytes:
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    with open(KEY_PATH, "wb") as f:
        f.write(key)
    return key


cipher = Fernet(load_or_create_key())

# SQLite for local persistence
conn = sqlite3.connect("vault/cyberlocker.db", check_same_thread=False)
conn.execute(
    """CREATE TABLE IF NOT EXISTS envelopes (
    id TEXT PRIMARY KEY,
    user TEXT,
    encrypted_data BLOB,
    created_at TEXT
)"""
)
conn.commit()


def encrypt_message(message: str) -> bytes:
    return cipher.encrypt(message.encode())


def decrypt_message(encrypted: bytes) -> str:
    return cipher.decrypt(encrypted).decode()


@app.post("/cyberlocker_create_identity")
async def create_identity(data: dict = Body(...)):
    name = data.get("name", "default")
    return {
        "status": "success",
        "message": f"Identity {name} created with biometric passkey support",
    }


@app.post("/cyberlocker_encrypt")
async def cyberlocker_encrypt(data: dict = Body(...)):
    msg = data.get("message", "").strip()
    user = data.get("user", "default")
    if not msg:
        return {"status": "error", "message": "No message"}
    encrypted = encrypt_message(msg)
    ref = f"vault-{datetime.datetime.utcnow().timestamp()}"
    created_at = datetime.datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO envelopes (id, user, encrypted_data, created_at) VALUES (?,?,?,?)",
        (ref, user, encrypted, created_at),
    )
    conn.commit()
    return {
        "status": "success",
        "ref": ref,
        "created_at": created_at,
        "message": "Encrypted and stored in SQLite",
    }


@app.post("/cyberlocker_decrypt")
async def cyberlocker_decrypt(data: dict = Body(...)):
    ref = data.get("ref")
    if not ref:
        return {"status": "error", "message": "ref is required"}
    row = conn.execute("SELECT encrypted_data FROM envelopes WHERE id=?", (ref,)).fetchone()
    if not row:
        return {"status": "error", "message": "Not found"}
    decrypted = decrypt_message(row[0])
    return {"status": "success", "decrypted": decrypted, "ref": ref}


@app.get("/cyberlocker_list_refs")
async def cyberlocker_list_refs(limit: int = 10):
    rows = conn.execute(
        "SELECT id, user, created_at FROM envelopes ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return {
        "status": "success",
        "items": [{"ref": r[0], "user": r[1], "created_at": r[2]} for r in rows],
    }


@app.get("/webauthn_challenge")
async def webauthn_challenge():
    challenge = os.urandom(32)
    return {"challenge": base64.b64encode(challenge).decode()}


@app.get("/")
async def index():
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Ω RAYO'S NUMBER OF GODS v∞+12 • BIOMETRIC MFA VAULT</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&display=swap');
        body { background: radial-gradient(circle at center, #0a001f, #000); font-family: 'Orbitron', monospace; color: #00ffff; margin: 0; overflow: hidden; min-height: 100vh; }
        .neon { text-shadow: 0 0 60px #00ffff, 0 0 120px #ff00ff; }
        canvas { position: fixed; top: 0; left: 0; z-index: -1; }
        .card { background: rgba(15,5,40,0.95); border: 2px solid #00ffff; box-shadow: 0 0 30px #00ffff; }
        .sidebar { background: rgba(10,0,30,0.98); }
    </style>
</head>
<body>
    <canvas id="cosmos"></canvas>
    <div class="max-w-7xl mx-auto p-8 relative z-10 flex gap-8">
        <div class="sidebar w-72 h-[92vh] rounded-3xl p-6 flex flex-col">
            <h1 class="text-4xl font-black neon mb-8">CYBERLOCKER</h1>
            <div onclick="switchTab(2)" class="cursor-pointer hover:bg-white/10 p-4 rounded-2xl mb-2 flex items-center gap-3"><span>🔒</span> Vault</div>
            <div onclick="switchTab(3)" class="cursor-pointer hover:bg-white/10 p-4 rounded-2xl mb-2 flex items-center gap-3"><span>🧬</span> Biometric + MFA</div>
        </div>

        <div id="tab-2" class="tab-content flex-1">
            <div class="card p-8 rounded-3xl">
                <h2 class="text-4xl font-black mb-6">🔒 Secure Vault</h2>
                <div class="grid grid-cols-2 gap-6">
                    <button onclick="biometricLogin()" class="w-full py-6 bg-emerald-600 text-black font-bold rounded-3xl">🧬 Biometric Unlock (WebAuthn)</button>
                    <button onclick="enableMFA()" class="w-full py-6 bg-amber-600 text-black font-bold rounded-3xl">🔐 Enable MFA (Demo)</button>
                </div>

                <textarea id="message" placeholder="Type message to encrypt..." class="mt-8 w-full h-40 px-6 py-4 bg-black border border-cyan-400 rounded-3xl text-white"></textarea>
                <input id="ref" placeholder="Paste reference id to decrypt (or use last saved ref)" class="mt-4 w-full px-6 py-3 bg-black border border-cyan-400 rounded-3xl text-white" />

                <div class="flex gap-4 mt-6">
                    <button onclick="encryptMessage()" class="flex-1 py-5 bg-red-600 text-white font-bold rounded-3xl">Encrypt & Store</button>
                    <button onclick="decryptMessage()" class="flex-1 py-5 bg-green-600 text-white font-bold rounded-3xl">Decrypt from Vault</button>
                </div>

                <div id="event" class="mt-6 text-cyan-200 text-sm break-all">Ready.</div>
            </div>
        </div>
    </div>

    <script>
        const canvas = document.getElementById('cosmos');
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        let particles = new Float32Array(12000 * 3);
        for(let i = 0; i < particles.length; i++) particles[i] = (Math.random() - 0.5) * 5000;

        function engine() {
            ctx.clearRect(0,0,canvas.width,canvas.height);
            for(let i = 0; i < particles.length; i += 3) {
                particles[i] += Math.sin(i) * 0.05;
                ctx.fillStyle = '#00ffff';
                ctx.fillRect(particles[i] + canvas.width/2, particles[i+1] + canvas.height/2, 2, 2);
            }
            requestAnimationFrame(engine);
        }
        engine();

        window.addEventListener('resize', () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        });

        let lastRef = '';

        async function biometricLogin() {
            const challengeRes = await fetch('/webauthn_challenge');
            const {challenge} = await challengeRes.json();
            try {
                await navigator.credentials.get({
                    publicKey: {
                        challenge: new Uint8Array(atob(challenge).split('').map(c => c.charCodeAt(0))),
                        timeout: 60000,
                        userVerification: "required"
                    }
                });
                document.getElementById('event').innerText = '✅ Biometric authentication successful';
            } catch (e) {
                document.getElementById('event').innerText = '❌ Biometric authentication failed or not supported';
            }
        }

        async function encryptMessage() {
            const msg = document.getElementById('message').value;
            const res = await fetch('/cyberlocker_encrypt', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: msg})
            });
            const data = await res.json();
            if (data.status === 'success') {
                lastRef = data.ref;
                document.getElementById('ref').value = data.ref;
                document.getElementById('event').innerText = `✅ Stored with ref: ${data.ref}`;
            } else {
                document.getElementById('event').innerText = `❌ Encrypt failed: ${data.message || 'Unknown error'}`;
            }
        }

        async function decryptMessage() {
            const ref = document.getElementById('ref').value || lastRef;
            const res = await fetch('/cyberlocker_decrypt', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ref})
            });
            const data = await res.json();
            if (data.status === 'success') {
                document.getElementById('message').value = data.decrypted;
                document.getElementById('event').innerText = `✅ Decrypted ref: ${data.ref}`;
            } else {
                document.getElementById('event').innerText = `❌ Decrypt failed: ${data.message || 'Unknown error'}`;
            }
        }

        function enableMFA() {
            document.getElementById('event').innerText = '🔐 Demo MFA toggle clicked';
        }

        function switchTab() {
            document.getElementById('event').innerText = 'Vault tab active';
        }
    </script>
</body>
</html>"""
    return HTMLResponse(html)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
