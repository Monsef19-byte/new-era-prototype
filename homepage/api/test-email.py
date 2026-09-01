# -*- coding: utf-8 -*-
"""
test-email.py — admin-only "Tester l'envoi" button in the dashboard's
Réglages Email panel. Sends a real test email using whatever SMTP settings
are currently typed in (not necessarily saved yet), so a non-technical site
manager can verify their credentials work before relying on them.
"""
import os
import re
import json
import time
import hmac
import hashlib
import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr
from http.server import BaseHTTPRequestHandler

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


def send_json(handler, obj, status=200):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(length) if length else b"{}"
    try:
        return json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        return {}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not is_authed(self.headers):
            return send_json(self, {"ok": False, "error": "unauthorized"}, 401)

        body = read_json_body(self)
        recipient = (body.get("lead_recipient") or "").strip()
        host = (body.get("smtp_host") or "").strip()
        port = body.get("smtp_port") or 587
        user = (body.get("smtp_user") or "").strip()
        # SMTP password lives only in the SMTP_PASSWORD Vercel env var — never
        # typed into the dashboard or stored in settings.json/Blob — same
        # convention as hamadat-promotion.com.
        password = os.environ.get("SMTP_PASSWORD") or ""
        sender_name = (body.get("smtp_sender_name") or "New Era — Site Web").strip()

        if not password:
            return send_json(self, {"ok": False, "error": "SMTP_PASSWORD n'est pas défini côté serveur (variable d'environnement Vercel)."}, 400)
        if not (recipient and host and user):
            return send_json(self, {"ok": False, "error": "Merci de remplir tous les champs avant de tester."}, 400)

        msg = MIMEText(
            "Ceci est un email de test envoyé depuis le panneau d'administration New Era.\n"
            "Si vous recevez ce message, les réglages email sont corrects.",
            "plain", "utf-8"
        )
        msg["Subject"] = "[New Era] Test des réglages email"
        msg["From"] = formataddr((sender_name, user))
        msg["To"] = recipient

        try:
            context = ssl.create_default_context()
            if int(port) == 465:
                with smtplib.SMTP_SSL(host, int(port), timeout=15, context=context) as server:
                    server.login(user, password)
                    server.sendmail(user, [recipient], msg.as_string())
            else:
                with smtplib.SMTP(host, int(port), timeout=15) as server:
                    server.starttls(context=context)
                    server.login(user, password)
                    server.sendmail(user, [recipient], msg.as_string())
            return send_json(self, {"ok": True})
        except Exception as e:
            return send_json(self, {"ok": False, "error": str(e)}, 500)
