# -*- coding: utf-8 -*-
"""
leads.py — admin-only. Lists stored leads (Vercel Blob, prefix "leads/")
and returns basic statistics for the dashboard "Leads" page. Session-authed
like every other admin endpoint (ne_session cookie).
"""
import os
import re
import json
import time
import hmac
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from http.server import BaseHTTPRequestHandler

BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
SESSION_SECRET = os.environ.get("ADMIN_SESSION_SECRET", "")


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


def blob_get_bytes_url(url):
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.read()
    except Exception:
        return None


def send_json(handler, obj, status=200):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not is_authed(self.headers):
            return send_json(self, {"error": "unauthorized"}, 401)

        blobs = [b for b in blob_list("leads/") if b.get("pathname", "").endswith(".json")]
        leads = []
        for b in blobs:
            raw = blob_get_bytes_url(b.get("url"))
            if not raw:
                continue
            try:
                leads.append(json.loads(raw.decode("utf-8")))
            except Exception:
                continue

        leads.sort(key=lambda l: l.get("ts", 0), reverse=True)

        stats_by_code = {}
        for l in leads:
            code = l.get("code", "NE-AUTRE")
            stats_by_code[code] = stats_by_code.get(code, 0) + 1

        thirty_days_ago = int(time.time()) - 30 * 86400
        last_30_days = sum(1 for l in leads if l.get("ts", 0) >= thirty_days_ago)

        send_json(self, {
            "leads": leads[:500],
            "total": len(leads),
            "last_30_days": last_30_days,
            "by_code": stats_by_code,
        })
