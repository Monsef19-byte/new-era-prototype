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
import re
import os
from http.server import BaseHTTPRequestHandler
import _common as C


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not C.is_authed(self.headers):
            return C.send_json(self, {"error": "unauthorized"}, 401)

        ctype = self.headers.get("Content-Type", "")
        m = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', ctype)
        if "multipart/form-data" not in ctype or not m:
            return C.send_json(self, {"error": "expected multipart/form-data"}, 400)
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
            return C.send_json(self, {"error": "no file field"}, 400)

        prefix = re.sub(r"[^a-z0-9\-]", "", fields.get("prefix", "").lower())
        ext = os.path.splitext(file_name)[1].lower()

        if ext in (".mp4", ".mov", ".m4v", ".webm"):
            return self.handle_video(file_data)

        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            return C.send_json(self, {"error": "type de fichier non supporté (jpg/png/webp, ou mp4/mov/webm pour une vidéo)"}, 400)

        base = C.safe_filename(os.path.splitext(file_name)[0]) or "image"
        fname = "{}-{}{}".format(prefix, base, ext) if prefix else "{}{}".format(base, ext)
        fname = fname.lower()
        content_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[ext.lstrip(".")]
        C.blob_put_bytes("assets/" + fname, file_data, content_type)
        C.send_json(self, {"ok": True, "filename": fname})

    def handle_video(self, file_data):
        C.blob_put_bytes("assets/hero-video.mp4", file_data, "video/mp4")
        warning = ("Vidéo mise en ligne sans compression automatique (la compression n'est pas "
                    "disponible depuis le panneau en ligne). Compressez-la vous-même avant l'envoi "
                    "(ex. avec HandBrake), ou utilisez le panneau d'administration local sur votre Mac "
                    "pour un envoi avec compression automatique.")
        C.send_json(self, {"ok": True, "filename": "hero-video.mp4", "warning": warning})
