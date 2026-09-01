#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — local admin server for the New Era website.

Pure standard library on purpose: the person running this is not a
developer, so there is nothing to "pip install", nothing that can fail
because of a missing package. Double-click the launcher, it works.

Routes:
  GET  /                       -> admin UI (static/index.html), gated by login
  GET  /login                  -> login page
  POST /api/login              {password} -> sets session cookie
  POST /api/logout
  GET  /api/content            -> {villas, home, apropos, opportunites, settings, blog}
  POST /api/save/<section>     body=JSON -> writes content/<section>.json
  POST /api/publish            -> regenerates the static site from content/*.json
  POST /api/upload             multipart file -> saves into Homepage/assets (+ mirror)
  GET  /assets/<file>          -> preview of a site asset image (for the dashboard)
"""
import http.server
import socketserver
import json
import os
import re
import sys
import hashlib
import secrets
import mimetypes
import webbrowser
import threading
import subprocess
import tempfile
import shutil
import platform
import gzip
import urllib.request
import urllib.error
import urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.dirname(BASE)
HOMEPAGE = os.path.join(PROTO, "Homepage")
MIRROR = os.path.join(PROTO, "Villa Agata")
CONTENT = os.path.join(BASE, "content")
STATIC = os.path.join(BASE, "static")
AUTH_FILE = os.path.join(CONTENT, "admin_auth.json")
BIN_DIR = os.path.join(BASE, "bin")
LOCAL_FFMPEG = os.path.join(BIN_DIR, "ffmpeg")

# Static ffmpeg builds published by eugeneware/ffmpeg-static on GitHub —
# actively maintained (1.4k+ stars), GPG-signed releases, used by the
# popular fluent-ffmpeg library. The "latest/download" URL is a stable
# GitHub feature that always resolves to whatever the newest release is,
# so this never needs to be updated by hand.
FFMPEG_DOWNLOAD_BASE = "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/"
FFMPEG_ASSET_BY_ARCH = {
    "arm64": "ffmpeg-darwin-arm64.gz",
    "x86_64": "ffmpeg-darwin-x64.gz",
}

def ensure_ffmpeg():
    """Returns a path to a working ffmpeg binary, with zero setup required
    from the person using the admin panel:
      1. Reuse the copy we already downloaded once, if present.
      2. Reuse a system-wide ffmpeg if the user happens to have one (e.g.
         via Homebrew) — never re-download in that case.
      3. Otherwise, download a static build matching this Mac's chip
         (Apple Silicon / Intel) straight from GitHub, no pip/brew/Terminal
         involved, and cache it in Admin/bin/ for every future publish.
    Returns None if none of the above worked (e.g. no internet on first
    run) — the caller falls back to uploading the raw file with a warning."""
    if os.path.exists(LOCAL_FFMPEG) and os.access(LOCAL_FFMPEG, os.X_OK):
        return LOCAL_FFMPEG

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    if platform.system() != "Darwin":
        return None  # this auto-download path only targets the client's Mac

    arch = platform.machine()
    asset = FFMPEG_ASSET_BY_ARCH.get(arch)
    if not asset:
        return None

    try:
        req = urllib.request.Request(FFMPEG_DOWNLOAD_BASE + asset, headers={"User-Agent": "NewEraAdmin/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            compressed = resp.read()
        data = gzip.decompress(compressed)
        os.makedirs(BIN_DIR, exist_ok=True)
        tmp_path = LOCAL_FFMPEG + ".part"
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.chmod(tmp_path, 0o755)
        # Ad-hoc code-sign so Gatekeeper doesn't balk on first run — costs
        # nothing if the `codesign` tool (Xcode Command Line Tools) isn't
        # present, we just skip it silently.
        try:
            subprocess.run(["codesign", "-s", "-", tmp_path], capture_output=True, timeout=30)
        except Exception:
            pass
        os.replace(tmp_path, LOCAL_FFMPEG)
        return LOCAL_FFMPEG
    except Exception:
        return None

sys.path.insert(0, BASE)
import generator  # noqa: E402

PORT = 5959
SESSIONS = set()

def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ensure_auth():
    if not os.path.exists(AUTH_FILE):
        default_password = "newera2026"
        salt = secrets.token_hex(8)
        h = hashlib.sha256((salt + default_password).encode("utf-8")).hexdigest()
        save_json(AUTH_FILE, {"salt": salt, "hash": h})
        print("=" * 60)
        print(" Mot de passe admin par défaut : {}".format(default_password))
        print(" (à changer depuis l'onglet Réglages une fois connecté)")
        print("=" * 60)

def check_password(pw):
    data = load_json(AUTH_FILE)
    h = hashlib.sha256((data["salt"] + pw).encode("utf-8")).hexdigest()
    return h == data["hash"]

def set_password(pw):
    salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()
    save_json(AUTH_FILE, {"salt": salt, "hash": h})

SAFE_SECTIONS = {"villas", "home", "apropos", "opportunites", "settings", "blog", "liens", "videos", "gallery"}

def slugify(s):
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s)
    return s or "residence"

def safe_filename(name):
    name = os.path.basename(name)
    name = re.sub(r"[^A-Za-z0-9_.\-]", "-", name)
    return name


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "NewEraAdmin/1.0"

    def log_message(self, fmt, *args):
        pass  # keep the terminal window quiet/friendly

    # ---------------------------------------------------------- helpers
    def _cookie_token(self):
        cookie = self.headers.get("Cookie", "")
        m = re.search(r"ne_session=([a-f0-9]+)", cookie)
        return m.group(1) if m else None

    def _authed(self):
        tok = self._cookie_token()
        return tok is not None and tok in SESSIONS

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type=None):
        if not os.path.exists(path):
            self._send_json({"error": "not found"}, 404)
            return
        if content_type is None:
            content_type, _ = mimetypes.guess_type(path)
            content_type = content_type or "application/octet-stream"
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    # ---------------------------------------------------------- GET
    def do_GET(self):
        path = self.path.split("?")[0]

        if path.startswith("/api/"):
            return self.handle_api_get(path)

        if path.startswith("/preview-assets/"):
            fname = safe_filename(path[len("/preview-assets/"):])
            return self._send_file(os.path.join(HOMEPAGE, "assets", fname))

        if path == "/login" or path == "/login.html":
            return self._send_file(os.path.join(STATIC, "login.html"), "text/html; charset=utf-8")

        if path in ("/", "/admin", "/admin/", "/index.html"):
            if not self._authed():
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            return self._send_file(os.path.join(STATIC, "index.html"), "text/html; charset=utf-8")

        # any other static asset under /static/
        safe_rel = path.lstrip("/")
        full = os.path.normpath(os.path.join(STATIC, safe_rel))
        if full.startswith(STATIC) and os.path.exists(full):
            return self._send_file(full)

        self._send_json({"error": "not found"}, 404)

    def _query_param(self, name):
        qs = self.path.split("?", 1)[1] if "?" in self.path else ""
        for pair in qs.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                if k == name:
                    return urllib.parse.unquote_plus(v)
        return None

    def handle_api_get(self, path):
        if path == "/api/preview-assets":
            fname = safe_filename(self._query_param("file") or "")
            return self._send_file(os.path.join(HOMEPAGE, "assets", fname))
        if path == "/api/content":
            if not self._authed():
                return self._send_json({"error": "unauthorized"}, 401)
            data = {
                "villas": load_json(os.path.join(CONTENT, "villas.json"), []),
                "home": load_json(os.path.join(CONTENT, "home.json"), {}),
                "apropos": load_json(os.path.join(CONTENT, "apropos.json"), {}),
                "opportunites": load_json(os.path.join(CONTENT, "opportunites.json"), {}),
                "settings": load_json(os.path.join(CONTENT, "settings.json"), {}),
                "blog": load_json(os.path.join(CONTENT, "blog.json"), []),
                "liens": load_json(os.path.join(CONTENT, "liens.json"), {
                    "logo": "logo-mono-white.png", "name": "", "tagline": "", "subtitle": "", "cards": []
                }),
                "videos": load_json(os.path.join(CONTENT, "videos.json"), {
                    "section_kicker": "Vidéos", "section_title": "New Era en vidéo",
                    "section_lede": "Visites virtuelles et actualités de nos résidences.", "items": []
                }),
                "gallery": load_json(os.path.join(CONTENT, "gallery.json"), {
                    "kicker": "Catalogue", "title": "Catalogue & Galerie",
                    "lede": "Un aperçu de nos réalisations, plans et documents.", "items": []
                }),
            }
            # SMTP password never travels to the client — only in the
            # SMTP_PASSWORD env var (same convention as hamadat-promotion.com).
            if isinstance(data.get("settings"), dict):
                data["settings"].pop("smtp_password", None)
                data["settings"]["smtp_password_set"] = bool(os.environ.get("SMTP_PASSWORD"))
            return self._send_json(data)
        self._send_json({"error": "not found"}, 404)

    # ---------------------------------------------------------- POST
    def do_POST(self):
        path = self.path.split("?")[0]

        if path == "/api/login":
            body = self._read_json_body()
            if check_password(body.get("password", "")):
                tok = secrets.token_hex(24)
                SESSIONS.add(tok)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Set-Cookie", "ne_session={}; Path=/; HttpOnly; SameSite=Lax".format(tok))
                body_out = json.dumps({"ok": True}).encode("utf-8")
                self.send_header("Content-Length", str(len(body_out)))
                self.end_headers()
                self.wfile.write(body_out)
            else:
                self._send_json({"ok": False, "error": "Mot de passe incorrect"}, 401)
            return

        if path == "/api/logout":
            tok = self._cookie_token()
            if tok in SESSIONS:
                SESSIONS.discard(tok)
            return self._send_json({"ok": True})

        if not self._authed():
            return self._send_json({"error": "unauthorized"}, 401)

        if path == "/api/save":
            section = self._query_param("section") or ""
            if section not in SAFE_SECTIONS:
                return self._send_json({"error": "unknown section"}, 400)
            try:
                data = self._read_json_body()
            except Exception as e:
                return self._send_json({"error": "invalid json: {}".format(e)}, 400)
            if section == "settings":
                # SMTP password is never stored in content — only in the
                # SMTP_PASSWORD environment variable (same convention as
                # hamadat-promotion.com). Strip it defensively.
                data.pop("smtp_password", None)
            save_json(os.path.join(CONTENT, section + ".json"), data)
            return self._send_json({"ok": True})

        if path == "/api/change-password":
            body = self._read_json_body()
            current = body.get("current", "")
            new = body.get("new", "")
            if not check_password(current):
                return self._send_json({"ok": False, "error": "Mot de passe actuel incorrect"}, 400)
            if len(new) < 4:
                return self._send_json({"ok": False, "error": "Nouveau mot de passe trop court"}, 400)
            set_password(new)
            return self._send_json({"ok": True})

        if path == "/api/publish":
            try:
                result = generator.publish()
                self.cleanup_orphan_villas()
                return self._send_json(result)
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        if path == "/api/upload":
            return self.handle_upload()

        self._send_json({"error": "not found"}, 404)

    def cleanup_orphan_villas(self):
        villas = load_json(os.path.join(CONTENT, "villas.json"), [])
        keep = set(v["slug"] + ".html" for v in villas)
        for d in (HOMEPAGE, MIRROR):
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                if fn.startswith("villa-") and fn.endswith(".html") and fn not in keep:
                    try:
                        os.remove(os.path.join(d, fn))
                    except OSError:
                        pass

    def handle_upload(self):
        """Minimal multipart/form-data parser — no external/deprecated
        modules (Python's own `cgi` module is gone in 3.13+), so this stays
        working no matter which Python the client's Mac ships with."""
        ctype = self.headers.get("Content-Type", "")
        m = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', ctype)
        if "multipart/form-data" not in ctype or not m:
            return self._send_json({"error": "expected multipart/form-data"}, 400)
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
            body = body[:-2] if body.endswith(b"\r\n") else body  # trailing CRLF before next boundary
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
            return self._send_json({"error": "no file field"}, 400)

        prefix = re.sub(r"[^a-z0-9\-]", "", fields.get("prefix", "").lower())
        ext = os.path.splitext(file_name)[1].lower()

        if ext in (".mp4", ".mov", ".m4v", ".webm"):
            return self.handle_video_upload(file_data, ext)

        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            return self._send_json({"error": "type de fichier non supporté (jpg/png/webp, ou mp4/mov/webm pour une vidéo)"}, 400)
        base = safe_filename(os.path.splitext(file_name)[0]) or "image"
        fname = "{}-{}{}".format(prefix, base, ext) if prefix else "{}{}".format(base, ext)
        fname = fname.lower()
        for d in (HOMEPAGE, MIRROR):
            assets_dir = os.path.join(d, "assets")
            os.makedirs(assets_dir, exist_ok=True)
            with open(os.path.join(assets_dir, fname), "wb") as f:
                f.write(file_data)
        return self._send_json({"ok": True, "filename": fname})

    def handle_video_upload(self, file_data, ext):
        """Saves the homepage hero video as the fixed filename main.js
        expects (assets/hero-video.mp4). Compresses via ffmpeg if it's
        installed on this Mac; otherwise uploads the raw file as-is and
        warns the caller so they know to compress it themselves first."""
        ffmpeg = ensure_ffmpeg()
        warning = None
        out_bytes = file_data

        if ffmpeg:
            in_path = out_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tin:
                    tin.write(file_data)
                    in_path = tin.name
                out_path = in_path + "-compressed.mp4"
                cmd = [
                    ffmpeg, "-y", "-i", in_path,
                    "-vcodec", "libx264", "-crf", "24", "-preset", "medium",
                    "-vf", "scale='min(1920,iw)':-2",
                    "-movflags", "+faststart",
                    "-acodec", "aac", "-b:a", "128k",
                    out_path,
                ]
                proc = subprocess.run(cmd, capture_output=True, timeout=900)
                if proc.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    with open(out_path, "rb") as f:
                        out_bytes = f.read()
                else:
                    warning = "La compression automatique a échoué — le fichier original a été mis en ligne sans compression."
            except Exception:
                warning = "La compression automatique a échoué — le fichier original a été mis en ligne sans compression."
            finally:
                for p in (in_path, out_path):
                    if p and os.path.exists(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass
        else:
            warning = ("Le téléchargement automatique de l'outil de compression a échoué (pas de connexion "
                        "internet au premier envoi ?) : la vidéo a été mise en ligne sans compression. "
                        "Réessayez avec une connexion active, ou compressez-la vous-même avant l'envoi "
                        "(ex. avec HandBrake).")

        for d in (HOMEPAGE, MIRROR):
            assets_dir = os.path.join(d, "assets")
            os.makedirs(assets_dir, exist_ok=True)
            with open(os.path.join(assets_dir, "hero-video.mp4"), "wb") as f:
                f.write(out_bytes)

        resp = {"ok": True, "filename": "hero-video.mp4"}
        if warning:
            resp["warning"] = warning
        return self._send_json(resp)


def main():
    ensure_auth()
    os.chdir(BASE)
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), Handler) as httpd:
        url = "http://127.0.0.1:{}/".format(PORT)
        print("Panneau admin New Era démarré : {}".format(url))
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
