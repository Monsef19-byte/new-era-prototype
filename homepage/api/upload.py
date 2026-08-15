# -*- coding: utf-8 -*-
"""POST /api/upload — multipart/form-data image or video upload.

Files are stored in Vercel Blob under "assets/<filename>" (same naming
convention as the local admin, which writes into Homepage/assets/). The
build step (admin/generator.py, sync_blob_assets()) downloads everything
under "assets/" into homepage/assets/ before regenerating the site, so a
plain filename saved in content JSON continues to resolve exactly like
today (src="assets/<filename>") — no template changes needed.

Video compression: the local admin auto-compresses with ffmpeg, which needs
a long-running subprocess (minutes) that a serverless function's execution
limit doesn't allow. Online uploads are stored as-is, with the same warning
message the local admin already shows when ffmpeg isn't available, pointing
the user at compressing the file themselves first (e.g. with HandBrake) or
using the local admin panel for video."""
import os
import re
import json
import time
import hmac
import hashlib
import secrets
import urllib.request
import urllib.parse
import urllib.error
from http.server import BaseHTTPRequestHandler

# ---- inlined from _common.py (Vercel Python doesn't reliably bundle sibling
# underscore-prefixed modules, so each endpoint is self-contained) ----
BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
SESSION_SECRET = os.environ.get("ADMIN_SESSION_SECRET", "")
SESSION_TTL = 60 * 60 * 12  # 12h

SAFE_SECTIONS = {"villas", "home", "apropos", "opportunites", "settings", "blog", "liens"}

SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_seed")


# ---------------------------------------------------------------- sessions
def make_session_token():
    exp = str(int(time.time()) + SESSION_TTL)
    sig = hmac.new(SESSION_SECRET.encode("utf-8"), exp.encode("utf-8"), hashlib.sha256).hexdigest()
    return exp + "." + sig


