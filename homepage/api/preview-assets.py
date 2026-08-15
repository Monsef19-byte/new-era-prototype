# -*- coding: utf-8 -*-
"""GET /api/preview-assets?file=<name> — used by the dashboard to show a
thumbnail of an already-selected image. Redirects to the Blob copy if the
file was uploaded online but not published yet, otherwise falls back to the
already-live copy on the site itself."""
from http.server import BaseHTTPRequestHandler
import _common as C


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not C.is_authed(self.headers):
            return C.send_json(self, {"error": "unauthorized"}, 401)
        fname = C.safe_filename(C.query_param(self, "file"))
        if not fname:
            return C.send_json(self, {"error": "missing file"}, 400)
        url = C.blob_find_url("assets/" + fname)
        if not url:
            url = "/assets/" + fname
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()
