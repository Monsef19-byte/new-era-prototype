# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import _common as C


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not C.is_authed(self.headers):
            return C.send_json(self, {"error": "unauthorized"}, 401)
        data = {
            "villas": C.load_content("villas.json", []),
            "home": C.load_content("home.json", {}),
            "apropos": C.load_content("apropos.json", {}),
            "opportunites": C.load_content("opportunites.json", {}),
            "settings": C.load_content("settings.json", {}),
            "blog": C.load_content("blog.json", []),
            "liens": C.load_content("liens.json", {
                "logo": "logo-mono-white.png", "name": "", "tagline": "", "subtitle": "", "cards": []
            }),
        }
        C.send_json(self, data)
