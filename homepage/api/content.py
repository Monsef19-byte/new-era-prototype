# -*- coding: utf-8 -*-
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
    def do_GET(self):
        if not is_authed(self.headers):
            return send_json(self, {"error": "unauthorized"}, 401)
        data = {
            "villas": load_content("villas.json", []),
            "home": load_content("home.json", {}),
            "apropos": load_content("apropos.json", {}),
            "opportunites": load_content("opportunites.json", {}),
            "settings": load_content("settings.json", {}),
            "blog": load_content("blog.json", []),
            "liens": load_content("liens.json", {
                "logo": "logo-mono-white.png", "name": "", "tagline": "", "subtitle": "", "cards": []
            }),
        }
        send_json(self, data)
