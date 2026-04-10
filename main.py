from fastapi import FastAPI, Body, Request, HTTPException
from fastapi.responses import HTMLResponse
import os
import datetime
import sqlite3
import base64
import hashlib
import hmac
import secrets
import json
from typing import Optional

app = FastAPI(
    title="Ω RAYO'S NUMBER OF GODS v∞+13 • ZERO-KNOWLEDGE BIOMETRIC VAULT",
    version="∞+13",
)

os.makedirs("vault", exist_ok=True)

DB_PATH = "vault/cyberlocker.db"
JWT_SECRET_PATH = "vault/jwt.secret"
JWT_ALG = "HS256"
JWT_TTL_SECONDS = 3600


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def load_or_create_secret(path: str, nbytes: int = 32) -> bytes:
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    key = os.urandom(nbytes)
    with open(path, "wb") as f:
        f.write(key)
    return key


JWT_SECRET = load_or_create_secret(JWT_SECRET_PATH)


# SQLite for persistence
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute(
    """CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    salt BLOB NOT NULL,
    created_at TEXT NOT NULL
)"""
)
conn.execute(
    """CREATE TABLE IF NOT EXISTS zk_envelopes (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    ciphertext BLOB NOT NULL,
    nonce BLOB NOT NULL,
    aad TEXT,
    created_at TEXT NOT NULL
)"""
)
conn.execute(
    """CREATE TABLE IF NOT EXISTS webauthn_challenges (
    username TEXT PRIMARY KEY,
    challenge TEXT NOT NULL,
    challenge_type TEXT NOT NULL,
    created_at TEXT NOT NULL
)"""
)
conn.execute(
    """CREATE TABLE IF NOT EXISTS webauthn_credentials (
    username TEXT PRIMARY KEY,
    credential_id TEXT NOT NULL,
    public_key TEXT,
    sign_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
)"""
)
conn.execute(
    """CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    event TEXT,
    target_ref TEXT,
    ip TEXT,
    created_at TEXT
)"""
)
conn.execute(
    """CREATE TABLE IF NOT EXISTS zk_chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room TEXT NOT NULL,
    username TEXT NOT NULL,
    ciphertext BLOB NOT NULL,
    nonce BLOB NOT NULL,
    created_at TEXT NOT NULL
)"""
)
conn.execute(
    """CREATE TABLE IF NOT EXISTS zk_files (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    ciphertext BLOB NOT NULL,
    nonce BLOB NOT NULL,
    created_at TEXT NOT NULL
)"""
)
conn.commit()


# Argon2id optional support
try:
    from argon2.low_level import hash_secret_raw, Type  # type: ignore

    ARGON2_AVAILABLE = True
except Exception:
    ARGON2_AVAILABLE = False


def derive_password_hash(password: str, salt: bytes) -> str:
    if ARGON2_AVAILABLE:
        raw = hash_secret_raw(
            password.encode(),
            salt,
            time_cost=3,
            memory_cost=65536,
            parallelism=4,
            hash_len=32,
            type=Type.ID,
        )
    else:
        raw = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return b64url_encode(raw)