def verify_session_token(tok):
    if not tok or "." not in tok or not SESSION_SECRET:
        return False
    exp_s, sig = tok.split(".", 1)
    expected = hmac.new(SESSION_SECRET.encode("utf-8"), exp_s.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        return int(exp_s) > int(time.time())
    except ValueError:
        return False


def get_cookie(headers, name):
    cookie = headers.get("Cookie") or headers.get("cookie") or ""
    m = re.search(r"(?:^|;\s*)" + re.escape(name) + r"=([^;]+)", cookie)
    return m.group(1) if m else None


def is_authed(headers):
    return verify_session_token(get_cookie(headers, "ne_session"))


# ---------------------------------------------------------------- blob I/O
def _blob_headers(extra=None):
    h = {"authorization": "Bearer " + BLOB_TOKEN}
    if extra:
        h.update(extra)
    return h


def blob_list(prefix):
    if not BLOB_TOKEN:
        return []
    url = "https://blob.vercel-storage.com/?prefix=" + urllib.parse.quote(prefix) + "&limit=1000"
    req = urllib.request.Request(url, headers=_blob_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8")).get("blobs", [])
    except Exception:
        return []


def blob_find_url(pathname):
    for b in blob_list(pathname):
        if b.get("pathname") == pathname:
            return b.get("url")
    return None


def blob_get_bytes(pathname):
    url = blob_find_url(pathname)
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.read()
    except Exception:
        return None


def blob_put_bytes(pathname, data, content_type="application/octet-stream"):
    url = "https://blob.vercel-storage.com/" + urllib.parse.quote(pathname)
    req = urllib.request.Request(url, data=data, method="PUT", headers=_blob_headers({
        "x-content-type": content_type,
        "x-add-random-suffix": "0",
        "x-allow-overwrite": "1",
    }))
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def blob_put_json(pathname, obj):
    data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    return blob_put_bytes(pathname, data, "application/json; charset=utf-8")


# ---------------------------------------------------------------- content (with seed fallback)
def _seed_path(name):
    return os.path.join(SEED_DIR, name)


def load_content(name, default=None):
    raw = blob_get_bytes("content/" + name)
    if raw is not None:
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            pass
    seed = _seed_path(name)
    if os.path.exists(seed):
        with open(seed, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_content(name, data):
    blob_put_json("content/" + name, data)


# ---------------------------------------------------------------- auth (password)
def check_password(pw):
    auth = load_content("admin_auth.json")
    if not auth:
        return False
    h = hashlib.sha256((auth["salt"] + pw).encode("utf-8")).hexdigest()
    return h == auth["hash"]


def set_password(pw):
    salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()
    save_content("admin_auth.json", {"salt": salt, "hash": h})


# ---------------------------------------------------------------- HTTP helpers
def send_json(handler, obj, status=200, cookie=None):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    if cookie:
        handler.send_header("Set-Cookie", cookie)
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(length) if length else b"{}"
    return json.loads(raw.decode("utf-8") or "{}")


def query_param(handler, name):
    qs = urllib.parse.urlparse(handler.path).query
    return urllib.parse.parse_qs(qs).get(name, [None])[0]


def safe_filename(name):
    name = os.path.basename(name or "")
    name = re.sub(r"[^A-Za-z0-9_.\-]", "-", name)
    return name

# ---- endpoint ----
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not is_authed(self.headers):
            return send_json(self, {"error": "unauthorized"}, 401)

        ctype = self.headers.get("Content-Type", "")
        m = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', ctype)
        if "multipart/form-data" not in ctype or not m:
            return send_json(self, {"error": "expected multipart/form-data"}, 400)
        boundary = (m.group(1) or m.group(2)).strip().encode("utf-8")
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        parts = raw.split(b"--" + boundary)
        fields = {}
        file_data, file_name = None, None
        for part in parts:
            part = part.strip(b"\r\n")
            if not part or part == b"--":
                continue
            if b"\r\n\r\n" not in part:
                continue
            head, body = part.split(b"\r\n\r\n", 1)
            body = body[:-2] if body.endswith(b"\r\n") else body
            head_text = head.decode("utf-8", errors="replace")
            name_m = re.search(r'name="([^"]+)"', head_text)
            if not name_m:
                continue
            field_name = name_m.group(1)
            fn_m = re.search(r'filename="([^"]*)"', head_text)
            if fn_m and fn_m.group(1):
                file_name = fn_m.group(1)
                file_data = body
            else:
                fields[field_name] = body.decode("utf-8", errors="replace")

        if file_data is None or not file_name:
            return send_json(self, {"error": "no file field"}, 400)

        prefix = re.sub(r"[^a-z0-9\-]", "", fields.get("prefix", "").lower())
        ext = os.path.splitext(file_name)[1].lower()

        if ext in (".mp4", ".mov", ".m4v", ".webm"):
            return self.handle_video(file_data)

        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            return send_json(self, {"error": "type de fichier non supporté (jpg/png/webp, ou mp4/mov/webm pour une vidéo)"}, 400)

        base = safe_filename(os.path.splitext(file_name)[0]) or "image"
        fname = "{}-{}{}".format(prefix, base, ext) if prefix else "{}{}".format(base, ext)
        fname = fname.lower()
        content_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[ext.lstrip(".")]
        blob_put_bytes("assets/" + fname, file_data, content_type)
        send_json(self, {"ok": True, "filename": fname})

    def handle_video(self, file_data):
        blob_put_bytes("assets/hero-video.mp4", file_data, "video/mp4")
        warning = ("Vidéo mise en ligne sans compression automatique (la compression n'est pas "
                    "disponible depuis le panneau en ligne). Compressez-la vous-même avant l'envoi "
                    "(ex. avec HandBrake), ou utilisez le panneau d'administration local sur votre Mac "
                    "pour un envoi avec compression automatique.")
        send_json(self, {"ok": True, "filename": "hero-video.mp4", "warning": warning})
