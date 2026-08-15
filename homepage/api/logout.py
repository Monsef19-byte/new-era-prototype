# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import _common as C


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        cookie = "ne_session=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0"
        C.send_json(self, {"ok": True}, 200, cookie=cookie)
