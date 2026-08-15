# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import _common as C


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = C.read_json_body(self)
        pw = body.get("password", "")
        if C.check_password(pw):
            tok = C.make_session_token()
            cookie = "ne_session={}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={}".format(tok, C.SESSION_TTL)
            C.send_json(self, {"ok": True}, 200, cookie=cookie)
        else:
            C.send_json(self, {"ok": False, "error": "Mot de passe incorrect"}, 401)