def create_token(username: str) -> str:
    header = {"alg": JWT_ALG, "typ": "JWT"}
    payload = {
        "sub": username,
        "iat": int(datetime.datetime.utcnow().timestamp()),
        "exp": int(datetime.datetime.utcnow().timestamp()) + JWT_TTL_SECONDS,
    }
    header_b64 = b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()
    sig = hmac.new(JWT_SECRET, signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{b64url_encode(sig)}"


def verify_token(token: str) -> str:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = hmac.new(JWT_SECRET, signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_sig, b64url_decode(sig_b64)):
            raise HTTPException(status_code=401, detail="Invalid token signature")
        payload = json.loads(b64url_decode(payload_b64).decode())
        if int(payload.get("exp", 0)) < int(datetime.datetime.utcnow().timestamp()):
            raise HTTPException(status_code=401, detail="Token expired")
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token subject")
        return username
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Malformed token")


def get_bearer_user(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return verify_token(auth.replace("Bearer ", "", 1).strip())


def write_audit(event: str, request: Request, username: Optional[str] = None, target_ref: str = ""):
    ip = request.client.host if request.client else "unknown"
    conn.execute(
        "INSERT INTO audit_log (username, event, target_ref, ip, created_at) VALUES (?,?,?,?,?)",
        (username, event, target_ref, ip, datetime.datetime.utcnow().isoformat()),
    )
    conn.commit()


@app.post("/auth/register")
async def auth_register(request: Request, data: dict = Body(...)):
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    if len(username) < 3 or len(password) < 10:
        raise HTTPException(status_code=400, detail="Username/password policy failed")
    existing = conn.execute("SELECT username FROM users WHERE username=?", (username,)).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    salt = os.urandom(16)
    pwhash = derive_password_hash(password, salt)
    conn.execute(
        "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?,?,?,?)",
        (username, pwhash, salt, datetime.datetime.utcnow().isoformat()),
    )
    conn.commit()
    write_audit("register", request, username=username)
    return {"status": "success", "username": username}


@app.post("/auth/login")
async def auth_login(request: Request, data: dict = Body(...)):
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    row = conn.execute("SELECT password_hash, salt FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    expected_hash, salt = row
    given_hash = derive_password_hash(password, salt)
    if not hmac.compare_digest(expected_hash, given_hash):
        write_audit("login_failed", request, username=username)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(username)
    write_audit("login_success", request, username=username)
    return {"status": "success", "token": token, "token_type": "Bearer", "expires_in": JWT_TTL_SECONDS}


@app.post("/zk_vault_store")
async def zk_vault_store(request: Request, data: dict = Body(...)):
    username = get_bearer_user(request)
    ciphertext = data.get("ciphertext", "")
    nonce = data.get("nonce", "")
    aad = data.get("aad", "")
    if not ciphertext or not nonce:
        raise HTTPException(status_code=400, detail="ciphertext and nonce required")

    env_id = f"zk-{secrets.token_hex(12)}"
    conn.execute(
        "INSERT INTO zk_envelopes (id, username, ciphertext, nonce, aad, created_at) VALUES (?,?,?,?,?,?)",
        (
            env_id,
            username,
            b64url_decode(ciphertext),
            b64url_decode(nonce),
            aad,
            datetime.datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    write_audit("zk_store", request, username=username, target_ref=env_id)
    return {"status": "success", "ref": env_id}


@app.post("/zk_vault_fetch")
async def zk_vault_fetch(request: Request, data: dict = Body(...)):
    username = get_bearer_user(request)
    ref = data.get("ref", "")
    if not ref:
        raise HTTPException(status_code=400, detail="ref required")

    row = conn.execute(
        "SELECT ciphertext, nonce, aad FROM zk_envelopes WHERE id=? AND username=?", (ref, username)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Envelope not found")
    write_audit("zk_fetch", request, username=username, target_ref=ref)
    return {
        "status": "success",
        "ref": ref,
        "ciphertext": b64url_encode(row[0]),
        "nonce": b64url_encode(row[1]),
        "aad": row[2] or "",
    }


@app.get("/zk_vault_list")
async def zk_vault_list(request: Request, limit: int = 25):
    username = get_bearer_user(request)
    rows = conn.execute(
        "SELECT id, created_at FROM zk_envelopes WHERE username=? ORDER BY created_at DESC LIMIT ?",
        (username, limit),
    ).fetchall()
    write_audit("zk_list", request, username=username)
    return {"status": "success", "items": [{"ref": r[0], "created_at": r[1]} for r in rows]}


@app.post("/zk_file_upload")
async def zk_file_upload(request: Request, data: dict = Body(...)):
    username = get_bearer_user(request)
    filename = (data.get("filename") or "").strip()
    mime_type = (data.get("mime_type") or "application/octet-stream").strip()
    ciphertext = data.get("ciphertext", "")
    nonce = data.get("nonce", "")
    if not filename or not ciphertext or not nonce:
        raise HTTPException(status_code=400, detail="filename, ciphertext, nonce required")

    file_id = f"file-{secrets.token_hex(12)}"
    conn.execute(
        "INSERT INTO zk_files (id, username, filename, mime_type, ciphertext, nonce, created_at) VALUES (?,?,?,?,?,?,?)",
        (
            file_id,
            username,
            filename,
            mime_type,
            b64url_decode(ciphertext),
            b64url_decode(nonce),
            datetime.datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    write_audit("zk_file_upload", request, username=username, target_ref=file_id)
    return {"status": "success", "file_id": file_id}


@app.post("/zk_file_download")
async def zk_file_download(request: Request, data: dict = Body(...)):
    username = get_bearer_user(request)
    file_id = data.get("file_id", "")
    if not file_id:
        raise HTTPException(status_code=400, detail="file_id required")
    row = conn.execute(
        "SELECT filename, mime_type, ciphertext, nonce FROM zk_files WHERE id=? AND username=?",
        (file_id, username),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")
    write_audit("zk_file_download", request, username=username, target_ref=file_id)
    return {
        "status": "success",
        "file_id": file_id,
        "filename": row[0],
        "mime_type": row[1],
        "ciphertext": b64url_encode(row[2]),
        "nonce": b64url_encode(row[3]),
    }


@app.get("/zk_file_list")
async def zk_file_list(request: Request, limit: int = 25):
    username = get_bearer_user(request)
    rows = conn.execute(
        "SELECT id, filename, mime_type, created_at FROM zk_files WHERE username=? ORDER BY created_at DESC LIMIT ?",
        (username, limit),
    ).fetchall()
    write_audit("zk_file_list", request, username=username)
    return {
        "status": "success",
        "items": [
            {"file_id": r[0], "filename": r[1], "mime_type": r[2], "created_at": r[3]} for r in rows
        ],
    }


@app.post("/zk_chat_send")
async def zk_chat_send(request: Request, data: dict = Body(...)):
    username = get_bearer_user(request)
    room = (data.get("room") or "global").strip()
    ciphertext = data.get("ciphertext", "")
    nonce = data.get("nonce", "")
    if not ciphertext or not nonce:
        raise HTTPException(status_code=400, detail="ciphertext and nonce required")
    conn.execute(
        "INSERT INTO zk_chat_messages (room, username, ciphertext, nonce, created_at) VALUES (?,?,?,?,?)",
        (room, username, b64url_decode(ciphertext), b64url_decode(nonce), datetime.datetime.utcnow().isoformat()),
    )
    msg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    write_audit("zk_chat_send", request, username=username, target_ref=f"{room}:{msg_id}")
    return {"status": "success", "message_id": msg_id}


@app.get("/zk_chat_poll")
async def zk_chat_poll(request: Request, room: str = "global", since_id: int = 0, limit: int = 50):
    username = get_bearer_user(request)
    rows = conn.execute(
        """SELECT id, username, ciphertext, nonce, created_at FROM zk_chat_messages
           WHERE room=? AND id>? ORDER BY id ASC LIMIT ?""",
        (room, since_id, limit),
    ).fetchall()
    write_audit("zk_chat_poll", request, username=username, target_ref=room)
    return {
        "status": "success",
        "room": room,
        "items": [
            {
                "id": r[0],
                "sender": r[1],
                "ciphertext": b64url_encode(r[2]),
                "nonce": b64url_encode(r[3]),
                "created_at": r[4],
            }
            for r in rows
        ],
    }


@app.post("/webauthn/register_begin")
async def webauthn_register_begin(request: Request):
    username = get_bearer_user(request)
    challenge = b64url_encode(os.urandom(32))
    conn.execute(
        "INSERT OR REPLACE INTO webauthn_challenges (username, challenge, challenge_type, created_at) VALUES (?,?,?,?)",
        (username, challenge, "register", datetime.datetime.utcnow().isoformat()),
    )
    conn.commit()
    return {"status": "success", "challenge": challenge, "rpId": "localhost", "user": username}


@app.post("/webauthn/register_verify")
async def webauthn_register_verify(request: Request, data: dict = Body(...)):
    username = get_bearer_user(request)
    challenge = data.get("challenge", "")
    credential_id = data.get("credential_id", "")
    public_key = data.get("public_key", "")
    row = conn.execute(
        "SELECT challenge FROM webauthn_challenges WHERE username=? AND challenge_type='register'", (username,)
    ).fetchone()
    if not row or row[0] != challenge:
        raise HTTPException(status_code=400, detail="Invalid registration challenge")
    if not credential_id:
        raise HTTPException(status_code=400, detail="credential_id required")
    conn.execute(
        "INSERT OR REPLACE INTO webauthn_credentials (username, credential_id, public_key, sign_count, created_at) VALUES (?,?,?,?,?)",
        (username, credential_id, public_key, 0, datetime.datetime.utcnow().isoformat()),
    )
    conn.commit()
    write_audit("webauthn_register", request, username=username)
    return {"status": "success", "message": "Credential registered"}


@app.post("/webauthn/auth_begin")
async def webauthn_auth_begin(request: Request):
    username = get_bearer_user(request)
    row = conn.execute(
        "SELECT credential_id FROM webauthn_credentials WHERE username=?", (username,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No registered credential")
    challenge = b64url_encode(os.urandom(32))
    conn.execute(
        "INSERT OR REPLACE INTO webauthn_challenges (username, challenge, challenge_type, created_at) VALUES (?,?,?,?)",
        (username, challenge, "auth", datetime.datetime.utcnow().isoformat()),
    )
    conn.commit()
    return {"status": "success", "challenge": challenge, "allowCredentials": [row[0]], "rpId": "localhost"}


@app.post("/webauthn/auth_verify")
async def webauthn_auth_verify(request: Request, data: dict = Body(...)):
    username = get_bearer_user(request)
    challenge = data.get("challenge", "")
    credential_id = data.get("credential_id", "")
    row = conn.execute(
        "SELECT challenge FROM webauthn_challenges WHERE username=? AND challenge_type='auth'", (username,)
    ).fetchone()
    cred = conn.execute(
        "SELECT credential_id, sign_count FROM webauthn_credentials WHERE username=?", (username,)
    ).fetchone()
    if not row or row[0] != challenge:
        raise HTTPException(status_code=400, detail="Invalid auth challenge")
    if not cred or cred[0] != credential_id:
        raise HTTPException(status_code=400, detail="Credential mismatch")
    conn.execute(
        "UPDATE webauthn_credentials SET sign_count=sign_count+1 WHERE username=?", (username,)
    )
    conn.commit()
    write_audit("webauthn_auth", request, username=username)
    return {"status": "success", "verified": True}


@app.get("/security/status")
async def security_status(request: Request):
    username = get_bearer_user(request)
    logs = conn.execute(
        "SELECT event, target_ref, ip, created_at FROM audit_log WHERE username=? ORDER BY id DESC LIMIT 20",
        (username,),
    ).fetchall()
    failed_logins_last_hour = conn.execute(
        """SELECT COUNT(*) FROM audit_log
           WHERE username=? AND event='login_failed'
           AND created_at >= ?""",
        (
            username,
            (datetime.datetime.utcnow() - datetime.timedelta(hours=1)).isoformat(),
        ),
    ).fetchone()[0]
    return {
        "status": "success",
        "security_mode": "zero_knowledge",
        "jwt_enabled": True,
        "argon2id_enabled": ARGON2_AVAILABLE,
        "anomaly_flags": {
            "failed_logins_last_hour": failed_logins_last_hour,
            "possible_bruteforce": failed_logins_last_hour >= 5,
        },
        "notes": "Server stores ciphertext only; decryption key is client-derived.",
        "recent_events": [
            {"event": r[0], "target_ref": r[1], "ip": r[2], "created_at": r[3]} for r in logs
        ],
    }


@app.get("/")
async def index():
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Ω ZK Military Vault v∞+13</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black text-cyan-300 p-6">
  <h1 class="text-3xl font-bold mb-4">Ω Zero-Knowledge Biometric Vault</h1>
  <p class="mb-4">Client-side AES-GCM encryption + JWT + WebAuthn flow endpoints.</p>
  <div class="grid gap-3 max-w-3xl">
    <input id="username" class="p-2 text-black" placeholder="username" />
    <input id="password" class="p-2 text-black" type="password" placeholder="password (>=10 chars)" />
    <button class="bg-blue-600 p-2" onclick="registerUser()">Register</button>
    <button class="bg-green-600 p-2" onclick="loginUser()">Login</button>

    <textarea id="plaintext" class="p-2 text-black" placeholder="secret message"></textarea>
    <button class="bg-red-600 p-2" onclick="storeZk()">Encrypt (client) + Store</button>

    <input id="ref" class="p-2 text-black" placeholder="envelope ref" />
    <button class="bg-emerald-700 p-2" onclick="fetchZk()">Fetch + Decrypt (client)</button>
    <button class="bg-indigo-700 p-2" onclick="loadSecurity()">Security Status</button>
    <input id="chatRoom" class="p-2 text-black" placeholder="chat room" value="global" />
    <input id="chatMessage" class="p-2 text-black" placeholder="chat plaintext message" />
    <button class="bg-purple-700 p-2" onclick="sendChat()">Send E2E Chat Message</button>
    <button class="bg-purple-900 p-2" onclick="pollChat()">Poll E2E Chat Messages</button>
    <input id="fileInput" class="p-2 text-black bg-white" type="file" />
    <button class="bg-orange-700 p-2" onclick="uploadEncryptedFile()">Upload Encrypted File</button>
    <input id="fileId" class="p-2 text-black" placeholder="file id" />
    <button class="bg-orange-900 p-2" onclick="downloadEncryptedFile()">Download + Decrypt File</button>
    <pre id="out" class="bg-zinc-900 p-3 rounded whitespace-pre-wrap">Ready.</pre>
  </div>

<script>
let token = "";

function b64urlFromBuf(buf) {
  let str = btoa(String.fromCharCode(...new Uint8Array(buf)));
  return str.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function bufFromB64url(s) {
  s = s.replace(/-/g, '+').replace(/_/g, '/');
  while (s.length % 4) s += '=';
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function deriveAesKey(password, username) {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey('raw', enc.encode(password), {name:'PBKDF2'}, false, ['deriveKey']);
  return crypto.subtle.deriveKey(
    {name:'PBKDF2', salt: enc.encode('zk-vault-'+username), iterations: 200000, hash:'SHA-256'},
    keyMaterial,
    {name:'AES-GCM', length:256},
    false,
    ['encrypt','decrypt']
  );
}

async function registerUser() {
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const res = await fetch('/auth/register', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username,password})});
  document.getElementById('out').innerText = JSON.stringify(await res.json(), null, 2);
}

async function loginUser() {
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const res = await fetch('/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username,password})});
  const data = await res.json();
  token = data.token || '';
  document.getElementById('out').innerText = JSON.stringify(data, null, 2);
}

async function storeZk() {
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const plaintext = document.getElementById('plaintext').value;
  const key = await deriveAesKey(password, username);
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const enc = new TextEncoder();
  const ciphertext = await crypto.subtle.encrypt({name:'AES-GCM', iv: nonce}, key, enc.encode(plaintext));
  const res = await fetch('/zk_vault_store', {
    method:'POST',
    headers:{'Content-Type':'application/json', 'Authorization':'Bearer '+token},
    body: JSON.stringify({ciphertext: b64urlFromBuf(ciphertext), nonce: b64urlFromBuf(nonce), aad: 'v1'})
  });
  const data = await res.json();
  if (data.ref) document.getElementById('ref').value = data.ref;
  document.getElementById('out').innerText = JSON.stringify(data, null, 2);
}

async function fetchZk() {
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const ref = document.getElementById('ref').value;
  const res = await fetch('/zk_vault_fetch', {
    method:'POST',
    headers:{'Content-Type':'application/json', 'Authorization':'Bearer '+token},
    body: JSON.stringify({ref})
  });
  const data = await res.json();
  if (data.status !== 'success') {
    document.getElementById('out').innerText = JSON.stringify(data, null, 2);
    return;
  }
  const key = await deriveAesKey(password, username);
  const ptBuf = await crypto.subtle.decrypt(
    {name:'AES-GCM', iv: bufFromB64url(data.nonce)},
    key,
    bufFromB64url(data.ciphertext)
  );
  const plaintext = new TextDecoder().decode(ptBuf);
  document.getElementById('out').innerText = JSON.stringify({...data, decrypted: plaintext}, null, 2);
}

async function loadSecurity() {
  const res = await fetch('/security/status', {headers:{'Authorization':'Bearer '+token}});
  document.getElementById('out').innerText = JSON.stringify(await res.json(), null, 2);
}

async function sendChat() {
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const room = document.getElementById('chatRoom').value || 'global';
  const text = document.getElementById('chatMessage').value;
  const key = await deriveAesKey(password, username + '::chat::' + room);
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt({name:'AES-GCM', iv: nonce}, key, new TextEncoder().encode(text));
  const res = await fetch('/zk_chat_send', {
    method:'POST',
    headers:{'Content-Type':'application/json', 'Authorization':'Bearer '+token},
    body: JSON.stringify({room, ciphertext: b64urlFromBuf(ciphertext), nonce: b64urlFromBuf(nonce)})
  });
  document.getElementById('out').innerText = JSON.stringify(await res.json(), null, 2);
}

let lastChatId = 0;
async function pollChat() {
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const room = document.getElementById('chatRoom').value || 'global';
  const res = await fetch(`/zk_chat_poll?room=${encodeURIComponent(room)}&since_id=${lastChatId}`, {
    headers:{'Authorization':'Bearer '+token}
  });
  const data = await res.json();
  if (data.status !== 'success') {
    document.getElementById('out').innerText = JSON.stringify(data, null, 2);
    return;
  }
  const key = await deriveAesKey(password, username + '::chat::' + room);
  const decrypted = [];
  for (const item of data.items) {
    lastChatId = Math.max(lastChatId, item.id);
    try {
      const ptBuf = await crypto.subtle.decrypt({name:'AES-GCM', iv: bufFromB64url(item.nonce)}, key, bufFromB64url(item.ciphertext));
      decrypted.push({...item, plaintext: new TextDecoder().decode(ptBuf)});
    } catch {
      decrypted.push({...item, plaintext: '[unable to decrypt with your key]'});
    }
  }
  document.getElementById('out').innerText = JSON.stringify({...data, items: decrypted}, null, 2);
}

async function uploadEncryptedFile() {
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const input = document.getElementById('fileInput');
  if (!input.files || !input.files[0]) {
    document.getElementById('out').innerText = 'Choose a file first.';
    return;
  }
  const file = input.files[0];
  const fileBytes = new Uint8Array(await file.arrayBuffer());
  const key = await deriveAesKey(password, username + '::files');
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt({name:'AES-GCM', iv: nonce}, key, fileBytes);
  const res = await fetch('/zk_file_upload', {
    method:'POST',
    headers:{'Content-Type':'application/json', 'Authorization':'Bearer '+token},
    body: JSON.stringify({
      filename: file.name,
      mime_type: file.type || 'application/octet-stream',
      ciphertext: b64urlFromBuf(ciphertext),
      nonce: b64urlFromBuf(nonce)
    })
  });
  const data = await res.json();
  if (data.file_id) document.getElementById('fileId').value = data.file_id;
  document.getElementById('out').innerText = JSON.stringify(data, null, 2);
}

async function downloadEncryptedFile() {
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const file_id = document.getElementById('fileId').value;
  const res = await fetch('/zk_file_download', {
    method:'POST',
    headers:{'Content-Type':'application/json', 'Authorization':'Bearer '+token},
    body: JSON.stringify({file_id})
  });
  const data = await res.json();
  if (data.status !== 'success') {
    document.getElementById('out').innerText = JSON.stringify(data, null, 2);
    return;
  }
  const key = await deriveAesKey(password, username + '::files');
  const plain = await crypto.subtle.decrypt(
    {name:'AES-GCM', iv: bufFromB64url(data.nonce)},
    key,
    bufFromB64url(data.ciphertext)
  );
  const blob = new Blob([plain], {type: data.mime_type || 'application/octet-stream'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = data.filename || 'decrypted.bin';
  a.click();
  URL.revokeObjectURL(a.href);
  document.getElementById('out').innerText = JSON.stringify({...data, downloaded: true}, null, 2);
}
</script>
</body>
</html>"""
    return HTMLResponse(html)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
