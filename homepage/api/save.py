# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import _common as C


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not C.is_authed(self.headers):
            return C.send_json(self, {"error": "unauthorized"}, 401)
        section = C.query_param(self, "section")
        if section not in C.SAFE_SECTIONS:
            return C.send_json(self, {"error": "unknown section"}, 400)
        try:
            data = C.read_json_body(self)
        except Exception as e:
            return C.send_json(self, {"error": "invalid json: {}".format(e)}, 400)
        C.save_content(section + ".json", data)
        C.send_json(self, {"ok": True})
