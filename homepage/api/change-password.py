# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import _common as C


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not C.is_authed(self.headers):
            return C.send_json(self, {"error": "unauthorized"}, 401)
        body = C.read_json_body(self)
        current = body.get("current", "")
        new = body.get("new", "")
        if not C.check_password(current):
            return C.send_json(self, {"ok": False, "error": "Mot de passe actuel incorrect"}, 400)
        if len(new) < 4:
            return C.send_json(self, {"ok": False, "error": "Nouveau mot de passe trop court"}, 400)
        C.set_password(new)
        C.send_json(self, {"ok": True})
